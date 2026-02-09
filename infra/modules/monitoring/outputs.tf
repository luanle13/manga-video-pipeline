# =============================================================================
# Monitoring Module - Outputs
# =============================================================================

# =============================================================================
# SNS Topic Outputs
# =============================================================================

output "sns_topic_arn" {
  description = "ARN of the SNS topic for alarm notifications"
  value       = var.create_sns_topic ? aws_sns_topic.alarms[0].arn : var.sns_topic_arn
}

output "sns_topic_name" {
  description = "Name of the SNS topic for alarm notifications"
  value       = var.create_sns_topic ? aws_sns_topic.alarms[0].name : null
}

# =============================================================================
# Lambda Alarm Outputs
# =============================================================================

output "lambda_error_alarm_arns" {
  description = "Map of Lambda error alarm ARNs"
  value = {
    for k, v in aws_cloudwatch_metric_alarm.lambda_errors : k => v.arn
  }
}

output "lambda_duration_alarm_arns" {
  description = "Map of Lambda duration alarm ARNs"
  value = {
    for k, v in aws_cloudwatch_metric_alarm.lambda_duration : k => v.arn
  }
}

output "lambda_throttle_alarm_arns" {
  description = "Map of Lambda throttle alarm ARNs"
  value = {
    for k, v in aws_cloudwatch_metric_alarm.lambda_throttles : k => v.arn
  }
}

# =============================================================================
# Step Functions Alarm Outputs
# =============================================================================

output "step_functions_failed_alarm_arn" {
  description = "ARN of the Step Functions failed execution alarm"
  value       = aws_cloudwatch_metric_alarm.step_functions_failed.arn
}

output "step_functions_timed_out_alarm_arn" {
  description = "ARN of the Step Functions timed out alarm"
  value       = aws_cloudwatch_metric_alarm.step_functions_timed_out.arn
}

output "step_functions_aborted_alarm_arn" {
  description = "ARN of the Step Functions aborted alarm"
  value       = aws_cloudwatch_metric_alarm.step_functions_aborted.arn
}

# =============================================================================
# EC2 Spot Outputs
# =============================================================================

output "spot_interruption_rule_arn" {
  description = "ARN of the EC2 Spot interruption EventBridge rule"
  value       = var.enable_spot_interruption_alarm ? aws_cloudwatch_event_rule.spot_interruption[0].arn : null
}

# =============================================================================
# Dashboard Outputs
# =============================================================================

output "dashboard_arn" {
  description = "ARN of the CloudWatch dashboard"
  value       = var.create_dashboard ? aws_cloudwatch_dashboard.pipeline[0].dashboard_arn : null
}

output "dashboard_name" {
  description = "Name of the CloudWatch dashboard"
  value       = var.create_dashboard ? aws_cloudwatch_dashboard.pipeline[0].dashboard_name : null
}

# =============================================================================
# Budget Outputs
# =============================================================================

output "monthly_budget_name" {
  description = "Name of the monthly cost budget"
  value       = var.create_budget ? aws_budgets_budget.monthly_budget[0].name : null
}

output "monthly_budget_id" {
  description = "ID of the monthly cost budget"
  value       = var.create_budget ? aws_budgets_budget.monthly_budget[0].id : null
}

output "budget_thresholds" {
  description = "Budget alert thresholds in USD"
  value = var.create_budget ? {
    for threshold in var.budget_alert_thresholds :
    "${threshold}pct" => floor(var.monthly_budget_limit * threshold / 100)
  } : null
}

# =============================================================================
# Monitoring Summary
# =============================================================================

output "monitoring_summary" {
  description = "Summary of monitoring resources created"
  value = {
    sns_topic = {
      arn     = var.create_sns_topic ? aws_sns_topic.alarms[0].arn : var.sns_topic_arn
      created = var.create_sns_topic
    }
    alarms = {
      lambda_errors     = length(aws_cloudwatch_metric_alarm.lambda_errors)
      lambda_duration   = length(aws_cloudwatch_metric_alarm.lambda_duration)
      lambda_throttles  = length(aws_cloudwatch_metric_alarm.lambda_throttles)
      step_functions    = 3 # failed, timed_out, aborted
      dynamodb_throttle = length(aws_cloudwatch_metric_alarm.dynamodb_throttle)
      spot_interruption = var.enable_spot_interruption_alarm ? 1 : 0
    }
    budgets = {
      created           = var.create_budget
      monthly_limit_usd = var.create_budget ? var.monthly_budget_limit : null
      thresholds        = var.create_budget ? var.budget_alert_thresholds : null
      budgets_count     = var.create_budget ? 3 : 0 # monthly, ec2-spot, lambda
    }
    dashboard = {
      created = var.create_dashboard
      name    = var.create_dashboard ? aws_cloudwatch_dashboard.pipeline[0].dashboard_name : null
    }
    notification_email = var.alarm_email
  }
}
