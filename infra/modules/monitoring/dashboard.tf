# =============================================================================
# CloudWatch Dashboard for Manga Video Pipeline (Optional)
# =============================================================================
# Provides visual overview of pipeline health and performance
# =============================================================================

resource "aws_cloudwatch_dashboard" "pipeline" {
  count = var.create_dashboard ? 1 : 0

  dashboard_name = "${var.project_name}-pipeline"

  dashboard_body = jsonencode({
    widgets = [
      # =======================================================================
      # Row 1: Pipeline Overview
      # =======================================================================
      {
        type   = "text"
        x      = 0
        y      = 0
        width  = 24
        height = 1
        properties = {
          markdown = "# Manga Video Pipeline - ${var.environment}"
        }
      },

      # =======================================================================
      # Row 2: Step Functions Metrics
      # =======================================================================
      {
        type   = "metric"
        x      = 0
        y      = 1
        width  = 8
        height = 6
        properties = {
          title  = "Step Functions Executions"
          region = local.region
          metrics = [
            ["AWS/States", "ExecutionsStarted", "StateMachineArn", "arn:aws:states:${local.region}:${local.account_id}:stateMachine:${var.state_machine_name}", { label = "Started", color = "#2ca02c" }],
            [".", "ExecutionsSucceeded", ".", ".", { label = "Succeeded", color = "#1f77b4" }],
            [".", "ExecutionsFailed", ".", ".", { label = "Failed", color = "#d62728" }],
            [".", "ExecutionsTimedOut", ".", ".", { label = "Timed Out", color = "#ff7f0e" }]
          ]
          period = 300
          stat   = "Sum"
          view   = "timeSeries"
        }
      },
      {
        type   = "metric"
        x      = 8
        y      = 1
        width  = 8
        height = 6
        properties = {
          title  = "Step Functions Execution Time"
          region = local.region
          metrics = [
            ["AWS/States", "ExecutionTime", "StateMachineArn", "arn:aws:states:${local.region}:${local.account_id}:stateMachine:${var.state_machine_name}", { label = "Duration" }]
          ]
          period = 300
          stat   = "Average"
          view   = "timeSeries"
        }
      },
      {
        type   = "metric"
        x      = 16
        y      = 1
        width  = 8
        height = 6
        properties = {
          title  = "Pipeline Success Rate"
          region = local.region
          metrics = [
            [{ expression = "100 * succeeded / started", label = "Success Rate %", id = "e1" }],
            ["AWS/States", "ExecutionsSucceeded", "StateMachineArn", "arn:aws:states:${local.region}:${local.account_id}:stateMachine:${var.state_machine_name}", { id = "succeeded", visible = false }],
            [".", "ExecutionsStarted", ".", ".", { id = "started", visible = false }]
          ]
          period = 3600
          stat   = "Sum"
          view   = "singleValue"
        }
      },

      # =======================================================================
      # Row 3: Lambda Functions - Invocations and Errors
      # =======================================================================
      {
        type   = "metric"
        x      = 0
        y      = 7
        width  = 12
        height = 6
        properties = {
          title  = "Lambda Invocations"
          region = local.region
          metrics = [
            ["AWS/Lambda", "Invocations", "FunctionName", local.lambda_functions.manga_fetcher, { label = "Fetcher" }],
            [".", ".", ".", local.lambda_functions.script_generator, { label = "Script Gen" }],
            [".", ".", ".", local.lambda_functions.tts_processor, { label = "TTS" }],
            [".", ".", ".", local.lambda_functions.quota_checker, { label = "Quota Check" }],
            [".", ".", ".", local.lambda_functions.cleanup, { label = "Cleanup" }]
          ]
          period = 300
          stat   = "Sum"
          view   = "timeSeries"
        }
      },
      {
        type   = "metric"
        x      = 12
        y      = 7
        width  = 12
        height = 6
        properties = {
          title  = "Lambda Errors"
          region = local.region
          metrics = [
            ["AWS/Lambda", "Errors", "FunctionName", local.lambda_functions.manga_fetcher, { label = "Fetcher", color = "#d62728" }],
            [".", ".", ".", local.lambda_functions.script_generator, { label = "Script Gen", color = "#ff7f0e" }],
            [".", ".", ".", local.lambda_functions.tts_processor, { label = "TTS", color = "#9467bd" }],
            [".", ".", ".", local.lambda_functions.quota_checker, { label = "Quota Check", color = "#8c564b" }],
            [".", ".", ".", local.lambda_functions.cleanup, { label = "Cleanup", color = "#e377c2" }]
          ]
          period = 300
          stat   = "Sum"
          view   = "timeSeries"
        }
      },

      # =======================================================================
      # Row 4: Lambda Duration and Concurrent Executions
      # =======================================================================
      {
        type   = "metric"
        x      = 0
        y      = 13
        width  = 12
        height = 6
        properties = {
          title  = "Lambda Duration (Avg)"
          region = local.region
          metrics = [
            ["AWS/Lambda", "Duration", "FunctionName", local.lambda_functions.manga_fetcher, { label = "Fetcher" }],
            [".", ".", ".", local.lambda_functions.script_generator, { label = "Script Gen" }],
            [".", ".", ".", local.lambda_functions.tts_processor, { label = "TTS" }],
            [".", ".", ".", local.lambda_functions.quota_checker, { label = "Quota Check" }],
            [".", ".", ".", local.lambda_functions.cleanup, { label = "Cleanup" }]
          ]
          period = 300
          stat   = "Average"
          view   = "timeSeries"
        }
      },
      {
        type   = "metric"
        x      = 12
        y      = 13
        width  = 12
        height = 6
        properties = {
          title  = "Lambda Concurrent Executions"
          region = local.region
          metrics = [
            ["AWS/Lambda", "ConcurrentExecutions", "FunctionName", local.lambda_functions.manga_fetcher, { label = "Fetcher" }],
            [".", ".", ".", local.lambda_functions.script_generator, { label = "Script Gen" }],
            [".", ".", ".", local.lambda_functions.tts_processor, { label = "TTS" }]
          ]
          period = 60
          stat   = "Maximum"
          view   = "timeSeries"
        }
      },

      # =======================================================================
      # Row 5: DynamoDB Metrics
      # =======================================================================
      {
        type   = "metric"
        x      = 0
        y      = 19
        width  = 8
        height = 6
        properties = {
          title  = "DynamoDB Read/Write"
          region = local.region
          metrics = [
            ["AWS/DynamoDB", "ConsumedReadCapacityUnits", "TableName", "${var.project_name}-jobs", { label = "Jobs Read" }],
            [".", "ConsumedWriteCapacityUnits", ".", ".", { label = "Jobs Write" }],
            [".", "ConsumedReadCapacityUnits", ".", "${var.project_name}-settings", { label = "Settings Read" }]
          ]
          period = 300
          stat   = "Sum"
          view   = "timeSeries"
        }
      },
      {
        type   = "metric"
        x      = 8
        y      = 19
        width  = 8
        height = 6
        properties = {
          title  = "S3 Bucket Size"
          region = local.region
          metrics = [
            ["AWS/S3", "BucketSizeBytes", "BucketName", "${var.project_name}-assets", "StorageType", "StandardStorage", { label = "Total Size" }]
          ]
          period = 86400
          stat   = "Average"
          view   = "singleValue"
        }
      },
      {
        type   = "metric"
        x      = 16
        y      = 19
        width  = 8
        height = 6
        properties = {
          title  = "S3 Object Count"
          region = local.region
          metrics = [
            ["AWS/S3", "NumberOfObjects", "BucketName", "${var.project_name}-assets", "StorageType", "AllStorageTypes", { label = "Objects" }]
          ]
          period = 86400
          stat   = "Average"
          view   = "singleValue"
        }
      },

      # =======================================================================
      # Row 6: Alarm Status
      # =======================================================================
      {
        type   = "alarm"
        x      = 0
        y      = 25
        width  = 24
        height = 3
        properties = {
          title = "Alarm Status"
          alarms = [
            "arn:aws:cloudwatch:${local.region}:${local.account_id}:alarm:${var.project_name}-step-functions-failed",
            "arn:aws:cloudwatch:${local.region}:${local.account_id}:alarm:${var.project_name}-manga_fetcher-errors",
            "arn:aws:cloudwatch:${local.region}:${local.account_id}:alarm:${var.project_name}-script_generator-errors",
            "arn:aws:cloudwatch:${local.region}:${local.account_id}:alarm:${var.project_name}-tts_processor-errors"
          ]
        }
      }
    ]
  })
}
