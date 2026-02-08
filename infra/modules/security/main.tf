# =============================================================================
# Security Module - Data Sources
# =============================================================================

data "aws_caller_identity" "current" {}
data "aws_region" "current" {}

locals {
  account_id = data.aws_caller_identity.current.account_id
  region     = data.aws_region.current.name

  # Common tags for all IAM resources
  common_tags = merge(
    var.tags,
    {
      Project    = var.project_name
      Module     = "security"
      ManagedBy  = "terraform"
      Owner      = "DevOps"
      Repository = "manga-video-pipeline"
    }
  )
}
