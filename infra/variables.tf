# =============================================================================
# General Variables
# =============================================================================

variable "project_name" {
  description = "Project name used for resource naming and tagging"
  type        = string
  default     = "manga-video-pipeline"

  validation {
    condition     = can(regex("^[a-z0-9-]+$", var.project_name))
    error_message = "Project name must contain only lowercase letters, numbers, and hyphens."
  }
}

variable "environment" {
  description = "Environment name (dev, staging, prod)"
  type        = string
  default     = "prod"

  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "Environment must be one of: dev, staging, prod."
  }
}

variable "region" {
  description = "AWS region for primary resources"
  type        = string
  default     = "ap-southeast-1"

  validation {
    condition     = can(regex("^[a-z]{2}-[a-z]+-[0-9]{1}$", var.region))
    error_message = "Region must be a valid AWS region format (e.g., ap-southeast-1)."
  }
}

# =============================================================================
# Network & Security Variables
# =============================================================================

variable "admin_ip" {
  description = "Admin IP address or CIDR block for SSH/dashboard access (e.g., 203.0.113.0/32)"
  type        = string

  validation {
    condition     = can(cidrhost(var.admin_ip, 0))
    error_message = "Admin IP must be a valid CIDR block (e.g., 203.0.113.0/32 or 203.0.113.0/24)."
  }
}

variable "allowed_ip_ranges" {
  description = "List of IP CIDR blocks allowed to access the dashboard (in addition to admin_ip)"
  type        = list(string)
  default     = []

  validation {
    condition     = alltrue([for cidr in var.allowed_ip_ranges : can(cidrhost(cidr, 0))])
    error_message = "All allowed IP ranges must be valid CIDR blocks."
  }
}

# =============================================================================
# Monitoring & Alerting Variables
# =============================================================================

variable "budget_alert_email" {
  description = "Email address for AWS budget alerts and CloudWatch alarms"
  type        = string

  validation {
    condition     = can(regex("^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}$", var.budget_alert_email))
    error_message = "Budget alert email must be a valid email address."
  }
}

variable "monthly_budget_limit" {
  description = "Monthly budget limit in USD for cost alerts"
  type        = number
  default     = 100

  validation {
    condition     = var.monthly_budget_limit > 0
    error_message = "Monthly budget limit must be greater than 0."
  }
}

variable "enable_detailed_monitoring" {
  description = "Enable detailed CloudWatch monitoring for EC2 instances (additional cost)"
  type        = bool
  default     = false
}

# =============================================================================
# DynamoDB Variables
# =============================================================================

variable "dynamodb_billing_mode" {
  description = "DynamoDB billing mode (PROVISIONED or PAY_PER_REQUEST)"
  type        = string
  default     = "PAY_PER_REQUEST"

  validation {
    condition     = contains(["PROVISIONED", "PAY_PER_REQUEST"], var.dynamodb_billing_mode)
    error_message = "Billing mode must be PROVISIONED or PAY_PER_REQUEST."
  }
}

variable "dynamodb_point_in_time_recovery" {
  description = "Enable point-in-time recovery for DynamoDB tables"
  type        = bool
  default     = true
}

# =============================================================================
# S3 Variables
# =============================================================================

variable "s3_lifecycle_days" {
  description = "Number of days before transitioning S3 objects to cheaper storage classes"
  type = object({
    standard_ia  = number
    glacier      = number
    deep_archive = number
  })
  default = {
    standard_ia  = 30  # Move to Standard-IA after 30 days
    glacier      = 90  # Move to Glacier after 90 days
    deep_archive = 365 # Move to Deep Archive after 1 year
  }
}

variable "s3_enable_versioning" {
  description = "Enable versioning for S3 buckets"
  type        = bool
  default     = true
}

# =============================================================================
# Lambda Variables
# =============================================================================

variable "lambda_runtime" {
  description = "Python runtime version for Lambda functions"
  type        = string
  default     = "python3.12"

  validation {
    condition     = can(regex("^python3\\.(9|10|11|12)$", var.lambda_runtime))
    error_message = "Lambda runtime must be python3.9, python3.10, python3.11, or python3.12."
  }
}

variable "lambda_memory_size" {
  description = "Memory allocation for Lambda functions (MB)"
  type = object({
    manga_fetcher    = number
    script_generator = number
    tts_processor    = number
  })
  default = {
    manga_fetcher    = 512
    script_generator = 1024
    tts_processor    = 512
  }
}

variable "lambda_timeout" {
  description = "Timeout for Lambda functions (seconds)"
  type = object({
    manga_fetcher    = number
    script_generator = number
    tts_processor    = number
  })
  default = {
    manga_fetcher    = 300 # 5 minutes
    script_generator = 600 # 10 minutes
    tts_processor    = 300 # 5 minutes
  }
}

