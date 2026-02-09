# =============================================================================
# Monitoring Module - Input Variables
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
# SNS Topic for Alarm Notifications
# =============================================================================

variable "alarm_email" {
  description = "Email address to receive CloudWatch alarm notifications"
  type        = string

  validation {
    condition     = can(regex("^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}$", var.alarm_email))
    error_message = "Alarm email must be a valid email address."
  }
}

variable "create_sns_topic" {
  description = "Create SNS topic for alarms (set false if using existing topic)"
  type        = bool
  default     = true
}

variable "sns_topic_arn" {
  description = "Existing SNS topic ARN for alarms (required if create_sns_topic = false)"
  type        = string
  default     = ""
}

# =============================================================================
# Lambda Monitoring Configuration
# =============================================================================

variable "lambda_error_threshold" {
  description = "Number of Lambda errors per hour to trigger alarm"
  type        = number
  default     = 3
}

variable "lambda_duration_thresholds" {
  description = "Lambda duration thresholds in milliseconds (warning when exceeded)"
  type = object({
    manga_fetcher    = number
    script_generator = number
    tts_processor    = number
    quota_checker    = number
    cleanup          = number
  })
  default = {
    manga_fetcher    = 300000 # 5 minutes
    script_generator = 540000 # 9 minutes (near Lambda timeout)
    tts_processor    = 540000 # 9 minutes
    quota_checker    = 10000  # 10 seconds
    cleanup          = 120000 # 2 minutes
  }
}

# =============================================================================
# Step Functions Monitoring Configuration
# =============================================================================

variable "state_machine_name" {
  description = "Name of the Step Functions state machine to monitor"
  type        = string
}

variable "step_functions_failure_threshold" {
  description = "Number of Step Functions execution failures to trigger alarm"
  type        = number
  default     = 1
}

# =============================================================================
# EC2 Spot Monitoring Configuration
# =============================================================================

variable "enable_spot_interruption_alarm" {
  description = "Enable alarm for EC2 Spot instance interruptions"
  type        = bool
  default     = true
}

variable "spot_interruption_threshold" {
  description = "Number of Spot interruptions per day to trigger alarm"
  type        = number
  default     = 2
}

# =============================================================================
# Dashboard Configuration
# =============================================================================

variable "create_dashboard" {
  description = "Create CloudWatch dashboard (optional, for visualization)"
  type        = bool
  default     = false
}

# =============================================================================
# Alarm Actions Configuration
# =============================================================================

variable "enable_alarm_actions" {
  description = "Enable alarm actions (SNS notifications)"
  type        = bool
  default     = true
}

variable "treat_missing_data" {
  description = "How to treat missing data in alarms"
  type        = string
  default     = "notBreaching"

  validation {
    condition     = contains(["breaching", "notBreaching", "ignore", "missing"], var.treat_missing_data)
    error_message = "treat_missing_data must be breaching, notBreaching, ignore, or missing."
  }
}

# =============================================================================
# AWS Budget Configuration
# =============================================================================

variable "create_budget" {
  description = "Create AWS Budget for cost monitoring"
  type        = bool
  default     = true
}

variable "monthly_budget_limit" {
  description = "Monthly budget limit in USD"
  type        = number
  default     = 120

  validation {
    condition     = var.monthly_budget_limit > 0
    error_message = "Monthly budget limit must be greater than 0."
  }
}

variable "budget_alert_thresholds" {
  description = "Budget alert thresholds as percentages"
  type        = list(number)
  default     = [65, 100, 120]

  validation {
    condition     = length(var.budget_alert_thresholds) > 0
    error_message = "At least one budget alert threshold is required."
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
