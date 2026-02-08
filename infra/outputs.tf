# =============================================================================
# S3 Outputs
# =============================================================================

output "s3_bucket_name" {
  description = "Name of the S3 bucket for temporary assets"
  value       = module.storage.s3_assets_bucket_id
}

output "s3_bucket_arn" {
  description = "ARN of the S3 bucket for temporary assets"
  value       = module.storage.s3_assets_bucket_arn
}

output "s3_bucket_regional_domain_name" {
  description = "Regional domain name of the S3 bucket"
  value       = module.storage.s3_assets_bucket_regional_domain_name
}

# =============================================================================
# DynamoDB Outputs
# =============================================================================

output "dynamodb_table_name" {
  description = "Name of the DynamoDB table for job tracking"
  value       = module.storage.dynamodb_jobs_table_name
}

output "dynamodb_table_arn" {
  description = "ARN of the DynamoDB table for job tracking"
  value       = module.storage.dynamodb_jobs_table_arn
}

output "dynamodb_table_names" {
  description = "Map of all DynamoDB table names"
  value       = module.storage.dynamodb_table_names
}

# =============================================================================
# Storage Module Summary
# =============================================================================

output "storage_summary" {
  description = "Summary of storage resources"
  value       = module.storage.storage_summary
}

# =============================================================================
# IAM Role Outputs
# =============================================================================

output "lambda_role_arns" {
  description = "Map of Lambda execution role ARNs"
  value       = module.security.lambda_role_arns
}

output "lambda_role_names" {
  description = "Map of Lambda execution role names"
  value       = module.security.lambda_role_names
}

output "ec2_instance_profile_arns" {
  description = "Map of EC2 instance profile ARNs"
  value       = module.security.ec2_instance_profile_arns
}

output "ec2_instance_profile_names" {
  description = "Map of EC2 instance profile names"
  value       = module.security.ec2_instance_profile_names
}

output "step_functions_role_arn" {
  description = "ARN of the Step Functions execution role"
  value       = module.security.step_functions_role_arn
}

output "eventbridge_role_arn" {
  description = "ARN of the EventBridge execution role"
  value       = module.security.eventbridge_role_arn
}

output "security_summary" {
  description = "Summary of IAM roles created"
  value       = module.security.security_summary
}

# =============================================================================
# Future Infrastructure Outputs (to be implemented)
# =============================================================================
# Lambda functions, Step Functions, EC2, EventBridge, Secrets Manager,
# CloudWatch, VPC, Budget, etc. will be added as additional modules are created
