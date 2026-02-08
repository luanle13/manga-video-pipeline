# EventBridge rule to trigger manga video pipeline daily at midnight Vietnam time (UTC+7)

terraform {
  required_version = ">= 1.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

# Variables are defined in variables.tf

# Data sources
data "aws_caller_identity" "current" {}
data "aws_region" "current" {}

# Locals
locals {
  account_id = data.aws_caller_identity.current.account_id
  region     = data.aws_region.current.name

  common_tags = {
    Project     = "manga-video-pipeline"
    Environment = var.environment
    ManagedBy   = "terraform"
  }

  tags = merge(local.common_tags, var.tags)
}

# =====================================================================
# EventBridge Rule - Daily Trigger
# =====================================================================

resource "aws_cloudwatch_event_rule" "daily_pipeline_trigger" {
  name        = "manga-pipeline-daily-trigger-${var.environment}"
  description = "Trigger manga video pipeline daily at midnight Vietnam time (UTC+7)"

  # Cron expression: 0 17 * * ? * (default)
  # Breakdown:
  #   Minutes: 0
  #   Hours: 17 (5 PM UTC = midnight UTC+7)
  #   Day of month: * (every day)
  #   Month: * (every month)
  #   Day of week: ? (any)
  #   Year: * (every year)
  #
  # Vietnam time: 00:00 (midnight)
  # UTC time: 17:00 (previous day)
  schedule_expression = var.schedule_expression

  state = var.enabled ? "ENABLED" : "DISABLED"

  tags = merge(local.tags, {
    Name = "manga-pipeline-daily-trigger"
  })
}

# =====================================================================
# EventBridge Target - Step Functions State Machine
# =====================================================================

resource "aws_cloudwatch_event_target" "step_functions" {
  rule      = aws_cloudwatch_event_rule.daily_pipeline_trigger.name
  target_id = "StepFunctionsStateMachine"
  arn       = var.state_machine_arn
  role_arn  = aws_iam_role.eventbridge_sfn.arn

  # Input to pass to Step Functions (empty JSON object)
  input = "{}"

  # Retry policy for failed executions
  retry_policy {
    maximum_event_age_in_seconds = 3600 # 1 hour
    maximum_retry_attempts       = 2
  }

  # Dead letter queue for failed events (optional but recommended)
  # Uncomment and configure if you want DLQ:
  # dead_letter_config {
  #   arn = aws_sqs_queue.eventbridge_dlq.arn
  # }
}

# =====================================================================
# IAM Role for EventBridge to Invoke Step Functions
# =====================================================================

resource "aws_iam_role" "eventbridge_sfn" {
  name               = "EventBridgeStepFunctionsRole-${var.environment}"
  description        = "Allow EventBridge to start Step Functions state machine executions"
  assume_role_policy = data.aws_iam_policy_document.eventbridge_assume_role.json

  tags = merge(local.tags, {
    Name = "eventbridge-step-functions-role"
  })
}

# Trust policy: Allow EventBridge to assume this role
data "aws_iam_policy_document" "eventbridge_assume_role" {
  statement {
    effect = "Allow"

    principals {
      type        = "Service"
      identifiers = ["events.amazonaws.com"]
    }

    actions = ["sts:AssumeRole"]

    # Security: Only allow EventBridge from this account to assume role
    condition {
      test     = "StringEquals"
      variable = "aws:SourceAccount"
      values   = [local.account_id]
    }
  }
}

# Permissions policy: Allow starting Step Functions executions
resource "aws_iam_role_policy" "eventbridge_sfn_execution" {
  name   = "StartStepFunctionsExecution"
  role   = aws_iam_role.eventbridge_sfn.id
  policy = data.aws_iam_policy_document.eventbridge_sfn_policy.json
}

# Least privilege policy: Only allow starting the specific state machine
data "aws_iam_policy_document" "eventbridge_sfn_policy" {
  statement {
    sid    = "StartStepFunctionsExecution"
    effect = "Allow"

    actions = [
      "states:StartExecution"
    ]

    # Restrict to specific state machine (least privilege)
    resources = [
      var.state_machine_arn
    ]
  }

  # Note: We do NOT grant DescribeExecution or other permissions
  # EventBridge only needs StartExecution to trigger the pipeline
}

# Outputs are defined in outputs.tf
