# Output values for the scheduling module

output "eventbridge_rule_name" {
  description = "Name of the EventBridge rule"
  value       = aws_cloudwatch_event_rule.daily_pipeline_trigger.name
}

output "eventbridge_rule_arn" {
  description = "ARN of the EventBridge rule"
  value       = aws_cloudwatch_event_rule.daily_pipeline_trigger.arn
}

output "eventbridge_rule_id" {
  description = "ID of the EventBridge rule"
  value       = aws_cloudwatch_event_rule.daily_pipeline_trigger.id
}

output "eventbridge_role_name" {
  description = "Name of the IAM role used by EventBridge"
  value       = aws_iam_role.eventbridge_sfn.name
}

output "eventbridge_role_arn" {
  description = "ARN of the IAM role used by EventBridge"
  value       = aws_iam_role.eventbridge_sfn.arn
}

output "schedule_expression" {
  description = "Cron expression for the EventBridge rule"
  value       = aws_cloudwatch_event_rule.daily_pipeline_trigger.schedule_expression
}

output "schedule_description" {
  description = "Human-readable schedule description"
  value       = "Daily at midnight Vietnam time (00:00 UTC+7 / 17:00 UTC)"
}

output "enabled" {
  description = "Whether the EventBridge rule is enabled"
  value       = aws_cloudwatch_event_rule.daily_pipeline_trigger.state == "ENABLED"
}

output "target_state_machine_arn" {
  description = "ARN of the Step Functions state machine being triggered"
  value       = var.state_machine_arn
}
