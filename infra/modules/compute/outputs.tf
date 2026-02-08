# =============================================================================
# Compute Module - Outputs
# =============================================================================

# =============================================================================
# Lambda Function ARNs
# =============================================================================

output "manga_fetcher_function_arn" {
  description = "ARN of the manga fetcher Lambda function"
  value       = aws_lambda_function.manga_fetcher.arn
}

output "manga_fetcher_function_name" {
  description = "Name of the manga fetcher Lambda function"
  value       = aws_lambda_function.manga_fetcher.function_name
}

output "script_generator_function_arn" {
  description = "ARN of the script generator Lambda function"
  value       = aws_lambda_function.script_generator.arn
}

output "script_generator_function_name" {
  description = "Name of the script generator Lambda function"
  value       = aws_lambda_function.script_generator.function_name
}

output "tts_processor_function_arn" {
  description = "ARN of the TTS processor Lambda function"
  value       = aws_lambda_function.tts_processor.arn
}

output "tts_processor_function_name" {
  description = "Name of the TTS processor Lambda function"
  value       = aws_lambda_function.tts_processor.function_name
}

output "cleanup_function_arn" {
  description = "ARN of the cleanup Lambda function"
  value       = aws_lambda_function.cleanup.arn
}

output "cleanup_function_name" {
  description = "Name of the cleanup Lambda function"
  value       = aws_lambda_function.cleanup.function_name
}

output "quota_checker_function_arn" {
  description = "ARN of the quota checker Lambda function"
  value       = aws_lambda_function.quota_checker.arn
}

output "quota_checker_function_name" {
  description = "Name of the quota checker Lambda function"
  value       = aws_lambda_function.quota_checker.function_name
}

# =============================================================================
# Lambda Invoke ARNs (for Step Functions)
# =============================================================================

output "manga_fetcher_invoke_arn" {
  description = "Invoke ARN of the manga fetcher Lambda function"
  value       = aws_lambda_function.manga_fetcher.invoke_arn
}

output "script_generator_invoke_arn" {
  description = "Invoke ARN of the script generator Lambda function"
  value       = aws_lambda_function.script_generator.invoke_arn
}

output "tts_processor_invoke_arn" {
  description = "Invoke ARN of the TTS processor Lambda function"
  value       = aws_lambda_function.tts_processor.invoke_arn
}

output "cleanup_invoke_arn" {
  description = "Invoke ARN of the cleanup Lambda function"
  value       = aws_lambda_function.cleanup.invoke_arn
}

output "quota_checker_invoke_arn" {
  description = "Invoke ARN of the quota checker Lambda function"
  value       = aws_lambda_function.quota_checker.invoke_arn
}

# =============================================================================
# CloudWatch Log Group ARNs
# =============================================================================

output "manga_fetcher_log_group_arn" {
  description = "ARN of the manga fetcher CloudWatch log group"
  value       = aws_cloudwatch_log_group.manga_fetcher.arn
}

output "script_generator_log_group_arn" {
  description = "ARN of the script generator CloudWatch log group"
  value       = aws_cloudwatch_log_group.script_generator.arn
}

output "tts_processor_log_group_arn" {
  description = "ARN of the TTS processor CloudWatch log group"
  value       = aws_cloudwatch_log_group.tts_processor.arn
}

output "cleanup_log_group_arn" {
  description = "ARN of the cleanup CloudWatch log group"
  value       = aws_cloudwatch_log_group.cleanup.arn
}

output "quota_checker_log_group_arn" {
  description = "ARN of the quota checker CloudWatch log group"
  value       = aws_cloudwatch_log_group.quota_checker.arn
}

# =============================================================================
# Combined Outputs
# =============================================================================

output "lambda_function_arns" {
  description = "Map of all Lambda function ARNs"
  value = {
    manga_fetcher    = aws_lambda_function.manga_fetcher.arn
    script_generator = aws_lambda_function.script_generator.arn
    tts_processor    = aws_lambda_function.tts_processor.arn
    cleanup          = aws_lambda_function.cleanup.arn
    quota_checker    = aws_lambda_function.quota_checker.arn
  }
}

output "lambda_function_names" {
  description = "Map of all Lambda function names"
  value = {
    manga_fetcher    = aws_lambda_function.manga_fetcher.function_name
    script_generator = aws_lambda_function.script_generator.function_name
    tts_processor    = aws_lambda_function.tts_processor.function_name
    cleanup          = aws_lambda_function.cleanup.function_name
    quota_checker    = aws_lambda_function.quota_checker.function_name
  }
}

output "lambda_invoke_arns" {
  description = "Map of all Lambda invoke ARNs (for Step Functions)"
  value = {
    manga_fetcher    = aws_lambda_function.manga_fetcher.invoke_arn
    script_generator = aws_lambda_function.script_generator.invoke_arn
    tts_processor    = aws_lambda_function.tts_processor.invoke_arn
    cleanup          = aws_lambda_function.cleanup.invoke_arn
    quota_checker    = aws_lambda_function.quota_checker.invoke_arn
  }
}

output "log_group_arns" {
  description = "Map of all CloudWatch log group ARNs"
  value = {
    manga_fetcher    = aws_cloudwatch_log_group.manga_fetcher.arn
    script_generator = aws_cloudwatch_log_group.script_generator.arn
    tts_processor    = aws_cloudwatch_log_group.tts_processor.arn
    cleanup          = aws_cloudwatch_log_group.cleanup.arn
    quota_checker    = aws_cloudwatch_log_group.quota_checker.arn
  }
}

