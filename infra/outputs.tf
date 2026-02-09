# =============================================================================
# S3 Outputs
# =============================================================================

output "s3_bucket_name" {
  description = "Name of the S3 bucket for temporary assets"
  value       = module.storage.s3_assets_bucket_id
}

output "s3_bucket_arn" {
  description = "ARN of the S3 bucket for temporary assets"
  value       = module.storage.s3_assets_bucket_arn
}

output "s3_bucket_regional_domain_name" {
  description = "Regional domain name of the S3 bucket"
  value       = module.storage.s3_assets_bucket_regional_domain_name
}

# =============================================================================
# DynamoDB Outputs
# =============================================================================

output "dynamodb_table_name" {
  description = "Name of the DynamoDB table for job tracking"
  value       = module.storage.dynamodb_jobs_table_name
}

output "dynamodb_table_arn" {
  description = "ARN of the DynamoDB table for job tracking"
  value       = module.storage.dynamodb_jobs_table_arn
}

output "dynamodb_table_names" {
  description = "Map of all DynamoDB table names"
  value       = module.storage.dynamodb_table_names
}

# =============================================================================
# Storage Module Summary
# =============================================================================

output "storage_summary" {
  description = "Summary of storage resources"
  value       = module.storage.storage_summary
}

# =============================================================================
# IAM Role Outputs
# =============================================================================

output "lambda_role_arns" {
  description = "Map of Lambda execution role ARNs"
  value       = module.security.lambda_role_arns
}

output "lambda_role_names" {
  description = "Map of Lambda execution role names"
  value       = module.security.lambda_role_names
}

output "ec2_instance_profile_arns" {
  description = "Map of EC2 instance profile ARNs"
  value       = module.security.ec2_instance_profile_arns
}

output "ec2_instance_profile_names" {
  description = "Map of EC2 instance profile names"
  value       = module.security.ec2_instance_profile_names
}

output "step_functions_role_arn" {
  description = "ARN of the Step Functions execution role"
  value       = module.security.step_functions_role_arn
}

output "eventbridge_role_arn" {
  description = "ARN of the EventBridge execution role"
  value       = module.security.eventbridge_role_arn
}

output "security_summary" {
  description = "Summary of IAM roles created"
  value       = module.security.security_summary
}

# =============================================================================
# Lambda Function Outputs
# =============================================================================

output "lambda_function_arns" {
  description = "Map of Lambda function ARNs"
  value       = module.compute.lambda_function_arns
}

output "lambda_function_names" {
  description = "Map of Lambda function names"
  value       = module.compute.lambda_function_names
}

output "lambda_invoke_arns" {
  description = "Map of Lambda invoke ARNs (for Step Functions)"
  value       = module.compute.lambda_invoke_arns
}

output "log_group_names" {
  description = "Map of CloudWatch log group names"
  value       = module.compute.log_group_names
}

output "compute_summary" {
  description = "Summary of compute resources created"
  value       = module.compute.compute_summary
}

# =============================================================================
# Networking Outputs
# =============================================================================

output "vpc_id" {
  description = "ID of the VPC"
  value       = module.networking.vpc_id
}

output "security_group_ids" {
  description = "Map of security group IDs"
  value       = module.networking.security_group_ids
}

output "networking_summary" {
  description = "Summary of networking resources"
  value       = module.networking.networking_summary
}

# =============================================================================
# EC2 Outputs
# =============================================================================

output "renderer_launch_template_id" {
  description = "ID of the renderer launch template"
  value       = module.compute.renderer_launch_template_id
}

output "dashboard_instance_id" {
  description = "ID of the dashboard EC2 instance"
  value       = module.compute.dashboard_instance_id
}

output "dashboard_public_ip" {
  description = "Public IP of the dashboard instance"
  value       = module.compute.dashboard_public_ip
}

output "dashboard_url" {
  description = "HTTPS URL to access the dashboard"
  value       = module.compute.dashboard_url
}

output "dashboard_nip_io_url" {
  description = "nip.io URL for the dashboard"
  value       = module.compute.dashboard_nip_io_url
}

# =============================================================================
# Step Functions Outputs
# =============================================================================

output "state_machine_arn" {
  description = "ARN of the Step Functions state machine"
  value       = module.compute.state_machine_arn
}

output "state_machine_name" {
  description = "Name of the Step Functions state machine"
  value       = module.compute.state_machine_name
}

output "step_functions_log_group_name" {
  description = "Name of the Step Functions CloudWatch log group"
  value       = module.compute.step_functions_log_group_name
}

# =============================================================================
# EventBridge Scheduling Outputs
# =============================================================================

output "eventbridge_rule_name" {
  description = "Name of the EventBridge daily trigger rule"
  value       = module.scheduling.eventbridge_rule_name
}

output "eventbridge_rule_arn" {
  description = "ARN of the EventBridge daily trigger rule"
  value       = module.scheduling.eventbridge_rule_arn
}

output "schedule_expression" {
  description = "Cron expression for the pipeline schedule"
  value       = module.scheduling.schedule_expression
}

output "schedule_enabled" {
  description = "Whether the EventBridge schedule is enabled"
  value       = module.scheduling.enabled
}

# =============================================================================
# Secrets Manager Outputs
# =============================================================================

output "secret_arns" {
  description = "Map of Secrets Manager secret ARNs"
  value       = module.security.secret_arns
}

output "deepinfra_secret_arn" {
  description = "ARN of the DeepInfra API key secret"
  value       = module.security.deepinfra_secret_arn
}

output "youtube_oauth_secret_arn" {
  description = "ARN of the YouTube OAuth secret"
  value       = module.security.youtube_oauth_secret_arn
}

output "admin_credentials_secret_arn" {
  description = "ARN of the admin credentials secret"
  value       = module.security.admin_credentials_secret_arn
}

# =============================================================================
# Monitoring Outputs
# =============================================================================

output "sns_topic_arn" {
  description = "ARN of the SNS topic for alarm notifications"
  value       = module.monitoring.sns_topic_arn
}

output "monitoring_summary" {
  description = "Summary of monitoring resources"
  value       = module.monitoring.monitoring_summary
}

# =============================================================================
# Pipeline Summary
# =============================================================================

output "pipeline_summary" {
  description = "Summary of the complete manga video pipeline"
  value = {
    state_machine = {
      name = module.compute.state_machine_name
      arn  = module.compute.state_machine_arn
    }
    schedule = {
      rule_name  = module.scheduling.eventbridge_rule_name
      expression = module.scheduling.schedule_expression
      enabled    = module.scheduling.enabled
    }
    dashboard = {
      url        = module.compute.dashboard_url
      nip_io_url = module.compute.dashboard_nip_io_url
    }
    monitoring = {
      sns_topic      = module.monitoring.sns_topic_arn
      alarms_created = module.monitoring.monitoring_summary.alarms
    }
    secrets = module.security.secret_arns
  }
}
