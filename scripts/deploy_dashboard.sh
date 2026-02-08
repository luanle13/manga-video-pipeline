#!/bin/bash
set -e

# Deployment script for Manga Video Pipeline Admin Dashboard
# Packages the application and deploys to EC2 instances via S3

# =============================================================================
# Configuration
# =============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# AWS Configuration (can be overridden via environment variables)
AWS_REGION="${AWS_REGION:-us-east-1}"
DEPLOYMENT_BUCKET="${DEPLOYMENT_BUCKET:-manga-pipeline-deployments}"
DASHBOARD_TAG_KEY="${DASHBOARD_TAG_KEY:-Name}"
DASHBOARD_TAG_VALUE="${DASHBOARD_TAG_VALUE:-manga-dashboard}"

# Package configuration
PACKAGE_NAME="dashboard-latest.zip"
TEMP_DIR="/tmp/manga-dashboard-deploy-$$"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# =============================================================================
# Helper Functions
# =============================================================================

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

cleanup() {
    log_info "Cleaning up temporary files..."
    rm -rf "$TEMP_DIR"
}

trap cleanup EXIT

# =============================================================================
# Validation
# =============================================================================

log_info "Starting dashboard deployment..."
log_info "Project root: $PROJECT_ROOT"
log_info "Deployment bucket: $DEPLOYMENT_BUCKET"
log_info "Region: $AWS_REGION"

# Check if AWS CLI is installed
if ! command -v aws &> /dev/null; then
    log_error "AWS CLI is not installed. Please install it first."
    exit 1
fi

# Check if we're in the right directory
if [ ! -f "$PROJECT_ROOT/src/dashboard/app.py" ]; then
    log_error "Cannot find src/dashboard/app.py. Are you in the project root?"
    exit 1
fi

# Check if S3 bucket exists
if ! aws s3 ls "s3://$DEPLOYMENT_BUCKET" --region "$AWS_REGION" &>/dev/null; then
    log_error "S3 bucket $DEPLOYMENT_BUCKET does not exist or is not accessible"
    log_info "Creating deployment bucket..."
    aws s3 mb "s3://$DEPLOYMENT_BUCKET" --region "$AWS_REGION"
fi

# =============================================================================
# Package Application
# =============================================================================

log_info "Creating deployment package..."

# Create temporary directory
mkdir -p "$TEMP_DIR"

# Copy necessary files
log_info "Copying application files..."

# Source code
cp -r "$PROJECT_ROOT/src" "$TEMP_DIR/"

# Requirements
cp "$PROJECT_ROOT/requirements.txt" "$TEMP_DIR/"

# Scripts
cp -r "$PROJECT_ROOT/scripts" "$TEMP_DIR/"

# Configuration files
[ -f "$PROJECT_ROOT/pyproject.toml" ] && cp "$PROJECT_ROOT/pyproject.toml" "$TEMP_DIR/"
[ -f "$PROJECT_ROOT/.env.example" ] && cp "$PROJECT_ROOT/.env.example" "$TEMP_DIR/"

# Remove unnecessary files
log_info "Cleaning up package..."
find "$TEMP_DIR" -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find "$TEMP_DIR" -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
find "$TEMP_DIR" -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
find "$TEMP_DIR" -type f -name "*.pyc" -delete 2>/dev/null || true
find "$TEMP_DIR" -type f -name "*.pyo" -delete 2>/dev/null || true
find "$TEMP_DIR" -type f -name ".DS_Store" -delete 2>/dev/null || true

# Create zip archive
log_info "Creating zip archive..."
cd "$TEMP_DIR"
zip -r -q "$PACKAGE_NAME" .
PACKAGE_SIZE=$(du -h "$PACKAGE_NAME" | cut -f1)
log_info "Package size: $PACKAGE_SIZE"

# =============================================================================
# Upload to S3
# =============================================================================

log_info "Uploading to S3..."

aws s3 cp "$PACKAGE_NAME" "s3://$DEPLOYMENT_BUCKET/$PACKAGE_NAME" \
    --region "$AWS_REGION" \
    --metadata "deployment-date=$(date -u +%Y-%m-%dT%H:%M:%SZ),git-commit=$(cd "$PROJECT_ROOT" && git rev-parse --short HEAD 2>/dev/null || echo 'unknown')"

# Also create a versioned backup
TIMESTAMP=$(date -u +%Y%m%d-%H%M%S)
VERSIONED_NAME="dashboard-${TIMESTAMP}.zip"

aws s3 cp "s3://$DEPLOYMENT_BUCKET/$PACKAGE_NAME" \
    "s3://$DEPLOYMENT_BUCKET/versions/$VERSIONED_NAME" \
    --region "$AWS_REGION"

log_info "Uploaded to s3://$DEPLOYMENT_BUCKET/$PACKAGE_NAME"
log_info "Backup: s3://$DEPLOYMENT_BUCKET/versions/$VERSIONED_NAME"

