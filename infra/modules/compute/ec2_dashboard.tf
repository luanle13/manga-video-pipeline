# =============================================================================
# EC2 Dashboard Instance
# =============================================================================
# Creates a small EC2 instance to run the admin dashboard.
# Uses t3.micro for cost efficiency (Free Tier eligible).
# =============================================================================

# =============================================================================
# AMI Lookup - Amazon Linux 2023 (x86_64)
# =============================================================================
# Using same AMI as renderer for consistency

data "aws_ami" "dashboard_ami" {
  most_recent = true
  owners      = ["amazon"]

  filter {
    name   = "name"
    values = ["al2023-ami-2023.*-x86_64"]
  }

  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }

  filter {
    name   = "root-device-type"
    values = ["ebs"]
  }

  filter {
    name   = "architecture"
    values = ["x86_64"]
  }
}

# =============================================================================
# EC2 Dashboard Instance
# =============================================================================

resource "aws_instance" "dashboard" {
  ami           = data.aws_ami.dashboard_ami.id
  instance_type = var.dashboard_instance_type

  # Network configuration
  subnet_id                   = var.dashboard_subnet_id
  vpc_security_group_ids      = [var.dashboard_security_group_id]
  associate_public_ip_address = var.dashboard_enable_public_ip

  # IAM instance profile
  iam_instance_profile = var.ec2_instance_profile_names.dashboard

  # Storage - 20GB gp3 root volume
  root_block_device {
    volume_size           = 20
    volume_type           = "gp3"
    iops                  = 3000
    throughput            = 125
    delete_on_termination = true
    encrypted             = true

    tags = merge(
      local.common_tags,
      {
        Name      = "${var.project_name}-dashboard-root"
        Component = "dashboard"
      }
    )
  }

  # Metadata configuration (IMDSv2 for security)
  metadata_options {
    http_endpoint               = "enabled"
    http_tokens                 = "required"
    http_put_response_hop_limit = 1
    instance_metadata_tags      = "enabled"
  }

  # Monitoring
  monitoring = var.enable_detailed_monitoring

  # User data script
  user_data = base64encode(templatefile("${path.module}/templates/dashboard_userdata.sh.tpl", {
    region                   = local.region
    project_name             = var.project_name
    s3_bucket                = var.s3_assets_bucket_name
    dynamodb_jobs_table      = var.dynamodb_jobs_table_name
    dynamodb_processed_table = var.dynamodb_processed_manga_table_name
    dynamodb_settings_table  = var.dynamodb_settings_table_name
    admin_credentials_secret = var.admin_credentials_secret_name
    jwt_secret_name          = var.jwt_secret_name
    state_machine_arn        = var.state_machine_arn
    log_level                = var.log_level
    dashboard_domain         = var.dashboard_domain
  }))

  # Prevent accidental termination
  disable_api_termination = var.environment == "prod" ? true : false

  tags = merge(
    local.common_tags,
    {
      Name      = "${var.project_name}-dashboard"
      Component = "dashboard"
    }
  )

  lifecycle {
    ignore_changes = [
      ami,       # Don't replace instance on AMI updates
      user_data, # Don't replace instance on user data changes
    ]
  }
}

# =============================================================================
# Elastic IP for Dashboard (Optional)
# =============================================================================
# Provides a stable IP address for nip.io domain

resource "aws_eip" "dashboard" {
  count = var.dashboard_enable_elastic_ip ? 1 : 0

  domain = "vpc"

  tags = merge(
    local.common_tags,
    {
      Name      = "${var.project_name}-dashboard-eip"
      Component = "dashboard"
    }
  )
}

resource "aws_eip_association" "dashboard" {
  count = var.dashboard_enable_elastic_ip ? 1 : 0

  instance_id   = aws_instance.dashboard.id
  allocation_id = aws_eip.dashboard[0].id
}

# =============================================================================
# CloudWatch Log Group for Dashboard
# =============================================================================

resource "aws_cloudwatch_log_group" "dashboard" {
  name              = "/aws/ec2/${var.project_name}-dashboard"
  retention_in_days = var.log_retention_days

  tags = merge(
    local.common_tags,
    {
      Name      = "${var.project_name}-dashboard-logs"
      Component = "dashboard"
    }
  )
}
