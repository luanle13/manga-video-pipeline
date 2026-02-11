# Terraform S3 Backend Configuration
#
# This backend stores Terraform state in S3 with DynamoDB locking for state consistency.
#
# Initial Setup (run once):
#   1. Create S3 bucket: aws s3 mb s3://manga-pipeline-tfstate-{account_id} --region ap-southeast-1
#   2. Enable versioning: aws s3api put-bucket-versioning --bucket manga-pipeline-tfstate-{account_id} --versioning-configuration Status=Enabled
#   3. Create DynamoDB table: aws dynamodb create-table --table-name manga-pipeline-tfstate-lock --attribute-definitions AttributeName=LockID,AttributeType=S --key-schema AttributeName=LockID,KeyType=HASH --billing-mode PAY_PER_REQUEST --region ap-southeast-1
#   4. Run: terraform init
#
# Note: Replace {account_id} with your AWS account ID
# You can get it with: aws sts get-caller-identity --query Account --output text

terraform {
  backend "s3" {
    # S3 bucket for state storage
    # Format: manga-pipeline-tfstate-{account_id}
    # Example: manga-pipeline-tfstate-123456789012
    bucket = "manga-pipeline-tfstate-442075129398"

    # State file path within the bucket
    key = "prod/terraform.tfstate"

    # AWS region for the backend resources
    region = "ap-southeast-1"

    # DynamoDB table for state locking
    dynamodb_table = "manga-pipeline-tfstate-lock"

    # Enable encryption at rest
    encrypt = true

    # Workspace key prefix (for multi-environment setups)
    workspace_key_prefix = "workspaces"

    # Server-side encryption configuration
    # Uses AWS managed keys (SSE-S3)
    # For KMS encryption, uncomment and specify kms_key_id
    # kms_key_id = "arn:aws:kms:ap-southeast-1:123456789012:key/12345678-1234-1234-1234-123456789012"
  }
}

# Note: The backend block does not support variable interpolation
# You must manually update the bucket name with your AWS account ID
# Or use backend configuration file (backend.hcl) with -backend-config flag
