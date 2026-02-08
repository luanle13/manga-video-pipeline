# Storage Module

Terraform module for S3 and DynamoDB storage resources for the Manga Video Pipeline.

## Resources Created

### S3 Bucket
- **Name**: `manga-pipeline-assets-{account_id}`
- **Purpose**: Temporary storage for video processing assets
- **Encryption**: SSE-S3 (AES256)
- **Public Access**: Blocked
- **Versioning**: Disabled (temporary files)
- **Lifecycle**: Auto-delete after 7 days
- **CORS**: Enabled for direct uploads
- **Policy**: HTTPS-only enforced

### DynamoDB Tables

#### 1. manga_jobs
- **Purpose**: Job tracking for video processing pipeline
- **Primary Key**: `job_id` (String)
- **GSI**: `status-created-index`
  - Hash Key: `status` (String)
  - Range Key: `created_at` (String)
  - Projection: ALL
- **Billing**: PAY_PER_REQUEST
- **Point-in-Time Recovery**: Enabled
- **Encryption**: AWS owned key
- **TTL**: Enabled on `ttl` attribute

#### 2. processed_manga
- **Purpose**: Metadata for processed manga
- **Primary Key**: `manga_id` (String)
- **Billing**: PAY_PER_REQUEST
- **Point-in-Time Recovery**: Enabled
- **Encryption**: AWS owned key

#### 3. settings
- **Purpose**: Pipeline configuration settings
- **Primary Key**: `setting_key` (String)
- **Billing**: PAY_PER_REQUEST
- **Point-in-Time Recovery**: Enabled
- **Encryption**: AWS owned key

## Usage

### Basic Usage

```hcl
module "storage" {
  source = "./modules/storage"

  project_name = "manga-video-pipeline"
  environment  = "prod"

  tags = {
    Team = "DevOps"
  }
}
```

### With Custom Lifecycle

```hcl
module "storage" {
  source = "./modules/storage"

  project_name         = "manga-video-pipeline"
  environment          = "prod"
  assets_lifecycle_days = 14  # Delete after 14 days instead of 7

  tags = {
    Team = "DevOps"
  }
}
```

### Disable Point-in-Time Recovery (not recommended for production)

```hcl
module "storage" {
  source = "./modules/storage"

  project_name                 = "manga-video-pipeline"
  environment                  = "dev"
  enable_point_in_time_recovery = false

  tags = {
    Team = "DevOps"
  }
}
```

## Inputs

| Name | Description | Type | Default | Required |
|------|-------------|------|---------|:--------:|
| project_name | Project name for resource naming | `string` | n/a | yes |
| environment | Environment name (dev, staging, prod) | `string` | n/a | yes |
| assets_lifecycle_days | Number of days before deleting objects in assets bucket | `number` | `7` | no |
| enable_point_in_time_recovery | Enable point-in-time recovery for DynamoDB tables | `bool` | `true` | no |
| tags | Additional tags to apply to resources | `map(string)` | `{}` | no |

## Outputs

| Name | Description |
|------|-------------|
| s3_assets_bucket_id | ID (name) of the S3 assets bucket |
| s3_assets_bucket_arn | ARN of the S3 assets bucket |
| dynamodb_jobs_table_name | Name of the manga_jobs DynamoDB table |
| dynamodb_jobs_table_arn | ARN of the manga_jobs DynamoDB table |
| dynamodb_processed_manga_table_name | Name of the processed_manga DynamoDB table |
| dynamodb_settings_table_name | Name of the settings DynamoDB table |
| dynamodb_table_names | Map of all DynamoDB table names |
| dynamodb_table_arns | Map of all DynamoDB table ARNs |
| storage_summary | Summary of storage resources created |

## DynamoDB Table Schemas

### manga_jobs Table

```python
{
    "job_id": "uuid-v4",                    # PK - Unique job identifier
    "manga_id": "mangadex-id",              # Manga ID from MangaDex
    "manga_title": "Manga Title",           # Manga title
    "chapter_number": "123",                # Chapter number
    "status": "pending|fetching|...",       # Job status (for GSI)
    "created_at": "2024-01-01T00:00:00Z",   # Creation timestamp (for GSI)
    "updated_at": "2024-01-01T00:00:00Z",   # Last update timestamp
    "youtube_url": "https://...",           # YouTube video URL
    "error_message": "Error details",       # Error message if failed
    "ttl": 1234567890                       # TTL for auto-deletion
}
```

**Query Patterns:**
- Get job by ID: `GetItem` on `job_id`
- List jobs by status: Query GSI `status-created-index` with `status = "pending"`
- List recent jobs: Query GSI `status-created-index` with `status = "completed"` and `ScanIndexForward = false`

