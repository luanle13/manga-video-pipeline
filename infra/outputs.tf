# =============================================================================
# S3 Outputs
# =============================================================================

output "s3_bucket_name" {
  description = "Name of the S3 bucket for video storage"
  value       = try(aws_s3_bucket.videos.id, "not-created")
}

output "s3_deployment_bucket_name" {
  description = "Name of the S3 bucket for deployment packages"
  value       = try(aws_s3_bucket.deployments.id, "not-created")
}

output "s3_bucket_arn" {
  description = "ARN of the S3 bucket for video storage"
  value       = try(aws_s3_bucket.videos.arn, "not-created")
}

output "s3_bucket_regional_domain_name" {
  description = "Regional domain name of the S3 bucket"
  value       = try(aws_s3_bucket.videos.bucket_regional_domain_name, "not-created")
}

# =============================================================================
# DynamoDB Outputs
# =============================================================================

output "dynamodb_table_name" {
  description = "Name of the DynamoDB table for job tracking"
  value       = try(aws_dynamodb_table.jobs.name, "not-created")
}

output "dynamodb_table_arn" {
  description = "ARN of the DynamoDB table for job tracking"
  value       = try(aws_dynamodb_table.jobs.arn, "not-created")
}

output "dynamodb_table_names" {
  description = "Map of all DynamoDB table names"
  value = {
    jobs     = try(aws_dynamodb_table.jobs.name, "not-created")
    settings = try(aws_dynamodb_table.settings.name, "not-created")
  }
}

# =============================================================================
# Lambda Outputs
# =============================================================================

output "lambda_function_arns" {
  description = "Map of Lambda function ARNs"
  value = {
    manga_fetcher    = try(aws_lambda_function.manga_fetcher.arn, "not-created")
    script_generator = try(aws_lambda_function.script_generator.arn, "not-created")
    tts_processor    = try(aws_lambda_function.tts_processor.arn, "not-created")
    quota_checker    = try(aws_lambda_function.quota_checker.arn, "not-created")
    cleanup          = try(aws_lambda_function.cleanup.arn, "not-created")
  }
}

output "lambda_function_names" {
  description = "Map of Lambda function names"
  value = {
    manga_fetcher    = try(aws_lambda_function.manga_fetcher.function_name, "not-created")
    script_generator = try(aws_lambda_function.script_generator.function_name, "not-created")
    tts_processor    = try(aws_lambda_function.tts_processor.function_name, "not-created")
    quota_checker    = try(aws_lambda_function.quota_checker.function_name, "not-created")
    cleanup          = try(aws_lambda_function.cleanup.function_name, "not-created")
  }
}

output "lambda_role_arns" {
  description = "Map of Lambda execution role ARNs"
  value = {
    manga_fetcher    = try(aws_iam_role.manga_fetcher_lambda.arn, "not-created")
    script_generator = try(aws_iam_role.script_generator_lambda.arn, "not-created")
    tts_processor    = try(aws_iam_role.tts_processor_lambda.arn, "not-created")
    quota_checker    = try(aws_iam_role.quota_checker_lambda.arn, "not-created")
    cleanup          = try(aws_iam_role.cleanup_lambda.arn, "not-created")
  }
}

# =============================================================================
# Step Functions Outputs
# =============================================================================

output "step_function_arn" {
  description = "ARN of the Step Functions state machine"
  value       = try(aws_sfn_state_machine.manga_pipeline.arn, "not-created")
}

output "step_function_name" {
  description = "Name of the Step Functions state machine"
  value       = try(aws_sfn_state_machine.manga_pipeline.name, "not-created")
}

output "step_function_role_arn" {
  description = "ARN of the Step Functions execution role"
  value       = try(aws_iam_role.step_functions.arn, "not-created")
}

# =============================================================================
# EC2 Spot Instance Outputs
# =============================================================================

output "ec2_spot_launch_template_id" {
  description = "ID of the EC2 Spot launch template for video rendering"
  value       = try(aws_launch_template.spot_renderer.id, "not-created")
}

