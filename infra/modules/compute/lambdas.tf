# =============================================================================
# Lambda Functions for Manga Video Pipeline
# =============================================================================
# This file creates all Lambda functions for the video processing pipeline.
# All functions use arm64 architecture for cost savings (~20% cheaper).
# =============================================================================

# =============================================================================
# CloudWatch Log Groups
# =============================================================================
# Create log groups before Lambda functions to control retention settings.
# Lambda will use these existing log groups instead of creating new ones.

resource "aws_cloudwatch_log_group" "manga_fetcher" {
  name              = "/aws/lambda/${local.lambda_functions.manga_fetcher.name}"
  retention_in_days = var.log_retention_days

  tags = merge(
    local.common_tags,
    {
      Name      = "${local.lambda_functions.manga_fetcher.name}-logs"
      Component = "lambda"
      Function  = "manga-fetcher"
    }
  )
}

resource "aws_cloudwatch_log_group" "script_generator" {
  name              = "/aws/lambda/${local.lambda_functions.script_generator.name}"
  retention_in_days = var.log_retention_days

  tags = merge(
    local.common_tags,
    {
      Name      = "${local.lambda_functions.script_generator.name}-logs"
      Component = "lambda"
      Function  = "script-generator"
    }
  )
}

resource "aws_cloudwatch_log_group" "tts_processor" {
  name              = "/aws/lambda/${local.lambda_functions.tts_processor.name}"
  retention_in_days = var.log_retention_days

  tags = merge(
    local.common_tags,
    {
      Name      = "${local.lambda_functions.tts_processor.name}-logs"
      Component = "lambda"
      Function  = "tts-processor"
    }
  )
}

resource "aws_cloudwatch_log_group" "cleanup" {
  name              = "/aws/lambda/${local.lambda_functions.cleanup.name}"
  retention_in_days = var.log_retention_days

  tags = merge(
    local.common_tags,
    {
      Name      = "${local.lambda_functions.cleanup.name}-logs"
      Component = "lambda"
      Function  = "cleanup"
    }
  )
}

resource "aws_cloudwatch_log_group" "quota_checker" {
  name              = "/aws/lambda/${local.lambda_functions.quota_checker.name}"
  retention_in_days = var.log_retention_days

  tags = merge(
    local.common_tags,
    {
      Name      = "${local.lambda_functions.quota_checker.name}-logs"
      Component = "lambda"
      Function  = "quota-checker"
    }
  )
}

# =============================================================================
# 1. Manga Fetcher Lambda
# =============================================================================
# Downloads manga panels from MangaDex API and stores them in S3.
# Memory: 512 MB (image processing)
# Timeout: 15 minutes (multiple chapter pages)

resource "aws_lambda_function" "manga_fetcher" {
  function_name = local.lambda_functions.manga_fetcher.name
  description   = local.lambda_functions.manga_fetcher.description
  role          = local.lambda_functions.manga_fetcher.role_arn

  # Deployment package from S3
  s3_bucket = var.lambda_deployment_bucket
  s3_key    = "${var.lambda_deployment_prefix}/manga-fetcher-${var.lambda_package_version}.zip"

  # Runtime configuration
  runtime       = var.lambda_runtime
  architectures = [var.lambda_architecture]
  handler       = local.lambda_functions.manga_fetcher.handler

  # Resource limits
  memory_size = local.lambda_functions.manga_fetcher.memory_size
  timeout     = local.lambda_functions.manga_fetcher.timeout

  # Reserved concurrency (if set)
  reserved_concurrent_executions = var.reserved_concurrency.manga_fetcher >= 0 ? var.reserved_concurrency.manga_fetcher : null

  # Environment variables
  environment {
    variables = local.lambda_functions.manga_fetcher.environment
  }

  # Ensure log group exists before function
  depends_on = [aws_cloudwatch_log_group.manga_fetcher]

  tags = merge(
    local.common_tags,
    {
      Name      = local.lambda_functions.manga_fetcher.name
      Component = "lambda"
      Function  = "manga-fetcher"
      Stage     = "fetching"
    }
  )

  lifecycle {
    # Ignore changes to S3 key when using CI/CD deployments
    ignore_changes = [
      s3_key,
      source_code_hash,
    ]
  }
}

# =============================================================================
# 2. Script Generator Lambda
# =============================================================================
# Generates Vietnamese narration scripts using DeepInfra/Qwen LLM.
# Memory: 256 MB (API calls, minimal local processing)
# Timeout: 15 minutes (LLM processing time)

resource "aws_lambda_function" "script_generator" {
  function_name = local.lambda_functions.script_generator.name
  description   = local.lambda_functions.script_generator.description
  role          = local.lambda_functions.script_generator.role_arn

  # Deployment package from S3
  s3_bucket = var.lambda_deployment_bucket
  s3_key    = "${var.lambda_deployment_prefix}/script-generator-${var.lambda_package_version}.zip"

  # Runtime configuration
  runtime       = var.lambda_runtime
  architectures = [var.lambda_architecture]
  handler       = local.lambda_functions.script_generator.handler

  # Resource limits
  memory_size = local.lambda_functions.script_generator.memory_size
  timeout     = local.lambda_functions.script_generator.timeout

  # Reserved concurrency - limit concurrent LLM API calls
  reserved_concurrent_executions = var.reserved_concurrency.script_generator >= 0 ? var.reserved_concurrency.script_generator : null

  # Environment variables
  environment {
    variables = local.lambda_functions.script_generator.environment
  }

  # Ensure log group exists before function
  depends_on = [aws_cloudwatch_log_group.script_generator]

  tags = merge(
    local.common_tags,
    {
      Name      = local.lambda_functions.script_generator.name
      Component = "lambda"
      Function  = "script-generator"
      Stage     = "scripting"
    }
  )

  lifecycle {
    ignore_changes = [
      s3_key,
      source_code_hash,
    ]
  }
}

