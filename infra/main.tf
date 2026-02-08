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
# Networking Module - VPC and Security Groups
# =============================================================================

module "networking" {
  source = "./modules/networking"

  project_name = var.project_name
  environment  = var.environment

  # Security configuration
  admin_ip          = var.admin_ip
  allowed_ip_ranges = var.allowed_ip_ranges

  # Feature flags
  enable_ssh_access    = var.enable_ssh_access
  enable_http_redirect = true

  # Additional tags
  tags = var.additional_tags
}

# =============================================================================
# Compute Module - Lambda Functions and EC2 Instances
# =============================================================================

module "compute" {
  source = "./modules/compute"

  project_name = var.project_name
  environment  = var.environment

  # IAM role ARNs (from security module)
  lambda_role_arns = module.security.lambda_role_arns

  # EC2 instance profiles (from security module)
  ec2_instance_profile_names = module.security.ec2_instance_profile_names

  # Storage resources (from storage module)
  s3_assets_bucket_name               = module.storage.s3_assets_bucket_id
  s3_assets_bucket_arn                = module.storage.s3_assets_bucket_arn
  dynamodb_jobs_table_name            = module.storage.dynamodb_jobs_table_name
  dynamodb_processed_manga_table_name = module.storage.dynamodb_processed_manga_table_name
  dynamodb_settings_table_name        = module.storage.dynamodb_settings_table_name

  # Networking resources (from networking module)
  renderer_security_group_id  = module.networking.renderer_security_group_id
  dashboard_security_group_id = module.networking.dashboard_security_group_id
  dashboard_subnet_id         = module.networking.primary_subnet_id
  renderer_subnet_ids         = module.networking.selected_subnet_ids

  # Secrets Manager secret names
  deepinfra_api_key_secret_name   = var.deepinfra_api_key_secret_name
  mangadex_secret_name            = var.mangadex_secret_name
  youtube_credentials_secret_name = var.youtube_credentials_secret_name
  admin_credentials_secret_name   = var.admin_credentials_secret_name
  jwt_secret_name                 = var.jwt_secret_name

  # Lambda deployment configuration
  lambda_deployment_bucket = var.lambda_deployment_bucket
  lambda_deployment_prefix = var.lambda_deployment_prefix
  lambda_package_version   = var.lambda_package_version

  # Lambda runtime configuration
  lambda_runtime      = var.lambda_runtime
  lambda_architecture = "arm64" # Cost savings (~20% cheaper)

  # EC2 Spot renderer configuration
  spot_instance_type         = var.spot_instance_type
  spot_max_price             = var.spot_max_price
  spot_interruption_behavior = var.spot_interruption_behavior
  enable_detailed_monitoring = var.enable_detailed_monitoring

  # EC2 dashboard configuration
  dashboard_instance_type     = var.dashboard_instance_type
  dashboard_enable_public_ip  = var.dashboard_enable_public_ip
  dashboard_enable_elastic_ip = var.dashboard_enable_elastic_ip
  dashboard_domain            = var.dashboard_domain

  # Step Functions integration
  step_functions_role_arn = module.security.step_functions_role_arn
  enable_xray_tracing     = var.enable_xray_tracing

  # CloudWatch Logs configuration
  log_retention_days = var.log_retention_days
  log_level          = var.log_level

  # Reserved concurrency
  reserved_concurrency = var.lambda_reserved_concurrency

  # Additional tags
  tags = var.additional_tags
}

# =============================================================================
# Scheduling Module - EventBridge Rules
# =============================================================================

module "scheduling" {
  source = "./modules/scheduling"

  # Step Functions state machine to trigger
  state_machine_arn = module.compute.state_machine_arn

  # Environment configuration
  environment = var.environment

  # Schedule configuration (default: midnight Vietnam time)
  schedule_expression = var.pipeline_schedule_expression
  enabled             = var.pipeline_schedule_enabled

  # Additional tags
  tags = var.additional_tags
}

# =============================================================================
# Additional modules can be added here:
# - Secrets Manager secrets (if not created manually)
# - CloudWatch alarms
# - SNS topics for notifications
# =============================================================================
