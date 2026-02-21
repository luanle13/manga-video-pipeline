# =============================================================================
# Step Functions State Machine for Manga Video Pipeline
# =============================================================================
# Orchestrates the entire pipeline: fetch → script → TTS → render → upload
# Uses callback pattern for long-running EC2 Spot instances
# =============================================================================

# =============================================================================
# CloudWatch Log Group for Step Functions
# =============================================================================

resource "aws_cloudwatch_log_group" "step_functions" {
  name              = "/aws/states/${var.project_name}-pipeline"
  retention_in_days = var.log_retention_days

  tags = merge(
    local.common_tags,
    {
      Name      = "${var.project_name}-step-functions-logs"
      Component = "step-functions"
    }
  )
}

# =============================================================================
# Step Functions Activity for Renderer Callback
# =============================================================================

resource "aws_sfn_activity" "renderer" {
  name = "${var.project_name}-renderer-activity"

  tags = merge(
    local.common_tags,
    {
      Name      = "${var.project_name}-renderer-activity"
      Component = "step-functions"
    }
  )
}

# =============================================================================
# Step Functions State Machine
# =============================================================================

resource "aws_sfn_state_machine" "pipeline" {
  name     = "${var.project_name}-pipeline"
  role_arn = var.step_functions_role_arn

  # State machine definition with variable substitution
  definition = templatefile("${path.module}/templates/pipeline.asl.json.tpl", {
    region                   = local.region
    account_id               = local.account_id
    quota_checker_arn        = aws_lambda_function.quota_checker.arn
    fetcher_arn              = aws_lambda_function.manga_fetcher.arn
    scriptgen_arn            = aws_lambda_function.script_generator.arn
    ttsgen_arn               = aws_lambda_function.tts_processor.arn
    cleanup_arn              = aws_lambda_function.cleanup.arn
    renderer_launch_template = aws_launch_template.renderer.id
    renderer_activity_arn    = aws_sfn_activity.renderer.id
    project_name             = var.project_name
  })

  # Logging configuration
  logging_configuration {
    log_destination        = "${aws_cloudwatch_log_group.step_functions.arn}:*"
    include_execution_data = true
    level                  = "ALL"
  }

  # Enable X-Ray tracing (optional but useful for debugging)
  tracing_configuration {
    enabled = var.enable_xray_tracing
  }

  tags = merge(
    local.common_tags,
    {
      Name      = "${var.project_name}-pipeline"
      Component = "step-functions"
    }
  )

  depends_on = [aws_cloudwatch_log_group.step_functions]
}

# =============================================================================
# Review Pipeline State Machine
# =============================================================================
# Orchestrates the review video pipeline: scrape → review script → TTS → render → upload
# Uses the same renderer and TTS as the main pipeline but with review-specific fetcher/scriptgen

resource "aws_cloudwatch_log_group" "review_step_functions" {
  name              = "/aws/states/${var.project_name}-review-pipeline"
  retention_in_days = var.log_retention_days

  tags = merge(
    local.common_tags,
    {
      Name      = "${var.project_name}-review-step-functions-logs"
      Component = "step-functions"
      Pipeline  = "review"
    }
  )
}

resource "aws_sfn_state_machine" "review_pipeline" {
  name     = "${var.project_name}-review-pipeline"
  role_arn = var.step_functions_role_arn

  # State machine definition with variable substitution
  definition = templatefile("${path.module}/templates/review_pipeline.asl.json.tpl", {
    region                   = local.region
    account_id               = local.account_id
    review_fetcher_arn       = aws_lambda_function.review_fetcher.arn
    review_scriptgen_arn     = aws_lambda_function.review_scriptgen.arn
    ttsgen_arn               = aws_lambda_function.tts_processor.arn
    cleanup_arn              = aws_lambda_function.cleanup.arn
    renderer_launch_template = aws_launch_template.renderer.id
    renderer_activity_arn    = aws_sfn_activity.renderer.id
    project_name             = var.project_name
  })

  # Logging configuration
  logging_configuration {
    log_destination        = "${aws_cloudwatch_log_group.review_step_functions.arn}:*"
    include_execution_data = true
    level                  = "ALL"
  }

  # Enable X-Ray tracing
  tracing_configuration {
    enabled = var.enable_xray_tracing
  }

  tags = merge(
    local.common_tags,
    {
      Name      = "${var.project_name}-review-pipeline"
      Component = "step-functions"
      Pipeline  = "review"
    }
  )

  depends_on = [aws_cloudwatch_log_group.review_step_functions]
}
