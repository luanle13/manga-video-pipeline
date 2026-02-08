# =============================================================================
# S3 Outputs
# =============================================================================

output "s3_assets_bucket_id" {
  description = "ID (name) of the S3 assets bucket"
  value       = aws_s3_bucket.assets.id
}

output "s3_assets_bucket_arn" {
  description = "ARN of the S3 assets bucket"
  value       = aws_s3_bucket.assets.arn
}

output "s3_assets_bucket_domain_name" {
  description = "Bucket domain name for the assets bucket"
  value       = aws_s3_bucket.assets.bucket_domain_name
}

output "s3_assets_bucket_regional_domain_name" {
  description = "Regional domain name of the assets bucket"
  value       = aws_s3_bucket.assets.bucket_regional_domain_name
}

# =============================================================================
# DynamoDB Outputs - manga_jobs
# =============================================================================

output "dynamodb_jobs_table_name" {
  description = "Name of the manga_jobs DynamoDB table"
  value       = aws_dynamodb_table.manga_jobs.name
}

output "dynamodb_jobs_table_arn" {
  description = "ARN of the manga_jobs DynamoDB table"
  value       = aws_dynamodb_table.manga_jobs.arn
}

output "dynamodb_jobs_table_id" {
  description = "ID of the manga_jobs DynamoDB table"
  value       = aws_dynamodb_table.manga_jobs.id
}

output "dynamodb_jobs_gsi_name" {
  description = "Name of the status-created GSI on manga_jobs table"
  value       = "status-created-index"
}

output "dynamodb_jobs_stream_arn" {
  description = "ARN of the DynamoDB stream for manga_jobs table (if enabled)"
  value       = try(aws_dynamodb_table.manga_jobs.stream_arn, null)
}

# =============================================================================
# DynamoDB Outputs - processed_manga
# =============================================================================

output "dynamodb_processed_manga_table_name" {
  description = "Name of the processed_manga DynamoDB table"
  value       = aws_dynamodb_table.processed_manga.name
}

output "dynamodb_processed_manga_table_arn" {
  description = "ARN of the processed_manga DynamoDB table"
  value       = aws_dynamodb_table.processed_manga.arn
}

output "dynamodb_processed_manga_table_id" {
  description = "ID of the processed_manga DynamoDB table"
  value       = aws_dynamodb_table.processed_manga.id
}

# =============================================================================
# DynamoDB Outputs - settings
# =============================================================================

output "dynamodb_settings_table_name" {
  description = "Name of the settings DynamoDB table"
  value       = aws_dynamodb_table.settings.name
}

output "dynamodb_settings_table_arn" {
  description = "ARN of the settings DynamoDB table"
  value       = aws_dynamodb_table.settings.arn
}

output "dynamodb_settings_table_id" {
  description = "ID of the settings DynamoDB table"
  value       = aws_dynamodb_table.settings.id
}

# =============================================================================
# Combined Outputs
# =============================================================================

output "dynamodb_table_names" {
  description = "Map of all DynamoDB table names"
  value = {
    jobs            = aws_dynamodb_table.manga_jobs.name
    processed_manga = aws_dynamodb_table.processed_manga.name
    settings        = aws_dynamodb_table.settings.name
  }
}

output "dynamodb_table_arns" {
  description = "Map of all DynamoDB table ARNs"
  value = {
    jobs            = aws_dynamodb_table.manga_jobs.arn
    processed_manga = aws_dynamodb_table.processed_manga.arn
    settings        = aws_dynamodb_table.settings.arn
  }
}

output "storage_summary" {
  description = "Summary of storage resources created"
  value = {
    s3_bucket = {
      name           = aws_s3_bucket.assets.id
      arn            = aws_s3_bucket.assets.arn
      lifecycle_days = var.assets_lifecycle_days
      versioning     = "Disabled"
      encryption     = "SSE-S3 (AES256)"
      public_access  = "Blocked"
    }

    dynamodb_tables = {
      jobs = {
        name                   = aws_dynamodb_table.manga_jobs.name
        billing_mode           = "PAY_PER_REQUEST"
        point_in_time_recovery = var.enable_point_in_time_recovery
        gsi                    = "status-created-index"
      }
      processed_manga = {
        name                   = aws_dynamodb_table.processed_manga.name
        billing_mode           = "PAY_PER_REQUEST"
        point_in_time_recovery = var.enable_point_in_time_recovery
      }
      settings = {
        name                   = aws_dynamodb_table.settings.name
        billing_mode           = "PAY_PER_REQUEST"
        point_in_time_recovery = var.enable_point_in_time_recovery
      }
    }
  }
}
