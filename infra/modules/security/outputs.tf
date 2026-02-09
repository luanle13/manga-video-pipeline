# =============================================================================
# Security Module - Outputs
# =============================================================================

# =============================================================================
# Lambda IAM Role ARNs
# =============================================================================

output "lambda_fetcher_role_arn" {
  description = "ARN of the manga fetcher Lambda execution role"
  value       = aws_iam_role.lambda_fetcher.arn
}

output "lambda_fetcher_role_name" {
  description = "Name of the manga fetcher Lambda execution role"
  value       = aws_iam_role.lambda_fetcher.name
}

output "lambda_scriptgen_role_arn" {
  description = "ARN of the script generator Lambda execution role"
  value       = aws_iam_role.lambda_scriptgen.arn
}

output "lambda_scriptgen_role_name" {
  description = "Name of the script generator Lambda execution role"
  value       = aws_iam_role.lambda_scriptgen.name
}

output "lambda_ttsgen_role_arn" {
  description = "ARN of the TTS generator Lambda execution role"
  value       = aws_iam_role.lambda_ttsgen.arn
}

output "lambda_ttsgen_role_name" {
  description = "Name of the TTS generator Lambda execution role"
  value       = aws_iam_role.lambda_ttsgen.name
}

output "lambda_cleanup_role_arn" {
  description = "ARN of the cleanup Lambda execution role"
  value       = aws_iam_role.lambda_cleanup.arn
}

output "lambda_cleanup_role_name" {
  description = "Name of the cleanup Lambda execution role"
  value       = aws_iam_role.lambda_cleanup.name
}

output "lambda_quota_checker_role_arn" {
  description = "ARN of the quota checker Lambda execution role"
  value       = aws_iam_role.lambda_quota_checker.arn
}

output "lambda_quota_checker_role_name" {
  description = "Name of the quota checker Lambda execution role"
  value       = aws_iam_role.lambda_quota_checker.name
}

# =============================================================================
# EC2 IAM Role ARNs and Instance Profiles
# =============================================================================

output "ec2_renderer_role_arn" {
  description = "ARN of the EC2 Spot renderer instance role"
  value       = aws_iam_role.ec2_renderer.arn
}

output "ec2_renderer_role_name" {
  description = "Name of the EC2 Spot renderer instance role"
  value       = aws_iam_role.ec2_renderer.name
}

output "ec2_renderer_instance_profile_arn" {
  description = "ARN of the EC2 Spot renderer instance profile"
  value       = aws_iam_instance_profile.ec2_renderer.arn
}

output "ec2_renderer_instance_profile_name" {
  description = "Name of the EC2 Spot renderer instance profile"
  value       = aws_iam_instance_profile.ec2_renderer.name
}

output "dashboard_ec2_role_arn" {
  description = "ARN of the dashboard EC2 instance role"
  value       = aws_iam_role.dashboard_ec2.arn
}

output "dashboard_ec2_role_name" {
  description = "Name of the dashboard EC2 instance role"
  value       = aws_iam_role.dashboard_ec2.name
}

output "dashboard_ec2_instance_profile_arn" {
  description = "ARN of the dashboard EC2 instance profile"
  value       = aws_iam_instance_profile.dashboard_ec2.arn
}

output "dashboard_ec2_instance_profile_name" {
  description = "Name of the dashboard EC2 instance profile"
  value       = aws_iam_instance_profile.dashboard_ec2.name
}

# =============================================================================
# Step Functions IAM Role ARN
# =============================================================================

output "step_functions_role_arn" {
  description = "ARN of the Step Functions execution role"
  value       = aws_iam_role.step_functions.arn
}

output "step_functions_role_name" {
  description = "Name of the Step Functions execution role"
  value       = aws_iam_role.step_functions.name
}

# =============================================================================
# EventBridge IAM Role ARN
# =============================================================================

output "eventbridge_role_arn" {
  description = "ARN of the EventBridge execution role"
  value       = aws_iam_role.eventbridge.arn
}

output "eventbridge_role_name" {
  description = "Name of the EventBridge execution role"
  value       = aws_iam_role.eventbridge.name
}

# =============================================================================
# Combined Outputs
# =============================================================================

output "lambda_role_arns" {
  description = "Map of all Lambda execution role ARNs"
  value = {
    manga_fetcher    = aws_iam_role.lambda_fetcher.arn
    script_generator = aws_iam_role.lambda_scriptgen.arn
    tts_processor    = aws_iam_role.lambda_ttsgen.arn
    quota_checker    = aws_iam_role.lambda_quota_checker.arn
    cleanup          = aws_iam_role.lambda_cleanup.arn
  }
}

