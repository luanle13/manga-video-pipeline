# =============================================================================
# VPC Configuration
# =============================================================================
# Uses the default VPC for cost savings (no NAT gateway needed).
# All instances use public subnets with direct internet access.
# This is acceptable for this use case because:
# - Renderer instances only need outbound access (S3, YouTube API)
# - Dashboard is protected by security group (admin IP only)
# - No sensitive data is stored on the instances
# =============================================================================

# =============================================================================
# Default VPC Lookup
# =============================================================================

data "aws_vpc" "default" {
  default = true
}

data "aws_subnets" "default" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.default.id]
  }

  filter {
    name   = "default-for-az"
    values = ["true"]
  }
}

# Get subnet details for AZ distribution
data "aws_subnet" "default" {
  for_each = toset(data.aws_subnets.default.ids)
  id       = each.value
}

# =============================================================================
# Availability Zone Selection
# =============================================================================
# Select subnets in different AZs for better availability
# Prioritize AZs with lower Spot pricing (usually a, b, c)

locals {
  # Sort subnets by AZ name for consistent selection
  sorted_subnets = sort(data.aws_subnets.default.ids)

  # Use first 2 subnets for multi-AZ deployment
  selected_subnet_ids = slice(local.sorted_subnets, 0, min(2, length(local.sorted_subnets)))

  # Primary subnet for single-instance resources (dashboard)
  primary_subnet_id = local.sorted_subnets[0]

  # Map of subnet ID to AZ
  subnet_az_map = {
    for id, subnet in data.aws_subnet.default : id => subnet.availability_zone
  }
}
