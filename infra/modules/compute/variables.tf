# =============================================================================
# Compute Module - Input Variables
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
# IAM Role ARNs (from security module)
# =============================================================================

variable "lambda_role_arns" {
  description = "Map of Lambda execution role ARNs from security module"
  type = object({
    manga_fetcher    = string
    script_generator = string
    tts_processor    = string
    quota_checker    = string
    cleanup          = string
  })
}

# =============================================================================
# Storage Resources (from storage module)
# =============================================================================

variable "s3_assets_bucket_name" {
  description = "Name of the S3 assets bucket"
  type        = string
}

variable "s3_assets_bucket_arn" {
  description = "ARN of the S3 assets bucket"
  type        = string
}

variable "dynamodb_jobs_table_name" {
  description = "Name of the manga_jobs DynamoDB table"
  type        = string
}

variable "dynamodb_processed_manga_table_name" {
  description = "Name of the processed_manga DynamoDB table"
  type        = string
}

variable "dynamodb_settings_table_name" {
  description = "Name of the settings DynamoDB table"
  type        = string
}

# =============================================================================
# Secrets Manager Secret Names
# =============================================================================

variable "deepinfra_api_key_secret_name" {
  description = "Name of the DeepInfra API key secret in Secrets Manager"
  type        = string
  default     = "manga-pipeline/deepinfra-api-key"
}

variable "mangadex_secret_name" {
  description = "Name of the MangaDex credentials secret (if needed)"
  type        = string
  default     = "manga-pipeline/mangadex-credentials"
}

# =============================================================================
# Lambda Deployment Configuration
# =============================================================================

variable "lambda_deployment_bucket" {
  description = "S3 bucket containing Lambda deployment packages"
  type        = string
}

variable "lambda_deployment_prefix" {
  description = "S3 key prefix for Lambda deployment packages"
  type        = string
  default     = "lambda-packages"
}

variable "lambda_package_version" {
  description = "Version/hash of the Lambda deployment package"
  type        = string
  default     = "latest"
}

# =============================================================================
# Lambda Runtime Configuration
# =============================================================================

variable "lambda_runtime" {
  description = "Python runtime version for Lambda functions"
  type        = string
  default     = "python3.12"

  validation {
    condition     = can(regex("^python3\\.(9|10|11|12|13)$", var.lambda_runtime))
    error_message = "Lambda runtime must be python3.9, python3.10, python3.11, python3.12, or python3.13."
  }
}

variable "lambda_architecture" {
  description = "Lambda function architecture (arm64 for cost savings)"
  type        = string
  default     = "arm64"

  validation {
    condition     = contains(["arm64", "x86_64"], var.lambda_architecture)
    error_message = "Lambda architecture must be arm64 or x86_64."
  }
}

# =============================================================================
# CloudWatch Logs Configuration
# =============================================================================

variable "log_retention_days" {
  description = "CloudWatch Logs retention period in days"
  type        = number
  default     = 30

  validation {
    condition     = contains([1, 3, 5, 7, 14, 30, 60, 90, 120, 150, 180, 365, 400, 545, 731, 1096, 1827, 2192, 2557, 2922, 3288, 3653], var.log_retention_days)
    error_message = "Log retention must be a valid CloudWatch Logs retention value."
  }
}

variable "log_level" {
  description = "Application log level"
  type        = string
  default     = "INFO"

  validation {
    condition     = contains(["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"], var.log_level)
    error_message = "Log level must be DEBUG, INFO, WARNING, ERROR, or CRITICAL."
  }
}

# =============================================================================
# Reserved Concurrency
# =============================================================================

variable "reserved_concurrency" {
  description = "Reserved concurrent executions for Lambda functions (-1 = unreserved)"
  type = object({
    manga_fetcher    = number
    script_generator = number
    tts_processor    = number
    quota_checker    = number
    cleanup          = number
  })
  default = {
    manga_fetcher    = -1
    script_generator = 5 # Limit concurrent LLM API calls
    tts_processor    = -1
    quota_checker    = -1
    cleanup          = -1
  }
}

# =============================================================================
# Additional Tags
# =============================================================================

variable "tags" {
  description = "Additional tags to apply to all resources"
  type        = map(string)
  default     = {}
}