output "ec2_spot_launch_template_latest_version" {
  description = "Latest version of the Spot launch template"
  value       = try(aws_launch_template.spot_renderer.latest_version, "not-created")
}

output "ec2_spot_security_group_id" {
  description = "Security group ID for Spot instances"
  value       = try(aws_security_group.spot_renderer.id, "not-created")
}

output "ec2_spot_instance_profile_arn" {
  description = "Instance profile ARN for Spot instances"
  value       = try(aws_iam_instance_profile.spot_renderer.arn, "not-created")
}

# =============================================================================
# Dashboard Outputs
# =============================================================================

output "dashboard_url" {
  description = "URL of the admin dashboard (after instance launch)"
  value       = var.dashboard_enable_public_ip ? "https://{INSTANCE_PUBLIC_IP}.nip.io" : "Dashboard requires public IP to be enabled"
}

output "dashboard_launch_template_id" {
  description = "ID of the EC2 launch template for the dashboard"
  value       = try(aws_launch_template.dashboard.id, "not-created")
}

output "dashboard_security_group_id" {
  description = "Security group ID for the dashboard instance"
  value       = try(aws_security_group.dashboard.id, "not-created")
}

output "dashboard_instance_profile_arn" {
  description = "Instance profile ARN for dashboard instance"
  value       = try(aws_iam_instance_profile.dashboard.arn, "not-created")
}

# =============================================================================
# EventBridge Outputs
# =============================================================================

output "eventbridge_rule_arn" {
  description = "ARN of the daily EventBridge rule"
  value       = try(aws_cloudwatch_event_rule.daily_trigger.arn, "not-created")
}

output "eventbridge_rule_name" {
  description = "Name of the daily EventBridge rule"
  value       = try(aws_cloudwatch_event_rule.daily_trigger.name, "not-created")
}

output "eventbridge_schedule" {
  description = "Cron schedule for the daily trigger"
  value       = try(aws_cloudwatch_event_rule.daily_trigger.schedule_expression, "not-created")
}

# =============================================================================
# Secrets Manager Outputs
# =============================================================================

output "secrets_arns" {
  description = "Map of Secrets Manager secret ARNs"
  value = {
    deepinfra_api_key = try(aws_secretsmanager_secret.deepinfra_api_key.arn, "not-created")
    admin_credentials = try(aws_secretsmanager_secret.admin_credentials.arn, "not-created")
    jwt_secret        = try(aws_secretsmanager_secret.jwt_secret.arn, "not-created")
  }
  sensitive = true
}

# =============================================================================
# CloudWatch Outputs
# =============================================================================

output "cloudwatch_log_groups" {
  description = "Map of CloudWatch log group names"
  value = {
    manga_fetcher    = try(aws_cloudwatch_log_group.manga_fetcher.name, "not-created")
    script_generator = try(aws_cloudwatch_log_group.script_generator.name, "not-created")
    tts_processor    = try(aws_cloudwatch_log_group.tts_processor.name, "not-created")
    quota_checker    = try(aws_cloudwatch_log_group.quota_checker.name, "not-created")
    cleanup          = try(aws_cloudwatch_log_group.cleanup.name, "not-created")
    step_functions   = try(aws_cloudwatch_log_group.step_functions.name, "not-created")
  }
}

output "sns_topic_arn" {
  description = "ARN of the SNS topic for alerts"
  value       = try(aws_sns_topic.alerts.arn, "not-created")
}

# =============================================================================
# VPC Outputs (if VPC is created)
# =============================================================================

output "vpc_id" {
  description = "ID of the VPC (if created)"
  value       = try(aws_vpc.main.id, "using-default-vpc")
}

output "vpc_cidr_block" {
  description = "CIDR block of the VPC"
  value       = try(aws_vpc.main.cidr_block, "not-created")
}

output "public_subnet_ids" {
  description = "List of public subnet IDs"
  value       = try(aws_subnet.public[*].id, [])
}

output "private_subnet_ids" {
  description = "List of private subnet IDs"
  value       = try(aws_subnet.private[*].id, [])
}

