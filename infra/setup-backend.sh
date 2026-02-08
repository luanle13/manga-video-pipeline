#!/bin/bash
set -e

# Setup script for Terraform S3 backend
# This script creates the S3 bucket and DynamoDB table required for Terraform remote state

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}╔══════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║           Terraform Backend Setup for Manga Pipeline            ║${NC}"
echo -e "${BLUE}╚══════════════════════════════════════════════════════════════════╝${NC}"
echo ""

# Configuration
DEFAULT_REGION="ap-southeast-1"
DYNAMODB_TABLE="manga-pipeline-tfstate-lock"

# Get AWS account ID
echo -e "${YELLOW}→${NC} Getting AWS account ID..."
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)

if [ -z "$ACCOUNT_ID" ]; then
    echo -e "${RED}✗ Failed to get AWS account ID. Is AWS CLI configured?${NC}"
    exit 1
fi

echo -e "${GREEN}✓${NC} AWS Account ID: ${ACCOUNT_ID}"

# Set bucket name
BUCKET_NAME="manga-pipeline-tfstate-${ACCOUNT_ID}"

# Get region (use default or from AWS CLI config)
REGION="${AWS_REGION:-$DEFAULT_REGION}"
echo -e "${GREEN}✓${NC} Region: ${REGION}"
echo ""

# Check if bucket already exists
echo -e "${YELLOW}→${NC} Checking if S3 bucket exists..."
if aws s3 ls "s3://${BUCKET_NAME}" --region "$REGION" 2>/dev/null; then
    echo -e "${GREEN}✓${NC} S3 bucket ${BUCKET_NAME} already exists"
else
    echo -e "${YELLOW}→${NC} Creating S3 bucket: ${BUCKET_NAME}"
    aws s3 mb "s3://${BUCKET_NAME}" --region "$REGION"
    echo -e "${GREEN}✓${NC} S3 bucket created"

    # Enable versioning
    echo -e "${YELLOW}→${NC} Enabling versioning..."
    aws s3api put-bucket-versioning \
        --bucket "$BUCKET_NAME" \
        --versioning-configuration Status=Enabled \
        --region "$REGION"
    echo -e "${GREEN}✓${NC} Versioning enabled"

    # Enable encryption
    echo -e "${YELLOW}→${NC} Enabling encryption..."
    aws s3api put-bucket-encryption \
        --bucket "$BUCKET_NAME" \
        --server-side-encryption-configuration '{
            "Rules": [{
                "ApplyServerSideEncryptionByDefault": {
                    "SSEAlgorithm": "AES256"
                },
                "BucketKeyEnabled": true
            }]
        }' \
        --region "$REGION"
    echo -e "${GREEN}✓${NC} Encryption enabled"

    # Block public access
    echo -e "${YELLOW}→${NC} Blocking public access..."
    aws s3api put-public-access-block \
        --bucket "$BUCKET_NAME" \
        --public-access-block-configuration \
            "BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true" \
        --region "$REGION"
    echo -e "${GREEN}✓${NC} Public access blocked"

    # Add bucket policy for HTTPS-only
    echo -e "${YELLOW}→${NC} Enforcing HTTPS-only access..."
    aws s3api put-bucket-policy \
        --bucket "$BUCKET_NAME" \
        --policy '{
            "Version": "2012-10-17",
            "Statement": [{
                "Sid": "DenyInsecureTransport",
                "Effect": "Deny",
                "Principal": "*",
                "Action": "s3:*",
                "Resource": [
                    "arn:aws:s3:::'"$BUCKET_NAME"'",
                    "arn:aws:s3:::'"$BUCKET_NAME"'/*"
                ],
                "Condition": {
                    "Bool": {
                        "aws:SecureTransport": "false"
                    }
                }
            }]
        }' \
        --region "$REGION"
    echo -e "${GREEN}✓${NC} HTTPS-only policy applied"
fi
echo ""

# Check if DynamoDB table exists
echo -e "${YELLOW}→${NC} Checking if DynamoDB table exists..."
if aws dynamodb describe-table --table-name "$DYNAMODB_TABLE" --region "$REGION" 2>/dev/null >/dev/null; then
    echo -e "${GREEN}✓${NC} DynamoDB table ${DYNAMODB_TABLE} already exists"
else
    echo -e "${YELLOW}→${NC} Creating DynamoDB table: ${DYNAMODB_TABLE}"
    aws dynamodb create-table \
        --table-name "$DYNAMODB_TABLE" \
        --attribute-definitions AttributeName=LockID,AttributeType=S \
        --key-schema AttributeName=LockID,KeyType=HASH \
        --billing-mode PAY_PER_REQUEST \
        --region "$REGION" \
        --tags Key=Project,Value=manga-video-pipeline Key=ManagedBy,Value=terraform Key=Purpose,Value=state-locking

    echo -e "${YELLOW}→${NC} Waiting for table to be active..."
    aws dynamodb wait table-exists --table-name "$DYNAMODB_TABLE" --region "$REGION"
    echo -e "${GREEN}✓${NC} DynamoDB table created"

    # Enable point-in-time recovery
    echo -e "${YELLOW}→${NC} Enabling point-in-time recovery..."
    aws dynamodb update-continuous-backups \
        --table-name "$DYNAMODB_TABLE" \
        --point-in-time-recovery-specification PointInTimeRecoveryEnabled=true \
        --region "$REGION"
    echo -e "${GREEN}✓${NC} Point-in-time recovery enabled"
fi
echo ""

# Update backend.tf with correct bucket name
echo -e "${YELLOW}→${NC} Updating backend.tf with bucket name..."
BACKEND_FILE="backend.tf"

if [ -f "$BACKEND_FILE" ]; then
    # Create backup
    cp "$BACKEND_FILE" "${BACKEND_FILE}.backup"

    # Update bucket name
    sed -i.bak "s/bucket = \"manga-pipeline-tfstate-[0-9]*\"/bucket = \"${BUCKET_NAME}\"/" "$BACKEND_FILE"
    rm "${BACKEND_FILE}.bak"

    echo -e "${GREEN}✓${NC} backend.tf updated"
else
    echo -e "${YELLOW}!${NC} backend.tf not found, skipping update"
fi
echo ""

# Display summary
echo -e "${BLUE}╔══════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║                       Setup Complete!                            ║${NC}"
echo -e "${BLUE}╚══════════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${GREEN}Backend Resources:${NC}"
echo -e "  S3 Bucket:       ${BUCKET_NAME}"
echo -e "  DynamoDB Table:  ${DYNAMODB_TABLE}"
echo -e "  Region:          ${REGION}"
echo ""
echo -e "${GREEN}Next Steps:${NC}"
echo -e "  1. Copy terraform.tfvars.example to terraform.tfvars"
echo -e "     ${YELLOW}cp terraform.tfvars.example terraform.tfvars${NC}"
echo ""
echo -e "  2. Edit terraform.tfvars with your values"
echo -e "     ${YELLOW}vim terraform.tfvars${NC}"
echo ""
echo -e "  3. Initialize Terraform"
echo -e "     ${YELLOW}terraform init${NC}"
echo ""
echo -e "  4. Review the plan"
echo -e "     ${YELLOW}terraform plan${NC}"
echo ""
echo -e "  5. Apply the configuration"
echo -e "     ${YELLOW}terraform apply${NC}"
echo ""
echo -e "${BLUE}═══════════════════════════════════════════════════════════════════${NC}"