### processed_manga Table

```python
{
    "manga_id": "mangadex-id",              # PK - Manga ID
    "manga_title": "Manga Title",           # Manga title
    "chapters_processed": ["1", "2", "3"],  # List of processed chapters
    "total_videos": 10,                     # Total videos created
    "first_processed_at": "2024-01-01",     # First processing date
    "last_processed_at": "2024-01-15"       # Most recent processing date
}
```

### settings Table

```python
{
    "setting_key": "pipeline_config",       # PK - Setting identifier
    "daily_quota": 10,                      # Daily video quota
    "voice_id": "vi-VN-HoaiMyNeural",      # TTS voice ID
    "tone": "engaging",                     # Narration tone
    "script_style": "chapter_walkthrough",  # Script generation style
    "updated_at": "2024-01-01T00:00:00Z"   # Last update timestamp
}
```

## Security

### S3 Bucket Security
- ✅ All public access blocked
- ✅ Encryption at rest (SSE-S3)
- ✅ HTTPS-only enforced via bucket policy
- ✅ CORS configured for direct uploads
- ✅ Intelligent tiering enabled for cost optimization

### DynamoDB Security
- ✅ Encryption at rest with AWS owned keys (no additional cost)
- ✅ Point-in-time recovery enabled for disaster recovery
- ✅ TTL enabled for automatic cleanup of old records
- ✅ On-demand billing to prevent throttling

## Cost Optimization

### S3 Costs
- **Storage**: $0.023/GB-month (Standard class)
- **Lifecycle**: Auto-delete after 7 days reduces storage costs
- **Intelligent Tiering**: Automatically moves infrequently accessed data to cheaper tiers
- **Estimated Cost**: ~$1-5/month depending on usage

### DynamoDB Costs
- **Billing Mode**: PAY_PER_REQUEST (no provisioned capacity)
- **Reads**: $0.25 per million read request units
- **Writes**: $1.25 per million write request units
- **Storage**: $0.25/GB-month
- **Point-in-Time Recovery**: ~$0.20/GB-month
- **Estimated Cost**: ~$5-10/month for moderate usage

## Disaster Recovery

### S3
- **Lifecycle Rules**: Objects auto-deleted after 7 days (temp files)
- **No Versioning**: Not needed for temporary files
- **Cross-Region Replication**: Not configured (temp files, not critical)

### DynamoDB
- **Point-in-Time Recovery**: Enabled (restore to any point in last 35 days)
- **Backup**: On-demand backups can be created via AWS Console or CLI
- **Recovery Time Objective (RTO)**: Minutes to hours
- **Recovery Point Objective (RPO)**: Seconds (PITR)

## Monitoring

### CloudWatch Metrics

**S3:**
- `BucketSizeBytes` - Monitor bucket size
- `NumberOfObjects` - Track object count
- `AllRequests` - API request metrics

**DynamoDB:**
- `ConsumedReadCapacityUnits` - Read capacity consumption
- `ConsumedWriteCapacityUnits` - Write capacity consumption
- `UserErrors` - Client-side errors
- `SystemErrors` - Service-side errors
- `SuccessfulRequestLatency` - Request latency

### Alarms (recommended)

```hcl
# Example CloudWatch alarm for DynamoDB user errors
resource "aws_cloudwatch_metric_alarm" "dynamodb_user_errors" {
  alarm_name          = "${var.project_name}-dynamodb-user-errors"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "1"
  metric_name         = "UserErrors"
  namespace           = "AWS/DynamoDB"
  period              = "300"
  statistic           = "Sum"
  threshold           = "10"
  alarm_description   = "DynamoDB user errors exceeded threshold"

  dimensions = {
    TableName = module.storage.dynamodb_jobs_table_name
  }
}
```

## Examples

See `examples/` directory for complete usage examples:
- `examples/basic/` - Basic module usage
- `examples/with-monitoring/` - With CloudWatch alarms
- `examples/multi-environment/` - Multi-environment setup

## Testing

```bash
# Format code
terraform fmt -recursive

# Validate configuration
terraform validate

# Plan changes
terraform plan

# Apply changes
terraform apply

# Run tests (requires terratest)
cd test
go test -v -timeout 30m
```

## References

- [AWS S3 Documentation](https://docs.aws.amazon.com/s3/)
- [AWS DynamoDB Documentation](https://docs.aws.amazon.com/dynamodb/)
- [Terraform AWS Provider](https://registry.terraform.io/providers/hashicorp/aws/latest/docs)
