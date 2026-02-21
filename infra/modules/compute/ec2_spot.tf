# =============================================================================
# EC2 Spot Launch Template for Video Renderer
# =============================================================================
# Creates a launch template for Spot instances that render videos.
# Instances are ephemeral - they process a single job and terminate.
# =============================================================================

# =============================================================================
# AMI Lookup - Amazon Linux 2023 (x86_64)
# =============================================================================
# Using x86_64 for c5 instances (c5 doesn't support arm64)
# Amazon Linux 2023 is optimized for AWS and includes recent Python

data "aws_ami" "amazon_linux_2023" {
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
# EC2 Launch Template for Spot Renderer
# =============================================================================

resource "aws_launch_template" "renderer" {
  name        = "${var.project_name}-renderer"
  description = "Launch template for video renderer Spot instances"

  # Instance configuration
  image_id      = data.aws_ami.amazon_linux_2023.id
  instance_type = var.spot_instance_type

  # IAM instance profile
  iam_instance_profile {
    name = var.ec2_instance_profile_names.renderer
  }

  # Network configuration
  network_interfaces {
    associate_public_ip_address = true
    security_groups             = [var.renderer_security_group_id]
    delete_on_termination       = true
  }

  # Storage configuration - 50GB gp3 root volume
  block_device_mappings {
    device_name = "/dev/xvda"

    ebs {
      volume_size           = 50
      volume_type           = "gp3"
      iops                  = 3000
      throughput            = 125
      delete_on_termination = true
      encrypted             = true
    }
  }

  # Spot instance configuration
  instance_market_options {
    market_type = "spot"

    spot_options {
      # Use on-demand price as max - let market decide actual price
      max_price          = var.spot_max_price != "" ? var.spot_max_price : null
      spot_instance_type = "one-time"
      # Don't use persistent - we want instances to terminate when done
      instance_interruption_behavior = var.spot_interruption_behavior
    }
  }

  # Metadata configuration (IMDSv2 for security)
  metadata_options {
    http_endpoint               = "enabled"
    http_tokens                 = "required" # IMDSv2 only
    http_put_response_hop_limit = 1
    instance_metadata_tags      = "enabled"
  }

  # Monitoring
  monitoring {
    enabled = var.enable_detailed_monitoring
  }

  # User data script - installs dependencies and runs renderer
  user_data = base64encode(templatefile("${path.module}/templates/renderer_userdata.sh.tpl", {
    region                  = local.region
    project_name            = var.project_name
    s3_bucket               = var.s3_assets_bucket_name
    dynamodb_jobs_table     = var.dynamodb_jobs_table_name
    dynamodb_settings_table = var.dynamodb_settings_table_name
    youtube_secret_name     = var.youtube_credentials_secret_name
    cleanup_function_name   = var.cleanup_function_name
    log_level               = var.log_level
    activity_arn            = aws_sfn_activity.renderer.id
  }))

  # Instance tags
  tag_specifications {
    resource_type = "instance"
    tags = merge(
      local.common_tags,
      {
        Name      = "${var.project_name}-renderer"
        Component = "renderer"
        ManagedBy = var.project_name
      }
    )
  }

  tag_specifications {
    resource_type = "volume"
    tags = merge(
      local.common_tags,
      {
        Name      = "${var.project_name}-renderer-volume"
        Component = "renderer"
      }
    )
  }

  tags = merge(
    local.common_tags,
    {
      Name      = "${var.project_name}-renderer-lt"
      Component = "renderer"
    }
  )

  lifecycle {
    create_before_destroy = true
  }
}

# =============================================================================
# CloudWatch Log Group for Renderer
# =============================================================================

resource "aws_cloudwatch_log_group" "renderer" {
  name              = "/aws/ec2/${var.project_name}-renderer"
  retention_in_days = var.log_retention_days

  tags = merge(
    local.common_tags,
    {
      Name      = "${var.project_name}-renderer-logs"
      Component = "renderer"
    }
  )
}

# =============================================================================
# SSM Parameter for Job ID
# =============================================================================
# Step Functions writes the job_id here before launching the instance.
# The renderer reads it on startup.

resource "aws_ssm_parameter" "renderer_job_id" {
  name        = "/${var.project_name}/renderer/current-job-id"
  description = "Current job ID for renderer instance (written by Step Functions)"
  type        = "String"
  value       = "none" # Placeholder - Step Functions updates this

  tags = merge(
    local.common_tags,
    {
      Name      = "${var.project_name}-renderer-job-id"
      Component = "renderer"
    }
  )

  lifecycle {
    ignore_changes = [value] # Value is managed by Step Functions
  }
}

# Note: Task token is now retrieved via GetActivityTask, not SSM
