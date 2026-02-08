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
# Future Infrastructure Outputs (to be implemented)
# =============================================================================
# Lambda functions, Step Functions, EC2, EventBridge, Secrets Manager,
# CloudWatch, VPC, Budget, etc. will be added as additional modules are created
