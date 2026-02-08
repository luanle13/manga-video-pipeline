# =============================================================================
# DynamoDB Table: manga_jobs
# =============================================================================
# Stores job records for the video processing pipeline
# Primary key: job_id
# GSI: status-created-index for querying jobs by status and creation time
# =============================================================================

resource "aws_dynamodb_table" "manga_jobs" {
  name         = "${var.project_name}-jobs"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "job_id"

  # Primary Key
  attribute {
    name = "job_id"
    type = "S"
  }

  # GSI Attributes
  attribute {
    name = "status"
    type = "S"
  }

  attribute {
    name = "created_at"
    type = "S"
  }

  # Global Secondary Index: Query jobs by status and creation time
  global_secondary_index {
    name            = "status-created-index"
    hash_key        = "status"
    range_key       = "created_at"
    projection_type = "ALL"
  }

  # Point-in-Time Recovery
  point_in_time_recovery {
    enabled = var.enable_point_in_time_recovery
  }

  # Server-Side Encryption (AWS owned key - no additional cost)
  server_side_encryption {
    enabled = true
  }

  # TTL for automatic cleanup of old jobs (optional)
  ttl {
    attribute_name = "ttl"
    enabled        = true
  }

  tags = merge(
    local.common_tags,
    {
      Name        = "${var.project_name}-jobs"
      Purpose     = "Job tracking for video processing pipeline"
      Environment = var.environment
    }
  )
}

# =============================================================================
# DynamoDB Table: processed_manga
# =============================================================================
# Stores metadata about processed manga
# Primary key: manga_id
# =============================================================================

resource "aws_dynamodb_table" "processed_manga" {
  name         = "${var.project_name}-processed-manga"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "manga_id"

  # Primary Key
  attribute {
    name = "manga_id"
    type = "S"
  }

  # Point-in-Time Recovery
  point_in_time_recovery {
    enabled = var.enable_point_in_time_recovery
  }

  # Server-Side Encryption (AWS owned key)
  server_side_encryption {
    enabled = true
  }

  tags = merge(
    local.common_tags,
    {
      Name        = "${var.project_name}-processed-manga"
      Purpose     = "Metadata for processed manga"
      Environment = var.environment
    }
  )
}

# =============================================================================
# DynamoDB Table: settings
# =============================================================================
# Stores pipeline configuration settings
# Primary key: setting_key
# =============================================================================

resource "aws_dynamodb_table" "settings" {
  name         = "${var.project_name}-settings"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "setting_key"

  # Primary Key
  attribute {
    name = "setting_key"
    type = "S"
  }

  # Point-in-Time Recovery
  point_in_time_recovery {
    enabled = var.enable_point_in_time_recovery
  }

  # Server-Side Encryption (AWS owned key)
  server_side_encryption {
    enabled = true
  }

  tags = merge(
    local.common_tags,
    {
      Name        = "${var.project_name}-settings"
      Purpose     = "Pipeline configuration settings"
      Environment = var.environment
    }
  )
}

# =============================================================================
# CloudWatch Contributor Insights (Optional - for monitoring)
# =============================================================================
# Uncomment to enable Contributor Insights for monitoring DynamoDB access patterns

# resource "aws_dynamodb_contributor_insights" "manga_jobs" {
#   table_name = aws_dynamodb_table.manga_jobs.name
# }

# resource "aws_dynamodb_contributor_insights" "processed_manga" {
#   table_name = aws_dynamodb_table.processed_manga.name
# }

# resource "aws_dynamodb_contributor_insights" "settings" {
#   table_name = aws_dynamodb_table.settings.name
# }