variable "lambda_reserved_concurrency" {
  description = "Reserved concurrent executions for Lambda functions (-1 = unreserved)"
  type = object({
    manga_fetcher    = number
    script_generator = number
    tts_processor    = number
  })
  default = {
    manga_fetcher    = -1
    script_generator = 5 # Limit to 5 concurrent LLM calls
    tts_processor    = -1
  }
}

# =============================================================================
# EC2 Spot Instance Variables
# =============================================================================

variable "spot_instance_type" {
  description = "EC2 instance type for video rendering (Spot instances)"
  type        = string
  default     = "c5.2xlarge"
}

variable "spot_max_price" {
  description = "Maximum price for Spot instances (USD per hour, empty = on-demand price)"
  type        = string
  default     = ""
}

variable "spot_interruption_behavior" {
  description = "Behavior when Spot instance is interrupted (terminate, stop, hibernate)"
  type        = string
  default     = "terminate"

  validation {
    condition     = contains(["terminate", "stop", "hibernate"], var.spot_interruption_behavior)
    error_message = "Interruption behavior must be terminate, stop, or hibernate."
  }
}

variable "ami_name_filter" {
  description = "AMI name filter for EC2 instances (e.g., ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-amd64-server-*)"
  type        = string
  default     = "ubuntu/images/hvm-ssd-gp3/ubuntu-noble-24.04-amd64-server-*"
}

# =============================================================================
# Dashboard Variables
# =============================================================================

variable "dashboard_instance_type" {
  description = "EC2 instance type for admin dashboard"
  type        = string
  default     = "t3.micro"
}

variable "dashboard_enable_public_ip" {
  description = "Enable public IP for dashboard instance (required for nip.io)"
  type        = bool
  default     = true
}

# =============================================================================
# EventBridge Scheduler Variables
# =============================================================================

variable "daily_trigger_time" {
  description = "Daily trigger time in UTC (format: HH:MM)"
  type        = string
  default     = "17:00" # Midnight Vietnam time (UTC+7)

  validation {
    condition     = can(regex("^([0-1][0-9]|2[0-3]):[0-5][0-9]$", var.daily_trigger_time))
    error_message = "Daily trigger time must be in HH:MM format (24-hour)."
  }
}

variable "enable_daily_trigger" {
  description = "Enable the daily EventBridge trigger for the pipeline"
  type        = bool
  default     = true
}

# =============================================================================
# API & External Service Variables
# =============================================================================

variable "deepinfra_api_key_secret_name" {
  description = "Secrets Manager secret name for DeepInfra API key"
  type        = string
  default     = "manga-pipeline/deepinfra-api-key"
}

variable "youtube_credentials_secret_name" {
  description = "Secrets Manager secret name for YouTube OAuth credentials"
  type        = string
  default     = "manga-pipeline/youtube-credentials"
}

variable "mangadex_secret_name" {
  description = "Secrets Manager secret name for MangaDex credentials (if needed)"
  type        = string
  default     = "manga-pipeline/mangadex-credentials"
}

variable "admin_credentials_secret_name" {
  description = "Secrets Manager secret name for dashboard admin credentials"
  type        = string
  default     = "manga-pipeline/admin-credentials"
}

variable "jwt_secret_name" {
  description = "Secrets Manager secret name for dashboard JWT signing key"
  type        = string
  default     = "manga-pipeline/jwt-secret"
}

# =============================================================================
# Pipeline Configuration Variables
# =============================================================================

variable "daily_quota" {
  description = "Default daily video quota (can be changed via dashboard)"
  type        = number
  default     = 10

  validation {
    condition     = var.daily_quota >= 1 && var.daily_quota <= 100
    error_message = "Daily quota must be between 1 and 100."
  }
}

variable "tts_voice_id" {
  description = "Default Edge TTS voice ID for Vietnamese narration"
  type        = string
  default     = "vi-VN-HoaiMyNeural"

  validation {
    condition     = contains(["vi-VN-HoaiMyNeural", "vi-VN-NamMinhNeural"], var.tts_voice_id)
    error_message = "TTS voice must be vi-VN-HoaiMyNeural or vi-VN-NamMinhNeural."
  }
}

variable "script_style" {
  description = "Default script generation style"
  type        = string
  default     = "chapter_walkthrough"

  validation {
    condition     = contains(["detailed_review", "summary", "chapter_walkthrough"], var.script_style)
    error_message = "Script style must be detailed_review, summary, or chapter_walkthrough."
  }
}

# =============================================================================
# Feature Flags
# =============================================================================

variable "enable_spot_interruption_handling" {
  description = "Enable EventBridge rule for Spot instance interruption warnings"
  type        = bool
  default     = true
}

variable "enable_cleanup_lambda" {
  description = "Enable Lambda function for cleaning up old S3 objects and failed jobs"
  type        = bool
  default     = true
}

variable "enable_cost_allocation_tags" {
  description = "Enable additional cost allocation tags for detailed billing"
  type        = bool
  default     = true
}

# =============================================================================
# Tags
# =============================================================================

variable "additional_tags" {
  description = "Additional tags to apply to all resources"
  type        = map(string)
  default     = {}
}