output "lambda_role_names" {
  description = "Map of all Lambda execution role names"
  value = {
    manga_fetcher    = aws_iam_role.lambda_fetcher.name
    script_generator = aws_iam_role.lambda_scriptgen.name
    tts_processor    = aws_iam_role.lambda_ttsgen.name
    quota_checker    = aws_iam_role.lambda_quota_checker.name
    cleanup          = aws_iam_role.lambda_cleanup.name
  }
}

output "ec2_instance_profile_arns" {
  description = "Map of EC2 instance profile ARNs"
  value = {
    renderer  = aws_iam_instance_profile.ec2_renderer.arn
    dashboard = aws_iam_instance_profile.dashboard_ec2.arn
  }
}

output "ec2_instance_profile_names" {
  description = "Map of EC2 instance profile names"
  value = {
    renderer  = aws_iam_instance_profile.ec2_renderer.name
    dashboard = aws_iam_instance_profile.dashboard_ec2.name
  }
}

# =============================================================================
# Secrets Manager Outputs
# =============================================================================

output "deepinfra_secret_arn" {
  description = "ARN of the DeepInfra API key secret"
  value       = aws_secretsmanager_secret.deepinfra_api_key.arn
}

output "deepinfra_secret_name" {
  description = "Name of the DeepInfra API key secret"
  value       = aws_secretsmanager_secret.deepinfra_api_key.name
}

output "youtube_oauth_secret_arn" {
  description = "ARN of the YouTube OAuth secret"
  value       = aws_secretsmanager_secret.youtube_oauth.arn
}

output "youtube_oauth_secret_name" {
  description = "Name of the YouTube OAuth secret"
  value       = aws_secretsmanager_secret.youtube_oauth.name
}

output "admin_credentials_secret_arn" {
  description = "ARN of the admin credentials secret"
  value       = aws_secretsmanager_secret.admin_credentials.arn
}

output "admin_credentials_secret_name" {
  description = "Name of the admin credentials secret"
  value       = aws_secretsmanager_secret.admin_credentials.name
}

output "jwt_secret_arn" {
  description = "ARN of the JWT signing key secret"
  value       = aws_secretsmanager_secret.jwt_secret.arn
}

output "jwt_secret_name" {
  description = "Name of the JWT signing key secret"
  value       = aws_secretsmanager_secret.jwt_secret.name
}

output "secret_arns" {
  description = "Map of all Secrets Manager secret ARNs"
  value = {
    deepinfra_api_key = aws_secretsmanager_secret.deepinfra_api_key.arn
    youtube_oauth     = aws_secretsmanager_secret.youtube_oauth.arn
    admin_credentials = aws_secretsmanager_secret.admin_credentials.arn
    jwt_secret        = aws_secretsmanager_secret.jwt_secret.arn
    mangadex          = var.mangadex_secret_name != "" ? aws_secretsmanager_secret.mangadex[0].arn : null
  }
}

# =============================================================================
# Security Summary
# =============================================================================

output "security_summary" {
  description = "Summary of security resources created"
  value = {
    lambda_roles = {
      manga_fetcher    = aws_iam_role.lambda_fetcher.name
      script_generator = aws_iam_role.lambda_scriptgen.name
      tts_processor    = aws_iam_role.lambda_ttsgen.name
      quota_checker    = aws_iam_role.lambda_quota_checker.name
      cleanup          = aws_iam_role.lambda_cleanup.name
    }
    ec2_roles = {
      renderer  = aws_iam_role.ec2_renderer.name
      dashboard = aws_iam_role.dashboard_ec2.name
    }
    orchestration_roles = {
      step_functions = aws_iam_role.step_functions.name
      eventbridge    = aws_iam_role.eventbridge.name
    }
    instance_profiles = {
      renderer  = aws_iam_instance_profile.ec2_renderer.name
      dashboard = aws_iam_instance_profile.dashboard_ec2.name
    }
    secrets = {
      deepinfra_api_key = aws_secretsmanager_secret.deepinfra_api_key.name
      youtube_oauth     = aws_secretsmanager_secret.youtube_oauth.name
      admin_credentials = aws_secretsmanager_secret.admin_credentials.name
      jwt_secret        = aws_secretsmanager_secret.jwt_secret.name
    }
  }
}
