# =============================================================================
# Manga Video Pipeline - Main Infrastructure Configuration
# =============================================================================

# =============================================================================
# Storage Module - S3 and DynamoDB
# =============================================================================

module "storage" {
  source = "./modules/storage"

  project_name = var.project_name
  environment  = var.environment

  # S3 lifecycle configuration
  assets_lifecycle_days = 7 # Delete temp files after 7 days

  # DynamoDB configuration
  enable_point_in_time_recovery = var.dynamodb_point_in_time_recovery

  # Additional tags
  tags = var.additional_tags
}

# =============================================================================
# Additional modules will be added here:
# - Lambda functions (fetcher, generator, tts, quota, cleanup)
# - Step Functions state machine
# - EC2 launch templates (spot renderer, dashboard)
# - EventBridge rules
# - Secrets Manager secrets
# - CloudWatch log groups and alarms
# - SNS topics for notifications
# - IAM roles and policies
# =============================================================================
