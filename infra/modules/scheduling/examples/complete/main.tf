# Complete example showing EventBridge scheduling with Step Functions

terraform {
  required_version = ">= 1.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = "us-east-1"

  default_tags {
    tags = {
      Project   = "manga-video-pipeline"
      ManagedBy = "terraform"
      Example   = "complete"
    }
  }
}

# =====================================================================
# Step Functions State Machine (simplified example)
# =====================================================================

# IAM role for Step Functions execution
resource "aws_iam_role" "step_functions" {
  name = "manga-pipeline-step-functions-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "states.amazonaws.com"
        }
        Action = "sts:AssumeRole"
      }
    ]
  })
}

# Policy for Step Functions to invoke Lambda functions
resource "aws_iam_role_policy" "step_functions" {
  name = "step-functions-lambda-policy"
  role = aws_iam_role.step_functions.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "lambda:InvokeFunction"
        ]
        Resource = "*" # In production, restrict to specific Lambda ARNs
      },
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "*"
      }
    ]
  })
}

# Step Functions state machine
resource "aws_sfn_state_machine" "manga_pipeline" {
  name     = "manga-pipeline"
  role_arn = aws_iam_role.step_functions.arn

  # Simplified ASL definition for example purposes
  # In production, use: file("path/to/pipeline.asl.json")
  definition = jsonencode({
    Comment = "Example manga video pipeline state machine"
    StartAt = "CheckQuota"
    States = {
      CheckQuota = {
        Type     = "Task"
        Resource = "arn:aws:lambda:$${AWS::Region}:$${AWS::AccountId}:function:check-quota"
        Next     = "Done"
      }
      Done = {
        Type = "Succeed"
      }
    }
  })

  # Enable logging
  logging_configuration {
    log_destination        = "${aws_cloudwatch_log_group.step_functions.arn}:*"
    include_execution_data = true
    level                  = "ALL"
  }

  # Enable X-Ray tracing
  tracing_configuration {
    enabled = true
  }

  tags = {
    Name = "manga-pipeline"
  }
}

# CloudWatch log group for Step Functions
resource "aws_cloudwatch_log_group" "step_functions" {
  name              = "/aws/states/manga-pipeline"
  retention_in_days = 14

  tags = {
    Name = "manga-pipeline-logs"
  }
}

# =====================================================================
# EventBridge Scheduling Module
# =====================================================================

module "pipeline_scheduling" {
  source = "../../"

  state_machine_arn = aws_sfn_state_machine.manga_pipeline.arn
  environment       = "prod"
  enabled           = true

  # Override schedule if needed (default is midnight Vietnam time)
  # schedule_expression = "cron(0 17 * * ? *)"

  tags = {
    Owner = "content-team"
    SLA   = "critical"
  }
}

# =====================================================================
# Monitoring (Optional)
# =====================================================================

# CloudWatch alarm for failed EventBridge invocations
resource "aws_cloudwatch_metric_alarm" "eventbridge_failures" {
  alarm_name          = "manga-pipeline-eventbridge-failures"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "1"
  metric_name         = "FailedInvocations"
  namespace           = "AWS/Events"
  period              = "300"
  statistic           = "Sum"
  threshold           = "0"
  alarm_description   = "Alert when EventBridge fails to trigger pipeline"
  treat_missing_data  = "notBreaching"

  dimensions = {
    RuleName = module.pipeline_scheduling.eventbridge_rule_name
  }

  alarm_actions = [] # Add SNS topic ARN for notifications
}

# CloudWatch alarm for failed Step Functions executions
resource "aws_cloudwatch_metric_alarm" "step_functions_failures" {
  alarm_name          = "manga-pipeline-step-functions-failures"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "1"
  metric_name         = "ExecutionsFailed"
  namespace           = "AWS/States"
  period              = "300"
  statistic           = "Sum"
  threshold           = "0"
  alarm_description   = "Alert when Step Functions execution fails"
  treat_missing_data  = "notBreaching"

  dimensions = {
    StateMachineArn = aws_sfn_state_machine.manga_pipeline.arn
  }

  alarm_actions = [] # Add SNS topic ARN for notifications
}

# =====================================================================
# Outputs
# =====================================================================

output "state_machine_arn" {
  description = "ARN of the Step Functions state machine"
  value       = aws_sfn_state_machine.manga_pipeline.arn
}

output "state_machine_console_url" {
  description = "AWS Console URL for the state machine"
  value       = "https://console.aws.amazon.com/states/home?region=${data.aws_region.current.name}#/statemachines/view/${aws_sfn_state_machine.manga_pipeline.arn}"
}

output "eventbridge_rule_name" {
  description = "Name of the EventBridge rule"
  value       = module.pipeline_scheduling.eventbridge_rule_name
}

output "eventbridge_console_url" {
  description = "AWS Console URL for the EventBridge rule"
  value       = "https://console.aws.amazon.com/events/home?region=${data.aws_region.current.name}#/rules/${module.pipeline_scheduling.eventbridge_rule_name}"
}

output "schedule_expression" {
  description = "Schedule expression for the pipeline"
  value       = module.pipeline_scheduling.schedule_expression
}

output "schedule_description" {
  description = "Human-readable schedule description"
  value       = module.pipeline_scheduling.schedule_description
}

# Data sources
data "aws_region" "current" {}
data "aws_caller_identity" "current" {}