# =============================================================================
# Update EC2 Instances
# =============================================================================

log_info "Finding dashboard instances..."

# Find instances with the dashboard tag
INSTANCE_IDS=$(aws ec2 describe-instances \
    --region "$AWS_REGION" \
    --filters "Name=tag:$DASHBOARD_TAG_KEY,Values=$DASHBOARD_TAG_VALUE" \
              "Name=instance-state-name,Values=running" \
    --query 'Reservations[*].Instances[*].InstanceId' \
    --output text)

if [ -z "$INSTANCE_IDS" ]; then
    log_warn "No running dashboard instances found with tag $DASHBOARD_TAG_KEY=$DASHBOARD_TAG_VALUE"
    log_info "Deployment package uploaded to S3. New instances will use it automatically."
    exit 0
fi

log_info "Found instances: $INSTANCE_IDS"

# Create update script
UPDATE_SCRIPT=$(cat <<'EOF'
#!/bin/bash
set -e

echo "==================================================="
echo "Dashboard Update Started: $(date)"
echo "==================================================="

APP_DIR="/opt/manga-pipeline"
DEPLOYMENT_BUCKET="__DEPLOYMENT_BUCKET__"
AWS_REGION="__AWS_REGION__"

# Stop services
echo "Stopping services..."
systemctl stop manga-dashboard.service

# Backup current deployment
echo "Backing up current deployment..."
cd $APP_DIR
tar -czf "/tmp/dashboard-backup-$(date +%Y%m%d-%H%M%S).tar.gz" . || true

# Download new version
echo "Downloading new version..."
aws s3 cp "s3://${DEPLOYMENT_BUCKET}/dashboard-latest.zip" dashboard.zip --region $AWS_REGION

# Extract
echo "Extracting..."
unzip -q -o dashboard.zip
rm dashboard.zip

# Update dependencies
echo "Updating dependencies..."
./venv/bin/pip install --upgrade pip
./venv/bin/pip install -r requirements.txt

# Restart services
echo "Restarting services..."
systemctl start manga-dashboard.service

# Verify
sleep 3
if systemctl is-active --quiet manga-dashboard.service; then
    echo "✓ Dashboard service is running"
else
    echo "✗ Dashboard service failed to start"
    systemctl status manga-dashboard.service --no-pager
    exit 1
fi

echo "==================================================="
echo "Dashboard Update Completed: $(date)"
echo "==================================================="
EOF
)

# Replace placeholders
UPDATE_SCRIPT="${UPDATE_SCRIPT//__DEPLOYMENT_BUCKET__/$DEPLOYMENT_BUCKET}"
UPDATE_SCRIPT="${UPDATE_SCRIPT//__AWS_REGION__/$AWS_REGION}"

# Send update command via SSM
log_info "Deploying to instances via SSM..."

for INSTANCE_ID in $INSTANCE_IDS; do
    log_info "Updating instance: $INSTANCE_ID"

    COMMAND_ID=$(aws ssm send-command \
        --region "$AWS_REGION" \
        --instance-ids "$INSTANCE_ID" \
        --document-name "AWS-RunShellScript" \
        --parameters "commands=[\"$UPDATE_SCRIPT\"]" \
        --query 'Command.CommandId' \
        --output text)

    log_info "SSM Command ID: $COMMAND_ID"

    # Wait for command to complete (max 2 minutes)
    log_info "Waiting for update to complete..."
    for i in {1..24}; do
        STATUS=$(aws ssm get-command-invocation \
            --region "$AWS_REGION" \
            --command-id "$COMMAND_ID" \
            --instance-id "$INSTANCE_ID" \
            --query 'Status' \
            --output text 2>/dev/null || echo "Pending")

        if [ "$STATUS" = "Success" ]; then
            log_info "✓ Update completed successfully on $INSTANCE_ID"
            break
        elif [ "$STATUS" = "Failed" ] || [ "$STATUS" = "TimedOut" ] || [ "$STATUS" = "Cancelled" ]; then
            log_error "✗ Update failed on $INSTANCE_ID (Status: $STATUS)"
            # Get output
            aws ssm get-command-invocation \
                --region "$AWS_REGION" \
                --command-id "$COMMAND_ID" \
                --instance-id "$INSTANCE_ID" \
                --query 'StandardErrorContent' \
                --output text
            break
        fi

        echo -n "."
        sleep 5
    done
    echo ""
done

# =============================================================================
# Summary
# =============================================================================

echo ""
log_info "==================================================="
log_info "Deployment Summary"
log_info "==================================================="
log_info "Package: $PACKAGE_NAME ($PACKAGE_SIZE)"
log_info "S3 Location: s3://$DEPLOYMENT_BUCKET/$PACKAGE_NAME"
log_info "Instances Updated: $(echo $INSTANCE_IDS | wc -w)"
log_info "==================================================="
log_info "Deployment completed successfully!"
log_info "==================================================="
echo ""

# Cleanup happens automatically via trap
exit 0
