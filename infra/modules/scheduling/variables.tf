# Input variables for the scheduling module

variable "state_machine_arn" {
  description = "ARN of the Step Functions state machine to trigger"
  type        = string

  validation {
    condition     = can(regex("^arn:aws:states:[a-z0-9-]+:[0-9]{12}:stateMachine:.+$", var.state_machine_arn))
    error_message = "state_machine_arn must be a valid Step Functions state machine ARN"
  }
}

variable "environment" {
  description = "Environment name (dev, staging, prod)"
  type        = string
  default     = "prod"

  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "environment must be one of: dev, staging, prod"
  }
}

variable "enabled" {
  description = "Whether the EventBridge rule is enabled. Set to false to disable automatic triggering."
  type        = bool
  default     = true
}

variable "schedule_expression" {
  description = "Cron expression for the EventBridge rule. Default is midnight Vietnam time (00:00 UTC+7)."
  type        = string
  default     = "cron(0 17 * * ? *)"

  validation {
    condition     = can(regex("^(rate|cron)\\(.+\\)$", var.schedule_expression))
    error_message = "schedule_expression must be a valid EventBridge rate or cron expression"
  }
}

variable "tags" {
  description = "Additional tags to apply to all resources"
  type        = map(string)
  default     = {}
}