# =============================================================================
# Budget Outputs
# =============================================================================

output "budget_name" {
  description = "Name of the AWS Budget"
  value       = try(aws_budgets_budget.monthly.budget_name, "not-created")
}

output "budget_limit" {
  description = "Monthly budget limit in USD"
  value       = var.monthly_budget_limit
}

# =============================================================================
# Summary Output
# =============================================================================

output "deployment_summary" {
  description = "Summary of deployed resources"
  value = {
    project_name = var.project_name
    environment  = var.environment
    region       = var.region

    resources = {
      s3_buckets           = "2 (videos, deployments)"
      dynamodb_tables      = "2 (jobs, settings)"
      lambda_functions     = "5 (fetcher, generator, tts, quota, cleanup)"
      step_function        = "1 (pipeline orchestrator)"
      ec2_launch_templates = "2 (spot renderer, dashboard)"
      eventbridge_rules    = "1 (daily trigger)"
    }

    monitoring = {
      cloudwatch_log_groups = "6"
      sns_topic             = try(aws_sns_topic.alerts.name, "not-created")
      budget_alerts         = var.budget_alert_email
    }
  }
}

# =============================================================================
# Connection Commands
# =============================================================================

output "useful_commands" {
  description = "Useful AWS CLI commands for this deployment"
  value = {
    view_logs = "aws logs tail /aws/lambda/${try(aws_lambda_function.manga_fetcher.function_name, "FUNCTION_NAME")} --follow"

    start_pipeline = "aws stepfunctions start-execution --state-machine-arn ${try(aws_sfn_state_machine.manga_pipeline.arn, "STATE_MACHINE_ARN")}"

    list_jobs = "aws dynamodb scan --table-name ${try(aws_dynamodb_table.jobs.name, "TABLE_NAME")} --limit 10"

    check_budget = "aws budgets describe-budget --account-id ${data.aws_caller_identity.current.account_id} --budget-name ${try(aws_budgets_budget.monthly.budget_name, "BUDGET_NAME")}"

    get_secret = "aws secretsmanager get-secret-value --secret-id ${var.admin_credentials_secret_name} --query SecretString --output text"

    ssh_dashboard = "ssh -i YOUR_KEY.pem ubuntu@INSTANCE_PUBLIC_IP"
  }
}

# =============================================================================
# Post-Deployment Instructions
# =============================================================================

output "next_steps" {
  description = "Post-deployment instructions"
  value       = <<-EOT

    ╔══════════════════════════════════════════════════════════════════════╗
    ║                   Manga Video Pipeline Deployed                     ║
    ╚══════════════════════════════════════════════════════════════════════╝

    Next Steps:

    1. Deploy Dashboard:
       cd scripts
       ./deploy_dashboard.sh

    2. Launch Dashboard Instance:
       aws ec2 run-instances --launch-template LaunchTemplateId=${try(aws_launch_template.dashboard.id, "TEMPLATE_ID")}

    3. Configure Secrets:
       # DeepInfra API Key
       aws secretsmanager put-secret-value --secret-id ${var.deepinfra_api_key_secret_name} --secret-string "YOUR_API_KEY"

       # Admin Credentials
       aws secretsmanager put-secret-value --secret-id ${var.admin_credentials_secret_name} --secret-string '{"username":"admin","password":"SECURE_PASSWORD"}'

       # JWT Secret
       aws secretsmanager put-secret-value --secret-id ${var.jwt_secret_name} --secret-string "$(openssl rand -hex 32)"

    4. Test Pipeline:
       aws stepfunctions start-execution \
         --state-machine-arn ${try(aws_sfn_state_machine.manga_pipeline.arn, "STATE_MACHINE_ARN")} \
         --input '{}'

    5. Monitor:
       - CloudWatch Logs: /aws/lambda/*
       - Step Functions Console
       - Budget Alerts: ${var.budget_alert_email}

    Documentation:
    - Deployment Guide: scripts/DEPLOYMENT.md
    - Quick Start: scripts/QUICKSTART.md

  EOT
}
