# =============================================================================
# S3 Bucket for Temporary Assets
# =============================================================================
# This bucket stores temporary files during video processing:
# - Downloaded manga panel images
# - Generated script files
# - TTS audio segments
# - Intermediate rendering files
#
# All objects are automatically deleted after 7 days as a safety net.
# =============================================================================

resource "aws_s3_bucket" "assets" {
  bucket = "${var.project_name}-assets-${local.account_id}"

  tags = merge(
    local.common_tags,
    {
      Name        = "${var.project_name}-assets-${local.account_id}"
      Purpose     = "Temporary storage for video processing assets"
      Retention   = "${var.assets_lifecycle_days} days"
      Environment = var.environment
    }
  )
}

# =============================================================================
# Block All Public Access
# =============================================================================

resource "aws_s3_bucket_public_access_block" "assets" {
  bucket = aws_s3_bucket.assets.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# =============================================================================
# Server-Side Encryption (SSE-S3)
# =============================================================================

resource "aws_s3_bucket_server_side_encryption_configuration" "assets" {
  bucket = aws_s3_bucket.assets.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
    bucket_key_enabled = true
  }
}

# =============================================================================
# Lifecycle Rule - Delete After 7 Days
# =============================================================================

resource "aws_s3_bucket_lifecycle_configuration" "assets" {
  bucket = aws_s3_bucket.assets.id

  rule {
    id     = "delete-old-temp-files"
    status = "Enabled"

    # Delete all objects after specified days
    expiration {
      days = var.assets_lifecycle_days
    }

    # Also delete incomplete multipart uploads after 1 day
    abort_incomplete_multipart_upload {
      days_after_initiation = 1
    }

    filter {
      # Apply to all objects
      prefix = ""
    }
  }
}

# =============================================================================
# Versioning - Disabled for Temp Files
# =============================================================================

resource "aws_s3_bucket_versioning" "assets" {
  bucket = aws_s3_bucket.assets.id

  versioning_configuration {
    status = "Disabled"
  }
}

# =============================================================================
# Bucket Policy - Enforce HTTPS Only
# =============================================================================

resource "aws_s3_bucket_policy" "assets" {
  bucket = aws_s3_bucket.assets.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid       = "DenyInsecureTransport"
        Effect    = "Deny"
        Principal = "*"
        Action    = "s3:*"
        Resource = [
          aws_s3_bucket.assets.arn,
          "${aws_s3_bucket.assets.arn}/*"
        ]
        Condition = {
          Bool = {
            "aws:SecureTransport" = "false"
          }
        }
      }
    ]
  })

  depends_on = [aws_s3_bucket_public_access_block.assets]
}

# =============================================================================
# CORS Configuration (if needed for direct uploads)
# =============================================================================

resource "aws_s3_bucket_cors_configuration" "assets" {
  bucket = aws_s3_bucket.assets.id

  cors_rule {
    allowed_headers = ["*"]
    allowed_methods = ["GET", "PUT", "POST", "DELETE"]
    allowed_origins = ["*"] # Restrict to specific origins in production
    expose_headers  = ["ETag"]
    max_age_seconds = 3000
  }
}

# =============================================================================
# Intelligent Tiering (optional - for cost optimization)
# =============================================================================

resource "aws_s3_bucket_intelligent_tiering_configuration" "assets" {
  bucket = aws_s3_bucket.assets.id
  name   = "EntireBucket"

  status = "Enabled"

  tiering {
    access_tier = "ARCHIVE_ACCESS"
    days        = 90
  }

  tiering {
    access_tier = "DEEP_ARCHIVE_ACCESS"
    days        = 180
  }
}

# =============================================================================
# Logging (optional - for audit trail)
# =============================================================================
# Uncomment to enable access logging to a separate bucket
#
# resource "aws_s3_bucket_logging" "assets" {
#   bucket = aws_s3_bucket.assets.id
#
#   target_bucket = aws_s3_bucket.logs.id
#   target_prefix = "s3-access-logs/assets/"
# }
