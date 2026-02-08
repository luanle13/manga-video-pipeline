# =============================================================================
# Security Groups for Manga Video Pipeline
# =============================================================================

# =============================================================================
# 1. Renderer Security Group
# =============================================================================
# Used by EC2 Spot instances running video rendering.
# No inbound access needed - instances only make outbound connections.
# Outbound: All traffic (S3, YouTube API, pip packages, etc.)

resource "aws_security_group" "renderer" {
  name        = "${var.project_name}-renderer-sg"
  description = "Security group for video renderer Spot instances"
  vpc_id      = data.aws_vpc.default.id

  tags = merge(
    local.common_tags,
    {
      Name      = "${var.project_name}-renderer-sg"
      Component = "renderer"
    }
  )

  lifecycle {
    create_before_destroy = true
  }
}

# Renderer - Egress: Allow all outbound traffic
resource "aws_vpc_security_group_egress_rule" "renderer_all_outbound" {
  security_group_id = aws_security_group.renderer.id
  description       = "Allow all outbound traffic for S3, YouTube API, package downloads"

  ip_protocol = "-1"
  cidr_ipv4   = "0.0.0.0/0"

  tags = merge(
    local.common_tags,
    {
      Name = "${var.project_name}-renderer-egress-all"
    }
  )
}

# =============================================================================
# 2. Dashboard Security Group
# =============================================================================
# Used by the admin dashboard EC2 instance.
# Inbound: HTTPS (443) from admin IP only
# Outbound: All traffic (AWS APIs, package downloads, etc.)

resource "aws_security_group" "dashboard" {
  name        = "${var.project_name}-dashboard-sg"
  description = "Security group for admin dashboard instance"
  vpc_id      = data.aws_vpc.default.id

  tags = merge(
    local.common_tags,
    {
      Name      = "${var.project_name}-dashboard-sg"
      Component = "dashboard"
    }
  )

  lifecycle {
    create_before_destroy = true
  }
}

# Dashboard - Ingress: HTTPS from admin IP(s) only
resource "aws_vpc_security_group_ingress_rule" "dashboard_https" {
  for_each = toset(local.dashboard_allowed_cidrs)

  security_group_id = aws_security_group.dashboard.id
  description       = "Allow HTTPS from admin IP: ${each.value}"

  ip_protocol = "tcp"
  from_port   = 443
  to_port     = 443
  cidr_ipv4   = each.value

  tags = merge(
    local.common_tags,
    {
      Name = "${var.project_name}-dashboard-ingress-https-${replace(each.value, "/", "-")}"
    }
  )
}

# Dashboard - Ingress: HTTP from admin IP(s) for redirect to HTTPS
resource "aws_vpc_security_group_ingress_rule" "dashboard_http" {
  for_each = var.enable_http_redirect ? toset(local.dashboard_allowed_cidrs) : toset([])

  security_group_id = aws_security_group.dashboard.id
  description       = "Allow HTTP from admin IP for HTTPS redirect: ${each.value}"

  ip_protocol = "tcp"
  from_port   = 80
  to_port     = 80
  cidr_ipv4   = each.value

  tags = merge(
    local.common_tags,
    {
      Name = "${var.project_name}-dashboard-ingress-http-${replace(each.value, "/", "-")}"
    }
  )
}

# Dashboard - Ingress: SSH from admin IP (optional, for debugging)
resource "aws_vpc_security_group_ingress_rule" "dashboard_ssh" {
  count = var.enable_ssh_access ? 1 : 0

  security_group_id = aws_security_group.dashboard.id
  description       = "Allow SSH from admin IP for debugging"

  ip_protocol = "tcp"
  from_port   = 22
  to_port     = 22
  cidr_ipv4   = var.admin_ip

  tags = merge(
    local.common_tags,
    {
      Name = "${var.project_name}-dashboard-ingress-ssh"
    }
  )
}

# Dashboard - Egress: Allow all outbound traffic
resource "aws_vpc_security_group_egress_rule" "dashboard_all_outbound" {
  security_group_id = aws_security_group.dashboard.id
  description       = "Allow all outbound traffic for AWS APIs, package downloads"

  ip_protocol = "-1"
  cidr_ipv4   = "0.0.0.0/0"

  tags = merge(
    local.common_tags,
    {
      Name = "${var.project_name}-dashboard-egress-all"
    }
  )
}
