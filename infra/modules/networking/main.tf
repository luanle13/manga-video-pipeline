# =============================================================================
# Networking Module - Data Sources and Locals
# =============================================================================

data "aws_caller_identity" "current" {}
data "aws_region" "current" {}

locals {
  account_id = data.aws_caller_identity.current.account_id
  region     = data.aws_region.current.name

  # Common tags for all networking resources
  common_tags = merge(
    var.tags,
    {
      Project    = var.project_name
      Module     = "networking"
      ManagedBy  = "terraform"
      Owner      = "DevOps"
      Repository = "manga-video-pipeline"
    }
  )

  # Combine admin_ip with additional allowed IPs for dashboard access
  dashboard_allowed_cidrs = concat([var.admin_ip], var.allowed_ip_ranges)
}
