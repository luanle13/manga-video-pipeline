# =============================================================================
# Compute Module - Data Sources and Locals
# =============================================================================

data "aws_caller_identity" "current" {}
data "aws_region" "current" {}

locals {
  account_id = data.aws_caller_identity.current.account_id
  region     = data.aws_region.current.name

  # Common tags for all compute resources
  common_tags = merge(
    var.tags,
    {
      Project    = var.project_name
      Module     = "compute"
      ManagedBy  = "terraform"
      Owner      = "DevOps"
      Repository = "manga-video-pipeline"
    }
  )

  # Lambda function configurations
  lambda_functions = {
    manga_fetcher = {
      name        = "${var.project_name}-manga-fetcher"
      description = "Fetches manga chapters from MangaDex and stores images in S3"
      handler     = "src.fetcher.handler.handler"
      memory_size = 512
      timeout     = 900
      role_arn    = var.lambda_role_arns.manga_fetcher
      environment = {
        AWS_REGION_NAME          = local.region
        S3_BUCKET                = var.s3_assets_bucket_name
        DYNAMODB_JOBS_TABLE      = var.dynamodb_jobs_table_name
        DYNAMODB_MANGA_TABLE = var.dynamodb_processed_manga_table_name
        MANGADEX_SECRET_NAME     = var.mangadex_secret_name
        LOG_LEVEL                = var.log_level
      }
    }
    script_generator = {
      name        = "${var.project_name}-script-generator"
      description = "Generates Vietnamese narration scripts using DeepInfra LLM"
      handler     = "src.scriptgen.handler.handler"
      memory_size = 256
      timeout     = 900
      role_arn    = var.lambda_role_arns.script_generator
      environment = {
        AWS_REGION_NAME         = local.region
        S3_BUCKET               = var.s3_assets_bucket_name
        DYNAMODB_JOBS_TABLE     = var.dynamodb_jobs_table_name
        DYNAMODB_SETTINGS_TABLE = var.dynamodb_settings_table_name
        DEEPINFRA_SECRET_NAME   = var.deepinfra_api_key_secret_name
        LOG_LEVEL               = var.log_level
      }
    }
    tts_processor = {
      name        = "${var.project_name}-tts-processor"
      description = "Converts script text to Vietnamese audio using Edge TTS"
      handler     = "src.ttsgen.handler.handler"
      memory_size = 512
      timeout     = 900
      role_arn    = var.lambda_role_arns.tts_processor
      environment = {
        AWS_REGION_NAME         = local.region
        S3_BUCKET               = var.s3_assets_bucket_name
        DYNAMODB_JOBS_TABLE     = var.dynamodb_jobs_table_name
        DYNAMODB_SETTINGS_TABLE = var.dynamodb_settings_table_name
        LOG_LEVEL               = var.log_level
      }
    }
    cleanup = {
      name        = "${var.project_name}-cleanup"
      description = "Cleans up temporary S3 objects after job completion"
      handler     = "src.cleanup.handler.handler"
      memory_size = 128
      timeout     = 300
      role_arn    = var.lambda_role_arns.cleanup
      environment = {
        AWS_REGION_NAME     = local.region
        S3_BUCKET           = var.s3_assets_bucket_name
        DYNAMODB_JOBS_TABLE = var.dynamodb_jobs_table_name
        LOG_LEVEL           = var.log_level
      }
    }
    quota_checker = {
      name        = "${var.project_name}-quota-checker"
      description = "Checks daily YouTube upload quota before starting pipeline"
      handler     = "src.scheduler.quota_checker.handler"
      memory_size = 128
      timeout     = 30
      role_arn    = var.lambda_role_arns.quota_checker
      environment = {
        AWS_REGION_NAME         = local.region
        S3_BUCKET               = var.s3_assets_bucket_name
        DYNAMODB_JOBS_TABLE     = var.dynamodb_jobs_table_name
        DYNAMODB_SETTINGS_TABLE = var.dynamodb_settings_table_name
        LOG_LEVEL               = var.log_level
      }
    }
    # Review Video Pipeline Lambdas
    review_fetcher = {
      name        = "${var.project_name}-review-fetcher"
      description = "Fetches manga content from Vietnamese sites for review video"
      handler     = "src.review_fetcher.handler.handler"
      memory_size = 1024  # Higher memory for web scraping
      timeout     = 900
      role_arn    = var.lambda_role_arns.review_fetcher
      environment = {
        AWS_REGION_NAME         = local.region
        S3_BUCKET               = var.s3_assets_bucket_name
        DYNAMODB_JOBS_TABLE     = var.dynamodb_jobs_table_name
        DYNAMODB_SETTINGS_TABLE = var.dynamodb_settings_table_name
        LOG_LEVEL               = var.log_level
      }
    }
    review_scriptgen = {
      name        = "${var.project_name}-review-scriptgen"
      description = "Generates Vietnamese review scripts using DeepInfra LLM"
      handler     = "src.review_scriptgen.handler.handler"
      memory_size = 512
      timeout     = 900
      role_arn    = var.lambda_role_arns.review_scriptgen
      environment = {
        AWS_REGION_NAME         = local.region
        S3_BUCKET               = var.s3_assets_bucket_name
        DYNAMODB_JOBS_TABLE     = var.dynamodb_jobs_table_name
        DYNAMODB_SETTINGS_TABLE = var.dynamodb_settings_table_name
        DEEPINFRA_SECRET_NAME   = var.deepinfra_api_key_secret_name
        LOG_LEVEL               = var.log_level
      }
    }
  }
}
