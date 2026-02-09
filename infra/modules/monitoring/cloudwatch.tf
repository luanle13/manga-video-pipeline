# =============================================================================
# CloudWatch Alarms for Manga Video Pipeline
# =============================================================================

# =============================================================================
# SNS Topic for Alarm Notifications
# =============================================================================

resource "aws_sns_topic" "alarms" {
  count = var.create_sns_topic ? 1 : 0

  name = "${var.project_name}-alarms"

  tags = merge(
    local.common_tags,
    {
      Name      = "${var.project_name}-alarms"
      Component = "notifications"
    }
  )
}

resource "aws_sns_topic_subscription" "email" {
  count = var.create_sns_topic ? 1 : 0

  topic_arn = aws_sns_topic.alarms[0].arn
  protocol  = "email"
  endpoint  = var.alarm_email
}

locals {
  # Use created topic or provided topic ARN
  alarm_topic_arn = var.create_sns_topic ? aws_sns_topic.alarms[0].arn : var.sns_topic_arn

  # Alarm actions (only if enabled)
  alarm_actions = var.enable_alarm_actions ? [local.alarm_topic_arn] : []
  ok_actions    = var.enable_alarm_actions ? [local.alarm_topic_arn] : []
}

# =============================================================================
# Lambda Error Rate Alarms
# =============================================================================
# Triggers when Lambda errors exceed threshold per hour

resource "aws_cloudwatch_metric_alarm" "lambda_errors" {
  for_each = local.lambda_functions

  alarm_name          = "${var.project_name}-${each.key}-errors"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "Errors"
  namespace           = "AWS/Lambda"
  period              = 3600 # 1 hour
  statistic           = "Sum"
  threshold           = var.lambda_error_threshold
  alarm_description   = "Lambda function ${each.value} has more than ${var.lambda_error_threshold} errors in the last hour"
  treat_missing_data  = var.treat_missing_data

  dimensions = {
    FunctionName = each.value
  }

  alarm_actions = local.alarm_actions
  ok_actions    = local.ok_actions

  tags = merge(
    local.common_tags,
    {
      Name      = "${var.project_name}-${each.key}-errors"
      Component = "lambda"
      Function  = each.key
    }
  )
}

# =============================================================================
# Lambda Duration Alarms (Optional - High Duration Warning)
# =============================================================================
# Warns when Lambda is running close to timeout

resource "aws_cloudwatch_metric_alarm" "lambda_duration" {
  for_each = local.lambda_functions

  alarm_name          = "${var.project_name}-${each.key}-duration"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "Duration"
  namespace           = "AWS/Lambda"
  period              = 300 # 5 minutes
  statistic           = "Maximum"
  threshold           = var.lambda_duration_thresholds[each.key]
  alarm_description   = "Lambda function ${each.value} duration exceeds ${var.lambda_duration_thresholds[each.key]}ms"
  treat_missing_data  = var.treat_missing_data

  dimensions = {
    FunctionName = each.value
  }

  alarm_actions = local.alarm_actions
  ok_actions    = local.ok_actions

  tags = merge(
    local.common_tags,
    {
      Name      = "${var.project_name}-${each.key}-duration"
      Component = "lambda"
      Function  = each.key
    }
  )
}

# =============================================================================
# Lambda Throttle Alarms
# =============================================================================
# Triggers when Lambda functions are being throttled

resource "aws_cloudwatch_metric_alarm" "lambda_throttles" {
  for_each = local.lambda_functions

  alarm_name          = "${var.project_name}-${each.key}-throttles"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "Throttles"
  namespace           = "AWS/Lambda"
  period              = 300 # 5 minutes
  statistic           = "Sum"
  threshold           = 0
  alarm_description   = "Lambda function ${each.value} is being throttled"
  treat_missing_data  = var.treat_missing_data

  dimensions = {
    FunctionName = each.value
  }

  alarm_actions = local.alarm_actions
  ok_actions    = local.ok_actions

  tags = merge(
    local.common_tags,
    {
      Name      = "${var.project_name}-${each.key}-throttles"
      Component = "lambda"
      Function  = each.key
    }
  )
}

