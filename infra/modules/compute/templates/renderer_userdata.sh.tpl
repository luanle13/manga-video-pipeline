#!/bin/bash
# =============================================================================
# Video Renderer EC2 Spot Instance User Data Script
# =============================================================================
# This script runs on instance launch to:
# 1. Install Python 3.12 and FFmpeg
# 2. Fetch the job_id from SSM Parameter Store
# 3. Run the renderer to process the video
# 4. Send callback to Step Functions on completion
# 5. Terminate the instance
# =============================================================================

set -e

# Configuration from Terraform
REGION="${region}"
PROJECT_NAME="${project_name}"
S3_BUCKET="${s3_bucket}"
DYNAMODB_JOBS_TABLE="${dynamodb_jobs_table}"
DYNAMODB_SETTINGS_TABLE="${dynamodb_settings_table}"
YOUTUBE_SECRET_NAME="${youtube_secret_name}"
CLEANUP_FUNCTION_NAME="${cleanup_function_name}"
LOG_LEVEL="${log_level}"
ACTIVITY_ARN="${activity_arn}"

# SSM parameter paths
JOB_ID_PARAM="/$PROJECT_NAME/renderer/current-job-id"

# Logging setup
LOG_GROUP="/aws/ec2/$PROJECT_NAME-renderer"

# Get instance ID using IMDSv2 (required for this instance)
IMDS_TOKEN=$(curl -s -X PUT "http://169.254.169.254/latest/api/token" -H "X-aws-ec2-metadata-token-ttl-seconds: 21600")
INSTANCE_ID=$(curl -s -H "X-aws-ec2-metadata-token: $IMDS_TOKEN" http://169.254.169.254/latest/meta-data/instance-id)
LOG_STREAM="$INSTANCE_ID/$(date +%Y-%m-%d)"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
    # Also send to CloudWatch Logs
    aws logs put-log-events \
        --log-group-name "$LOG_GROUP" \
        --log-stream-name "$LOG_STREAM" \
        --log-events "timestamp=$(date +%s000),message=$1" \
        --region "$REGION" 2>/dev/null || true
}

# Create log stream
aws logs create-log-stream \
    --log-group-name "$LOG_GROUP" \
    --log-stream-name "$LOG_STREAM" \
    --region "$REGION" 2>/dev/null || true

log "Starting renderer instance: $INSTANCE_ID"

# =============================================================================
# 1. Install System Dependencies
# =============================================================================

log "Installing system dependencies..."

# Update system packages
dnf update -y

# Install Python 3.12 and development tools
dnf install -y python3.12 python3.12-pip python3.12-devel

# Install additional dependencies for video processing
dnf install -y \
    gcc \
    gcc-c++ \
    make \
    git \
    jq \
    tar \
    xz

# Install FFmpeg from static build (not available in AL2023 repos)
log "Installing FFmpeg from static build..."
cd /tmp
curl -L -o ffmpeg-release-amd64-static.tar.xz https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz
tar -xf ffmpeg-release-amd64-static.tar.xz
cp ffmpeg-*-amd64-static/ffmpeg /usr/local/bin/
cp ffmpeg-*-amd64-static/ffprobe /usr/local/bin/
chmod +x /usr/local/bin/ffmpeg /usr/local/bin/ffprobe
rm -rf ffmpeg-*
cd -

# Verify ffmpeg installation
ffmpeg -version

# Set Python 3.12 as default (use symlink since alternatives may not be set up)
ln -sf /usr/bin/python3.12 /usr/local/bin/python3
export PATH="/usr/local/bin:$PATH"

# Upgrade pip
python3.12 -m pip install --upgrade pip

log "System dependencies installed"

# =============================================================================
# 2. Fetch Job Configuration from SSM
# =============================================================================

log "Fetching job configuration from SSM..."

# Get job ID
JOB_ID=$(aws ssm get-parameter \
    --name "$JOB_ID_PARAM" \
    --region "$REGION" \
    --query 'Parameter.Value' \
    --output text)

if [ "$JOB_ID" == "none" ] || [ -z "$JOB_ID" ]; then
    log "ERROR: No job ID found in SSM parameter"
    # Terminate instance on error
    aws ec2 terminate-instances --instance-ids "$INSTANCE_ID" --region "$REGION"
    exit 1
fi

log "Processing job: $JOB_ID"

# Get task from Step Functions Activity (this blocks until a task is available)
log "Polling for Step Functions Activity task..."
ACTIVITY_RESPONSE=$(aws stepfunctions get-activity-task \
    --activity-arn "$ACTIVITY_ARN" \
    --worker-name "$INSTANCE_ID" \
    --region "$REGION")

