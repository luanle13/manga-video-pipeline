# =============================================================================
# Security Module - Input Variables
# =============================================================================

variable "project_name" {
  description = "Project name for resource naming"
  type        = string
}

variable "environment" {
  description = "Environment name (dev, staging, prod)"
  type        = string
}

# =============================================================================
# Storage Resource ARNs (from storage module)
# =============================================================================

variable "s3_assets_bucket_arn" {
  description = "ARN of the S3 assets bucket"
  type        = string
}

variable "s3_assets_bucket_name" {
  description = "Name of the S3 assets bucket"
  type        = string
}

variable "dynamodb_jobs_table_arn" {
  description = "ARN of the manga_jobs DynamoDB table"
  type        = string
}

variable "dynamodb_jobs_table_name" {
  description = "Name of the manga_jobs DynamoDB table"
  type        = string
}

variable "dynamodb_processed_manga_table_arn" {
  description = "ARN of the processed_manga DynamoDB table"
  type        = string
}

variable "dynamodb_processed_manga_table_name" {
  description = "Name of the processed_manga DynamoDB table"
  type        = string
}

variable "dynamodb_settings_table_arn" {
  description = "ARN of the settings DynamoDB table"
  type        = string
}

variable "dynamodb_settings_table_name" {
  description = "Name of the settings DynamoDB table"
  type        = string
}

variable "dynamodb_jobs_gsi_name" {
  description = "Name of the status-created GSI on manga_jobs table"
  type        = string
  default     = "status-created-index"
}

# =============================================================================
# Secrets Manager Secret Names
# =============================================================================

variable "deepinfra_api_key_secret_name" {
  description = "Name of the DeepInfra API key secret in Secrets Manager"
  type        = string
  default     = "manga-pipeline/deepinfra-api-key"
}

variable "youtube_credentials_secret_name" {
  description = "Name of the YouTube credentials secret in Secrets Manager"
  type        = string
  default     = "manga-pipeline/youtube-credentials"
}

variable "admin_credentials_secret_name" {
  description = "Name of the admin credentials secret in Secrets Manager"
  type        = string
  default     = "manga-pipeline/admin-credentials"
}

variable "mangadex_secret_name" {
  description = "Name of the MangaDex credentials secret (if needed)"
  type        = string
  default     = "manga-pipeline/mangadex-credentials"
}

# =============================================================================
# State Machine ARN (for dashboard retry capability)
# =============================================================================

variable "state_machine_arn" {
  description = "ARN of the Step Functions state machine (optional, for dashboard)"
  type        = string
  default     = ""
}

# =============================================================================
# Lambda Function Names (for Step Functions invoke permissions)
# =============================================================================

variable "lambda_function_names" {
  description = "Map of Lambda function names"
  type = object({
    manga_fetcher    = string
    script_generator = string
    tts_processor    = string
    quota_checker    = string
    cleanup          = string
  })
  default = {
    manga_fetcher    = "manga-video-pipeline-manga-fetcher"
    script_generator = "manga-video-pipeline-script-generator"
    tts_processor    = "manga-video-pipeline-tts-processor"
    quota_checker    = "manga-video-pipeline-quota-checker"
    cleanup          = "manga-video-pipeline-cleanup"
  }
}

# =============================================================================
# EC2 Configuration
# =============================================================================

variable "ec2_spot_tag_key" {
  description = "Tag key for EC2 Spot instances (used in conditions)"
  type        = string
  default     = "ManagedBy"
}

variable "ec2_spot_tag_value" {
  description = "Tag value for EC2 Spot instances (used in conditions)"
  type        = string
  default     = "manga-pipeline"
}

# =============================================================================
# Additional Tags
# =============================================================================

variable "tags" {
  description = "Additional tags to apply to all resources"
  type        = map(string)
  default     = {}
}