# =============================================================================
# Step Functions Execution Failed Alarm
# =============================================================================

resource "aws_cloudwatch_metric_alarm" "step_functions_failed" {
  alarm_name          = "${var.project_name}-step-functions-failed"
  comparison_operator = "GreaterThanOrEqualToThreshold"
  evaluation_periods  = 1
  metric_name         = "ExecutionsFailed"
  namespace           = "AWS/States"
  period              = 300 # 5 minutes
  statistic           = "Sum"
  threshold           = var.step_functions_failure_threshold
  alarm_description   = "Step Functions state machine ${var.state_machine_name} has failed executions"
  treat_missing_data  = var.treat_missing_data

  dimensions = {
    StateMachineArn = "arn:aws:states:${local.region}:${local.account_id}:stateMachine:${var.state_machine_name}"
  }

  alarm_actions = local.alarm_actions
  ok_actions    = local.ok_actions

  tags = merge(
    local.common_tags,
    {
      Name      = "${var.project_name}-step-functions-failed"
      Component = "step-functions"
    }
  )
}

# =============================================================================
# Step Functions Execution Timed Out Alarm
# =============================================================================

resource "aws_cloudwatch_metric_alarm" "step_functions_timed_out" {
  alarm_name          = "${var.project_name}-step-functions-timed-out"
  comparison_operator = "GreaterThanOrEqualToThreshold"
  evaluation_periods  = 1
  metric_name         = "ExecutionsTimedOut"
  namespace           = "AWS/States"
  period              = 3600 # 1 hour
  statistic           = "Sum"
  threshold           = 1
  alarm_description   = "Step Functions state machine ${var.state_machine_name} has timed out executions"
  treat_missing_data  = var.treat_missing_data

  dimensions = {
    StateMachineArn = "arn:aws:states:${local.region}:${local.account_id}:stateMachine:${var.state_machine_name}"
  }

  alarm_actions = local.alarm_actions
  ok_actions    = local.ok_actions

  tags = merge(
    local.common_tags,
    {
      Name      = "${var.project_name}-step-functions-timed-out"
      Component = "step-functions"
    }
  )
}

# =============================================================================
# Step Functions Execution Aborted Alarm
# =============================================================================

resource "aws_cloudwatch_metric_alarm" "step_functions_aborted" {
  alarm_name          = "${var.project_name}-step-functions-aborted"
  comparison_operator = "GreaterThanOrEqualToThreshold"
  evaluation_periods  = 1
  metric_name         = "ExecutionsAborted"
  namespace           = "AWS/States"
  period              = 3600 # 1 hour
  statistic           = "Sum"
  threshold           = 1
  alarm_description   = "Step Functions state machine ${var.state_machine_name} has aborted executions"
  treat_missing_data  = var.treat_missing_data

  dimensions = {
    StateMachineArn = "arn:aws:states:${local.region}:${local.account_id}:stateMachine:${var.state_machine_name}"
  }

  alarm_actions = local.alarm_actions
  ok_actions    = local.ok_actions

  tags = merge(
    local.common_tags,
    {
      Name      = "${var.project_name}-step-functions-aborted"
      Component = "step-functions"
    }
  )
}

# =============================================================================
# EC2 Spot Interruption Alarm
# =============================================================================
# Uses EventBridge rule to track Spot interruption warnings

resource "aws_cloudwatch_event_rule" "spot_interruption" {
  count = var.enable_spot_interruption_alarm ? 1 : 0

  name        = "${var.project_name}-spot-interruption"
  description = "Capture EC2 Spot Instance interruption warnings"

  event_pattern = jsonencode({
    source      = ["aws.ec2"]
    detail-type = ["EC2 Spot Instance Interruption Warning"]
    detail = {
      instance-action = ["terminate", "stop", "hibernate"]
    }
  })

  tags = merge(
    local.common_tags,
    {
      Name      = "${var.project_name}-spot-interruption"
      Component = "ec2-spot"
    }
  )
}

