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
# Security Module - IAM Roles and Policies
# =============================================================================

module "security" {
  source = "./modules/security"

  project_name = var.project_name
  environment  = var.environment

  # Storage resource ARNs (from storage module)
  s3_assets_bucket_arn                = module.storage.s3_assets_bucket_arn
  s3_assets_bucket_name               = module.storage.s3_assets_bucket_id
  dynamodb_jobs_table_arn             = module.storage.dynamodb_jobs_table_arn
  dynamodb_jobs_table_name            = module.storage.dynamodb_jobs_table_name
  dynamodb_processed_manga_table_arn  = module.storage.dynamodb_processed_manga_table_arn
  dynamodb_processed_manga_table_name = module.storage.dynamodb_processed_manga_table_name
  dynamodb_settings_table_arn         = module.storage.dynamodb_settings_table_arn
  dynamodb_settings_table_name        = module.storage.dynamodb_settings_table_name
  dynamodb_jobs_gsi_name              = module.storage.dynamodb_jobs_gsi_name

  # Secrets Manager secret names
  deepinfra_api_key_secret_name   = var.deepinfra_api_key_secret_name
  youtube_credentials_secret_name = var.youtube_credentials_secret_name
  admin_credentials_secret_name   = var.admin_credentials_secret_name
  mangadex_secret_name            = var.mangadex_secret_name

  # Lambda function names (use defaults or override)
  lambda_function_names = {
    manga_fetcher    = "${var.project_name}-manga-fetcher"
    script_generator = "${var.project_name}-script-generator"
    tts_processor    = "${var.project_name}-tts-processor"
    quota_checker    = "${var.project_name}-quota-checker"
    cleanup          = "${var.project_name}-cleanup"
  }

  # EC2 Spot instance tagging for conditions
  ec2_spot_tag_key   = "ManagedBy"
  ec2_spot_tag_value = var.project_name

  # State machine ARN (will be set after state machine is created)
  state_machine_arn = ""

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
# =============================================================================
