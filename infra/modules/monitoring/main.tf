# =============================================================================
# Monitoring Module - Main Configuration
# =============================================================================
# CloudWatch alarms, dashboard, and log groups for manga video pipeline
# =============================================================================

terraform {
  required_version = ">= 1.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

# =============================================================================
# Data Sources
# =============================================================================

data "aws_caller_identity" "current" {}
data "aws_region" "current" {}

# =============================================================================
# Local Values
# =============================================================================

locals {
  account_id = data.aws_caller_identity.current.account_id
  region     = data.aws_region.current.name

  # Common tags for all monitoring resources
  common_tags = merge(
    var.tags,
    {
      Project     = var.project_name
      Environment = var.environment
      Module      = "monitoring"
      ManagedBy   = "terraform"
    }
  )

  # Lambda function names for alarm configuration
  lambda_functions = {
    manga_fetcher    = "${var.project_name}-manga-fetcher"
    script_generator = "${var.project_name}-script-generator"
    tts_processor    = "${var.project_name}-tts-processor"
    quota_checker    = "${var.project_name}-quota-checker"
    cleanup          = "${var.project_name}-cleanup"
  }
}