resource "aws_cloudwatch_event_target" "spot_interruption_sns" {
  count = var.enable_spot_interruption_alarm ? 1 : 0

  rule      = aws_cloudwatch_event_rule.spot_interruption[0].name
  target_id = "SendToSNS"
  arn       = local.alarm_topic_arn

  input_transformer {
    input_paths = {
      instance_id = "$.detail.instance-id"
      action      = "$.detail.instance-action"
      time        = "$.time"
    }
    input_template = "\"EC2 Spot Interruption Warning: Instance <instance_id> will be <action> at <time>\""
  }
}

# SNS topic policy to allow EventBridge to publish
resource "aws_sns_topic_policy" "allow_eventbridge" {
  count = var.create_sns_topic && var.enable_spot_interruption_alarm ? 1 : 0

  arn = aws_sns_topic.alarms[0].arn

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "AllowEventBridgePublish"
        Effect = "Allow"
        Principal = {
          Service = "events.amazonaws.com"
        }
        Action   = "sns:Publish"
        Resource = aws_sns_topic.alarms[0].arn
        Condition = {
          ArnLike = {
            "aws:SourceArn" = aws_cloudwatch_event_rule.spot_interruption[0].arn
          }
        }
      }
    ]
  })
}

# =============================================================================
# Spot Interruption Count Metric and Alarm
# =============================================================================
# Custom metric to count Spot interruptions per day

resource "aws_cloudwatch_log_metric_filter" "spot_interruptions" {
  count = var.enable_spot_interruption_alarm ? 1 : 0

  name           = "${var.project_name}-spot-interruptions"
  pattern        = "{ $.detail-type = \"EC2 Spot Instance Interruption Warning\" }"
  log_group_name = "/aws/events/${var.project_name}"

  metric_transformation {
    name          = "SpotInterruptions"
    namespace     = "${var.project_name}/EC2"
    value         = "1"
    default_value = "0"
  }
}

resource "aws_cloudwatch_metric_alarm" "spot_interruption_count" {
  count = var.enable_spot_interruption_alarm ? 1 : 0

  alarm_name          = "${var.project_name}-spot-interruption-count"
  comparison_operator = "GreaterThanOrEqualToThreshold"
  evaluation_periods  = 1
  metric_name         = "SpotInterruptions"
  namespace           = "${var.project_name}/EC2"
  period              = 86400 # 24 hours
  statistic           = "Sum"
  threshold           = var.spot_interruption_threshold
  alarm_description   = "More than ${var.spot_interruption_threshold} Spot interruptions in the last 24 hours"
  treat_missing_data  = "notBreaching"

  alarm_actions = local.alarm_actions
  ok_actions    = local.ok_actions

  tags = merge(
    local.common_tags,
    {
      Name      = "${var.project_name}-spot-interruption-count"
      Component = "ec2-spot"
    }
  )
}

# =============================================================================
# DynamoDB Throttle Alarms
# =============================================================================

resource "aws_cloudwatch_metric_alarm" "dynamodb_throttle" {
  for_each = toset([
    "${var.project_name}-jobs",
    "${var.project_name}-processed-manga",
    "${var.project_name}-settings"
  ])

  alarm_name          = "${each.value}-throttle"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "ThrottledRequests"
  namespace           = "AWS/DynamoDB"
  period              = 300 # 5 minutes
  statistic           = "Sum"
  threshold           = 0
  alarm_description   = "DynamoDB table ${each.value} is being throttled"
  treat_missing_data  = var.treat_missing_data

  dimensions = {
    TableName = each.value
  }

  alarm_actions = local.alarm_actions
  ok_actions    = local.ok_actions

  tags = merge(
    local.common_tags,
    {
      Name      = "${each.value}-throttle"
      Component = "dynamodb"
    }
  )
}