output "log_group_names" {
  description = "Map of all CloudWatch log group names"
  value = {
    manga_fetcher    = aws_cloudwatch_log_group.manga_fetcher.name
    script_generator = aws_cloudwatch_log_group.script_generator.name
    tts_processor    = aws_cloudwatch_log_group.tts_processor.name
    cleanup          = aws_cloudwatch_log_group.cleanup.name
    quota_checker    = aws_cloudwatch_log_group.quota_checker.name
  }
}

# =============================================================================
# EC2 Spot Renderer Outputs
# =============================================================================

output "renderer_launch_template_id" {
  description = "ID of the renderer launch template"
  value       = aws_launch_template.renderer.id
}

output "renderer_launch_template_arn" {
  description = "ARN of the renderer launch template"
  value       = aws_launch_template.renderer.arn
}

output "renderer_launch_template_latest_version" {
  description = "Latest version of the renderer launch template"
  value       = aws_launch_template.renderer.latest_version
}

output "renderer_log_group_name" {
  description = "Name of the renderer CloudWatch log group"
  value       = aws_cloudwatch_log_group.renderer.name
}

output "renderer_job_id_parameter_name" {
  description = "SSM parameter name for renderer job ID"
  value       = aws_ssm_parameter.renderer_job_id.name
}

output "renderer_task_token_parameter_name" {
  description = "SSM parameter name for renderer task token"
  value       = aws_ssm_parameter.renderer_task_token.name
}

# =============================================================================
# EC2 Dashboard Outputs
# =============================================================================

output "dashboard_instance_id" {
  description = "ID of the dashboard EC2 instance"
  value       = aws_instance.dashboard.id
}

output "dashboard_private_ip" {
  description = "Private IP address of the dashboard instance"
  value       = aws_instance.dashboard.private_ip
}

output "dashboard_public_ip" {
  description = "Public IP address of the dashboard instance"
  value       = var.dashboard_enable_elastic_ip ? aws_eip.dashboard[0].public_ip : aws_instance.dashboard.public_ip
}

output "dashboard_public_dns" {
  description = "Public DNS name of the dashboard instance"
  value       = aws_instance.dashboard.public_dns
}

output "dashboard_elastic_ip" {
  description = "Elastic IP address (if enabled)"
  value       = var.dashboard_enable_elastic_ip ? aws_eip.dashboard[0].public_ip : null
}

output "dashboard_url" {
  description = "HTTPS URL to access the dashboard"
  value       = "https://${var.dashboard_enable_elastic_ip ? aws_eip.dashboard[0].public_ip : aws_instance.dashboard.public_ip}"
}

output "dashboard_nip_io_url" {
  description = "nip.io URL for the dashboard (no DNS required)"
  value       = "https://${var.dashboard_enable_elastic_ip ? aws_eip.dashboard[0].public_ip : aws_instance.dashboard.public_ip}.nip.io"
}

output "dashboard_log_group_name" {
  description = "Name of the dashboard CloudWatch log group"
  value       = aws_cloudwatch_log_group.dashboard.name
}

# =============================================================================
# Combined Summary
# =============================================================================

output "compute_summary" {
  description = "Summary of compute resources created"
  value = {
    lambda_functions = {
      manga_fetcher = {
        name        = aws_lambda_function.manga_fetcher.function_name
        arn         = aws_lambda_function.manga_fetcher.arn
        memory_mb   = aws_lambda_function.manga_fetcher.memory_size
        timeout_sec = aws_lambda_function.manga_fetcher.timeout
        runtime     = aws_lambda_function.manga_fetcher.runtime
        arch        = aws_lambda_function.manga_fetcher.architectures[0]
      }
      script_generator = {
        name        = aws_lambda_function.script_generator.function_name
        arn         = aws_lambda_function.script_generator.arn
        memory_mb   = aws_lambda_function.script_generator.memory_size
        timeout_sec = aws_lambda_function.script_generator.timeout
        runtime     = aws_lambda_function.script_generator.runtime
        arch        = aws_lambda_function.script_generator.architectures[0]
      }
      tts_processor = {
        name        = aws_lambda_function.tts_processor.function_name
        arn         = aws_lambda_function.tts_processor.arn
        memory_mb   = aws_lambda_function.tts_processor.memory_size
        timeout_sec = aws_lambda_function.tts_processor.timeout
        runtime     = aws_lambda_function.tts_processor.runtime
        arch        = aws_lambda_function.tts_processor.architectures[0]
      }
      cleanup = {
        name        = aws_lambda_function.cleanup.function_name
        arn         = aws_lambda_function.cleanup.arn
        memory_mb   = aws_lambda_function.cleanup.memory_size
        timeout_sec = aws_lambda_function.cleanup.timeout
        runtime     = aws_lambda_function.cleanup.runtime
        arch        = aws_lambda_function.cleanup.architectures[0]
      }
      quota_checker = {
        name        = aws_lambda_function.quota_checker.function_name
        arn         = aws_lambda_function.quota_checker.arn
        memory_mb   = aws_lambda_function.quota_checker.memory_size
        timeout_sec = aws_lambda_function.quota_checker.timeout
        runtime     = aws_lambda_function.quota_checker.runtime
        arch        = aws_lambda_function.quota_checker.architectures[0]
      }
    }
    ec2_renderer = {
      launch_template_id = aws_launch_template.renderer.id
      instance_type      = var.spot_instance_type
      spot_pricing       = var.spot_max_price != "" ? var.spot_max_price : "on-demand"
      root_volume_gb     = 50
    }
    ec2_dashboard = {
      instance_id    = aws_instance.dashboard.id
      instance_type  = var.dashboard_instance_type
      public_ip      = var.dashboard_enable_elastic_ip ? aws_eip.dashboard[0].public_ip : aws_instance.dashboard.public_ip
      elastic_ip     = var.dashboard_enable_elastic_ip
      root_volume_gb = 20
    }
    log_retention_days = var.log_retention_days
  }
}