# =============================================================================
# 3. TTS Processor Lambda
# =============================================================================
# Converts script text to Vietnamese audio using Edge TTS.
# Memory: 512 MB (audio generation)
# Timeout: 15 minutes (uses continuation for long scripts)

resource "aws_lambda_function" "tts_processor" {
  function_name = local.lambda_functions.tts_processor.name
  description   = local.lambda_functions.tts_processor.description
  role          = local.lambda_functions.tts_processor.role_arn

  # Deployment package from S3
  s3_bucket = var.lambda_deployment_bucket
  s3_key    = "${var.lambda_deployment_prefix}/tts-processor-${var.lambda_package_version}.zip"

  # Runtime configuration
  runtime       = var.lambda_runtime
  architectures = [var.lambda_architecture]
  handler       = local.lambda_functions.tts_processor.handler

  # Resource limits
  memory_size = local.lambda_functions.tts_processor.memory_size
  timeout     = local.lambda_functions.tts_processor.timeout

  # Reserved concurrency (if set)
  reserved_concurrent_executions = var.reserved_concurrency.tts_processor >= 0 ? var.reserved_concurrency.tts_processor : null

  # Environment variables
  environment {
    variables = local.lambda_functions.tts_processor.environment
  }

  # Ensure log group exists before function
  depends_on = [aws_cloudwatch_log_group.tts_processor]

  tags = merge(
    local.common_tags,
    {
      Name      = local.lambda_functions.tts_processor.name
      Component = "lambda"
      Function  = "tts-processor"
      Stage     = "tts"
    }
  )

  lifecycle {
    ignore_changes = [
      s3_key,
      source_code_hash,
    ]
  }
}

# =============================================================================
# 4. Cleanup Lambda
# =============================================================================
# Cleans up temporary S3 objects after job completion or failure.
# Memory: 128 MB (S3 delete operations)
# Timeout: 5 minutes

resource "aws_lambda_function" "cleanup" {
  function_name = local.lambda_functions.cleanup.name
  description   = local.lambda_functions.cleanup.description
  role          = local.lambda_functions.cleanup.role_arn

  # Deployment package from S3
  s3_bucket = var.lambda_deployment_bucket
  s3_key    = "${var.lambda_deployment_prefix}/cleanup-${var.lambda_package_version}.zip"

  # Runtime configuration
  runtime       = var.lambda_runtime
  architectures = [var.lambda_architecture]
  handler       = local.lambda_functions.cleanup.handler

  # Resource limits
  memory_size = local.lambda_functions.cleanup.memory_size
  timeout     = local.lambda_functions.cleanup.timeout

  # Reserved concurrency (if set)
  reserved_concurrent_executions = var.reserved_concurrency.cleanup >= 0 ? var.reserved_concurrency.cleanup : null

  # Environment variables
  environment {
    variables = local.lambda_functions.cleanup.environment
  }

  # Ensure log group exists before function
  depends_on = [aws_cloudwatch_log_group.cleanup]

  tags = merge(
    local.common_tags,
    {
      Name      = local.lambda_functions.cleanup.name
      Component = "lambda"
      Function  = "cleanup"
      Stage     = "cleanup"
    }
  )

  lifecycle {
    ignore_changes = [
      s3_key,
      source_code_hash,
    ]
  }
}

# =============================================================================
# 5. Quota Checker Lambda
# =============================================================================
# Checks daily YouTube upload quota before starting pipeline.
# Memory: 128 MB (simple DynamoDB queries)
# Timeout: 30 seconds

resource "aws_lambda_function" "quota_checker" {
  function_name = local.lambda_functions.quota_checker.name
  description   = local.lambda_functions.quota_checker.description
  role          = local.lambda_functions.quota_checker.role_arn

  # Deployment package from S3
  s3_bucket = var.lambda_deployment_bucket
  s3_key    = "${var.lambda_deployment_prefix}/quota-checker-${var.lambda_package_version}.zip"

  # Runtime configuration
  runtime       = var.lambda_runtime
  architectures = [var.lambda_architecture]
  handler       = local.lambda_functions.quota_checker.handler

  # Resource limits
  memory_size = local.lambda_functions.quota_checker.memory_size
  timeout     = local.lambda_functions.quota_checker.timeout

  # Reserved concurrency (if set)
  reserved_concurrent_executions = var.reserved_concurrency.quota_checker >= 0 ? var.reserved_concurrency.quota_checker : null

  # Environment variables
  environment {
    variables = local.lambda_functions.quota_checker.environment
  }

  # Ensure log group exists before function
  depends_on = [aws_cloudwatch_log_group.quota_checker]

  tags = merge(
    local.common_tags,
    {
      Name      = local.lambda_functions.quota_checker.name
      Component = "lambda"
      Function  = "quota-checker"
      Stage     = "pre-check"
    }
  )

  lifecycle {
    ignore_changes = [
      s3_key,
      source_code_hash,
    ]
  }
}
