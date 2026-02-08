# =============================================================================
# Networking Module - Outputs
# =============================================================================

# =============================================================================
# VPC Outputs
# =============================================================================

output "vpc_id" {
  description = "ID of the VPC (default VPC)"
  value       = data.aws_vpc.default.id
}

output "vpc_cidr_block" {
  description = "CIDR block of the VPC"
  value       = data.aws_vpc.default.cidr_block
}

# =============================================================================
# Subnet Outputs
# =============================================================================

output "subnet_ids" {
  description = "List of subnet IDs in the VPC"
  value       = data.aws_subnets.default.ids
}

output "selected_subnet_ids" {
  description = "Selected subnet IDs for multi-AZ deployment"
  value       = local.selected_subnet_ids
}

output "primary_subnet_id" {
  description = "Primary subnet ID for single-instance resources"
  value       = local.primary_subnet_id
}

output "subnet_az_map" {
  description = "Map of subnet IDs to availability zones"
  value       = local.subnet_az_map
}

# =============================================================================
# Security Group Outputs
# =============================================================================

output "renderer_security_group_id" {
  description = "ID of the renderer security group"
  value       = aws_security_group.renderer.id
}

output "renderer_security_group_arn" {
  description = "ARN of the renderer security group"
  value       = aws_security_group.renderer.arn
}

output "dashboard_security_group_id" {
  description = "ID of the dashboard security group"
  value       = aws_security_group.dashboard.id
}

output "dashboard_security_group_arn" {
  description = "ARN of the dashboard security group"
  value       = aws_security_group.dashboard.arn
}

# =============================================================================
# Combined Outputs
# =============================================================================

output "security_group_ids" {
  description = "Map of security group IDs"
  value = {
    renderer  = aws_security_group.renderer.id
    dashboard = aws_security_group.dashboard.id
  }
}

output "networking_summary" {
  description = "Summary of networking resources"
  value = {
    vpc = {
      id         = data.aws_vpc.default.id
      cidr_block = data.aws_vpc.default.cidr_block
      is_default = true
    }
    subnets = {
      total_count    = length(data.aws_subnets.default.ids)
      selected_count = length(local.selected_subnet_ids)
      primary_id     = local.primary_subnet_id
    }
    security_groups = {
      renderer = {
        id          = aws_security_group.renderer.id
        name        = aws_security_group.renderer.name
        description = "No inbound, all outbound"
      }
      dashboard = {
        id          = aws_security_group.dashboard.id
        name        = aws_security_group.dashboard.name
        description = "HTTPS from admin IP only"
      }
    }
    access_control = {
      admin_ip         = var.admin_ip
      allowed_ip_count = length(var.allowed_ip_ranges)
      ssh_enabled      = var.enable_ssh_access
      http_redirect    = var.enable_http_redirect
    }
  }
}
