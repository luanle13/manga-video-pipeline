# Data source for AWS account ID
data "aws_caller_identity" "current" {}

# Data source for AWS region
data "aws_region" "current" {}

# Local values for consistent naming
locals {
  account_id = data.aws_caller_identity.current.account_id
  region     = data.aws_region.current.name

  # Common tags
  common_tags = merge(
    var.tags,
    {
      Module = "storage"
    }
  )
}