TASK_TOKEN=$(echo "$ACTIVITY_RESPONSE" | jq -r '.taskToken')
TASK_INPUT=$(echo "$ACTIVITY_RESPONSE" | jq -r '.input')

if [ -z "$TASK_TOKEN" ] || [ "$TASK_TOKEN" = "null" ]; then
    log "ERROR: Failed to get task token from Activity"
    exit 1
fi

log "Received task token from Activity"

# Override JOB_ID from task input if available
TASK_JOB_ID=$(echo "$TASK_INPUT" | jq -r '.job_id // empty')
if [ -n "$TASK_JOB_ID" ]; then
    JOB_ID="$TASK_JOB_ID"
    log "Using job_id from task input: $JOB_ID"
fi

# =============================================================================
# 3. Download and Setup Application Code
# =============================================================================

log "Setting up application code..."

# Create working directory
WORK_DIR="/opt/manga-renderer"
mkdir -p "$WORK_DIR"
cd "$WORK_DIR"

# Download application code from S3
aws s3 cp "s3://$S3_BUCKET/deployments/renderer-latest.tar.gz" ./renderer.tar.gz --region "$REGION"
tar -xzf renderer.tar.gz
rm renderer.tar.gz

# Install Python dependencies
python3.12 -m pip install -r requirements.txt

log "Application code ready"

# =============================================================================
# 4. Register SIGTERM Handler for Spot Interruption
# =============================================================================

# Spot interruption handler - save checkpoint before termination
handle_interruption() {
    log "Received SIGTERM - Spot interruption detected"

    # Save checkpoint to S3
    if [ -f "$WORK_DIR/checkpoint.json" ]; then
        aws s3 cp "$WORK_DIR/checkpoint.json" \
            "s3://$S3_BUCKET/jobs/$JOB_ID/checkpoint.json" \
            --region "$REGION"
        log "Checkpoint saved to S3"
    fi

    # Send task failure to Step Functions
    if [ -n "$TASK_TOKEN" ] && [ "$TASK_TOKEN" != "none" ]; then
        aws stepfunctions send-task-failure \
            --task-token "$TASK_TOKEN" \
            --error "SpotInterruption" \
            --cause "Instance received Spot interruption warning" \
            --region "$REGION" || true
    fi

    exit 0
}

trap handle_interruption SIGTERM

# =============================================================================
# 5. Run the Renderer
# =============================================================================

log "Starting video rendering..."

# Export environment variables for the renderer
export AWS_DEFAULT_REGION="$REGION"
export S3_BUCKET="$S3_BUCKET"
export DYNAMODB_JOBS_TABLE="$DYNAMODB_JOBS_TABLE"
export DYNAMODB_SETTINGS_TABLE="$DYNAMODB_SETTINGS_TABLE"
export YOUTUBE_SECRET_NAME="$YOUTUBE_SECRET_NAME"
export JOB_ID="$JOB_ID"
export LOG_LEVEL="$LOG_LEVEL"
export TASK_TOKEN="$TASK_TOKEN"

# Run the renderer
RESULT=0
python3.12 -m src.renderer.main || RESULT=$?

# =============================================================================
# 6. Handle Completion
# =============================================================================

if [ $RESULT -eq 0 ]; then
    log "Rendering completed successfully"

    # Send success callback to Step Functions
    if [ -n "$TASK_TOKEN" ] && [ "$TASK_TOKEN" != "none" ]; then
        aws stepfunctions send-task-success \
            --task-token "$TASK_TOKEN" \
            --task-output "{\"job_id\": \"$JOB_ID\", \"status\": \"completed\"}" \
            --region "$REGION"
        log "Step Functions callback sent"
    fi
else
    log "ERROR: Rendering failed with code $RESULT"

    # Send failure callback to Step Functions
    if [ -n "$TASK_TOKEN" ] && [ "$TASK_TOKEN" != "none" ]; then
        aws stepfunctions send-task-failure \
            --task-token "$TASK_TOKEN" \
            --error "RenderingFailed" \
            --cause "Renderer exited with code $RESULT" \
            --region "$REGION" || true
    fi
fi

# =============================================================================
# 7. Cleanup and Terminate
# =============================================================================

log "Terminating instance..."

# Clear SSM parameters
aws ssm put-parameter \
    --name "$JOB_ID_PARAM" \
    --value "none" \
    --type String \
    --overwrite \
    --region "$REGION" || true

# Terminate this instance
aws ec2 terminate-instances --instance-ids "$INSTANCE_ID" --region "$REGION"
