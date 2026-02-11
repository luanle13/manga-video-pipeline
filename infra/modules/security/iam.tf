# =============================================================================
# IAM Roles for Manga Video Pipeline
# =============================================================================
# This file contains all IAM roles and policies for the pipeline components.
# All roles follow the principle of least privilege with resource-specific ARNs.
# =============================================================================

# =============================================================================
# 1. Lambda Fetcher Role
# =============================================================================
# Purpose: Fetch manga chapters from MangaDex and store images in S3
# Permissions: S3 (PutObject, GetObject), DynamoDB (GetItem, PutItem, UpdateItem, Query),
#              Secrets Manager (GetSecretValue), CloudWatch Logs
# =============================================================================

resource "aws_iam_role" "lambda_fetcher" {
  name        = "${var.project_name}-lambda-fetcher"
  description = "IAM role for manga fetcher Lambda function"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
        Action = "sts:AssumeRole"
      }
    ]
  })

  tags = merge(
    local.common_tags,
    {
      Name      = "${var.project_name}-lambda-fetcher"
      Component = "lambda"
      Function  = "manga-fetcher"
    }
  )
}

resource "aws_iam_role_policy" "lambda_fetcher" {
  name = "${var.project_name}-lambda-fetcher-policy"
  role = aws_iam_role.lambda_fetcher.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      # S3 permissions for storing manga images
      {
        Sid    = "S3AssetsBucketAccess"
        Effect = "Allow"
        Action = [
          "s3:PutObject",
          "s3:GetObject"
        ]
        Resource = "${var.s3_assets_bucket_arn}/jobs/*"
      },
      # DynamoDB permissions for job tracking and manga metadata
      {
        Sid    = "DynamoDBJobsAccess"
        Effect = "Allow"
        Action = [
          "dynamodb:GetItem",
          "dynamodb:PutItem",
          "dynamodb:UpdateItem",
          "dynamodb:Query"
        ]
        Resource = [
          var.dynamodb_jobs_table_arn,
          "${var.dynamodb_jobs_table_arn}/index/${var.dynamodb_jobs_gsi_name}"
        ]
      },
      {
        Sid    = "DynamoDBProcessedMangaAccess"
        Effect = "Allow"
        Action = [
          "dynamodb:GetItem",
          "dynamodb:PutItem",
          "dynamodb:UpdateItem"
        ]
        Resource = var.dynamodb_processed_manga_table_arn
      },
      # Secrets Manager for MangaDex credentials (if needed)
      {
        Sid    = "SecretsManagerMangaDexAccess"
        Effect = "Allow"
        Action = [
          "secretsmanager:GetSecretValue"
        ]
        Resource = "arn:aws:secretsmanager:${local.region}:${local.account_id}:secret:${var.mangadex_secret_name}*"
      },
      # CloudWatch Logs
      {
        Sid    = "CloudWatchLogsAccess"
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "arn:aws:logs:${local.region}:${local.account_id}:log-group:/aws/lambda/${var.lambda_function_names.manga_fetcher}*"
      }
    ]
  })
}

# =============================================================================
# 2. Lambda Script Generator Role
# =============================================================================
# Purpose: Generate narration scripts from manga images using Qwen LLM
# Permissions: S3 (GetObject, PutObject), DynamoDB (GetItem, UpdateItem),
#              Secrets Manager (GetSecretValue), CloudWatch Logs
# =============================================================================

resource "aws_iam_role" "lambda_scriptgen" {
  name        = "${var.project_name}-lambda-scriptgen"
  description = "IAM role for script generator Lambda function"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
        Action = "sts:AssumeRole"
      }
    ]
  })

  tags = merge(
    local.common_tags,
    {
      Name      = "${var.project_name}-lambda-scriptgen"
      Component = "lambda"
      Function  = "script-generator"
    }
  )
}

resource "aws_iam_role_policy" "lambda_scriptgen" {
  name = "${var.project_name}-lambda-scriptgen-policy"
  role = aws_iam_role.lambda_scriptgen.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      # S3 permissions for reading images and writing scripts
      {
        Sid    = "S3AssetsBucketAccess"
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject"
        ]
        Resource = "${var.s3_assets_bucket_arn}/jobs/*"
      },
      # DynamoDB permissions for job updates
      {
        Sid    = "DynamoDBJobsAccess"
        Effect = "Allow"
        Action = [
          "dynamodb:GetItem",
          "dynamodb:UpdateItem"
        ]
        Resource = var.dynamodb_jobs_table_arn
      },
      # DynamoDB permissions for reading settings
      {
        Sid    = "DynamoDBSettingsAccess"
        Effect = "Allow"
        Action = [
          "dynamodb:GetItem"
        ]
        Resource = var.dynamodb_settings_table_arn
      },
      # Secrets Manager for DeepInfra API key
      {
        Sid    = "SecretsManagerDeepInfraAccess"
        Effect = "Allow"
        Action = [
          "secretsmanager:GetSecretValue"
        ]
        Resource = "arn:aws:secretsmanager:${local.region}:${local.account_id}:secret:${var.deepinfra_api_key_secret_name}*"
      },
      # CloudWatch Logs
      {
        Sid    = "CloudWatchLogsAccess"
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "arn:aws:logs:${local.region}:${local.account_id}:log-group:/aws/lambda/${var.lambda_function_names.script_generator}*"
      }
    ]
  })
}

# =============================================================================
# 3. Lambda TTS Generator Role
# =============================================================================
# Purpose: Generate Vietnamese audio from scripts using Edge TTS
# Permissions: S3 (GetObject, PutObject), DynamoDB (GetItem, UpdateItem),
#              CloudWatch Logs
# =============================================================================

resource "aws_iam_role" "lambda_ttsgen" {
  name        = "${var.project_name}-lambda-ttsgen"
  description = "IAM role for TTS generator Lambda function"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
        Action = "sts:AssumeRole"
      }
    ]
  })

  tags = merge(
    local.common_tags,
    {
      Name      = "${var.project_name}-lambda-ttsgen"
      Component = "lambda"
      Function  = "tts-processor"
    }
  )
}

resource "aws_iam_role_policy" "lambda_ttsgen" {
  name = "${var.project_name}-lambda-ttsgen-policy"
  role = aws_iam_role.lambda_ttsgen.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      # S3 permissions for reading scripts and writing audio files
      {
        Sid    = "S3AssetsBucketAccess"
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject"
        ]
        Resource = "${var.s3_assets_bucket_arn}/jobs/*"
      },
      # DynamoDB permissions for job updates
      {
        Sid    = "DynamoDBJobsAccess"
        Effect = "Allow"
        Action = [
          "dynamodb:GetItem",
          "dynamodb:UpdateItem"
        ]
        Resource = var.dynamodb_jobs_table_arn
      },
      # DynamoDB permissions for reading settings (voice ID, tone)
      {
        Sid    = "DynamoDBSettingsAccess"
        Effect = "Allow"
        Action = [
          "dynamodb:GetItem"
        ]
        Resource = var.dynamodb_settings_table_arn
      },
      # CloudWatch Logs
      {
        Sid    = "CloudWatchLogsAccess"
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "arn:aws:logs:${local.region}:${local.account_id}:log-group:/aws/lambda/${var.lambda_function_names.tts_processor}*"
      }
    ]
  })
}

# =============================================================================
# 4. Lambda Cleanup Role
# =============================================================================
# Purpose: Clean up temporary files from S3 after video upload
# Permissions: S3 (DeleteObject, ListBucket), DynamoDB (UpdateItem),
#              CloudWatch Logs
# =============================================================================

resource "aws_iam_role" "lambda_cleanup" {
  name        = "${var.project_name}-lambda-cleanup"
  description = "IAM role for cleanup Lambda function"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
        Action = "sts:AssumeRole"
      }
    ]
  })

  tags = merge(
    local.common_tags,
    {
      Name      = "${var.project_name}-lambda-cleanup"
      Component = "lambda"
      Function  = "cleanup"
    }
  )
}

resource "aws_iam_role_policy" "lambda_cleanup" {
  name = "${var.project_name}-lambda-cleanup-policy"
  role = aws_iam_role.lambda_cleanup.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      # S3 permissions for deleting temporary job files
      {
        Sid    = "S3DeleteObjectsAccess"
        Effect = "Allow"
        Action = [
          "s3:DeleteObject"
        ]
        Resource = "${var.s3_assets_bucket_arn}/jobs/*"
      },
      # S3 permission to list bucket for cleanup
      {
        Sid    = "S3ListBucketAccess"
        Effect = "Allow"
        Action = [
          "s3:ListBucket"
        ]
        Resource = var.s3_assets_bucket_arn
        Condition = {
          StringLike = {
            "s3:prefix" = "jobs/*"
          }
        }
      },
      # DynamoDB permissions for updating job status
      {
        Sid    = "DynamoDBJobsAccess"
        Effect = "Allow"
        Action = [
          "dynamodb:UpdateItem"
        ]
        Resource = var.dynamodb_jobs_table_arn
      },
      # CloudWatch Logs
      {
        Sid    = "CloudWatchLogsAccess"
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "arn:aws:logs:${local.region}:${local.account_id}:log-group:/aws/lambda/${var.lambda_function_names.cleanup}*"
      }
    ]
  })
}

# =============================================================================
# 5. Lambda Quota Checker Role
# =============================================================================
# Purpose: Check daily video quota before starting pipeline
# Permissions: DynamoDB (GetItem on settings, Query on manga_jobs),
#              CloudWatch Logs
# =============================================================================

resource "aws_iam_role" "lambda_quota_checker" {
  name        = "${var.project_name}-lambda-quota-checker"
  description = "IAM role for quota checker Lambda function"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
        Action = "sts:AssumeRole"
      }
    ]
  })

  tags = merge(
    local.common_tags,
    {
      Name      = "${var.project_name}-lambda-quota-checker"
      Component = "lambda"
      Function  = "quota-checker"
    }
  )
}

resource "aws_iam_role_policy" "lambda_quota_checker" {
  name = "${var.project_name}-lambda-quota-checker-policy"
  role = aws_iam_role.lambda_quota_checker.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      # DynamoDB permissions for reading settings (daily quota)
      {
        Sid    = "DynamoDBSettingsAccess"
        Effect = "Allow"
        Action = [
          "dynamodb:GetItem"
        ]
        Resource = var.dynamodb_settings_table_arn
      },
      # DynamoDB permissions for querying jobs by status
      {
        Sid    = "DynamoDBJobsQueryAccess"
        Effect = "Allow"
        Action = [
          "dynamodb:Query"
        ]
        Resource = [
          var.dynamodb_jobs_table_arn,
          "${var.dynamodb_jobs_table_arn}/index/${var.dynamodb_jobs_gsi_name}"
        ]
      },
      # CloudWatch Logs
      {
        Sid    = "CloudWatchLogsAccess"
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "arn:aws:logs:${local.region}:${local.account_id}:log-group:/aws/lambda/${var.lambda_function_names.quota_checker}*"
      }
    ]
  })
}

# =============================================================================
# 6. EC2 Renderer Role (Spot Instances)
# =============================================================================
# Purpose: Render videos, merge audio, upload to YouTube from Spot instances
# Permissions: S3 (GetObject, PutObject), DynamoDB (GetItem, UpdateItem),
#              Secrets Manager (GetSecretValue), States (SendTask*),
#              Lambda (InvokeFunction), CloudWatch Logs, SSM (GetParameter)
# =============================================================================

resource "aws_iam_role" "ec2_renderer" {
  name        = "${var.project_name}-ec2-renderer"
  description = "IAM role for EC2 Spot instances running video renderer"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "ec2.amazonaws.com"
        }
        Action = "sts:AssumeRole"
      }
    ]
  })

  tags = merge(
    local.common_tags,
    {
      Name      = "${var.project_name}-ec2-renderer"
      Component = "ec2"
      Function  = "video-renderer"
    }
  )
}

resource "aws_iam_instance_profile" "ec2_renderer" {
  name = "${var.project_name}-ec2-renderer"
  role = aws_iam_role.ec2_renderer.name

  tags = merge(
    local.common_tags,
    {
      Name      = "${var.project_name}-ec2-renderer"
      Component = "ec2"
    }
  )
}

resource "aws_iam_role_policy" "ec2_renderer" {
  name = "${var.project_name}-ec2-renderer-policy"
  role = aws_iam_role.ec2_renderer.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      # S3 permissions for reading assets and uploading videos
      {
        Sid    = "S3AssetsBucketAccess"
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject"
        ]
        Resource = "${var.s3_assets_bucket_arn}/jobs/*"
      },
      # DynamoDB permissions for job updates
      {
        Sid    = "DynamoDBJobsAccess"
        Effect = "Allow"
        Action = [
          "dynamodb:GetItem",
          "dynamodb:UpdateItem"
        ]
        Resource = var.dynamodb_jobs_table_arn
      },
      # Secrets Manager for YouTube credentials
      {
        Sid    = "SecretsManagerYouTubeAccess"
        Effect = "Allow"
        Action = [
          "secretsmanager:GetSecretValue"
        ]
        Resource = "arn:aws:secretsmanager:${local.region}:${local.account_id}:secret:${var.youtube_credentials_secret_name}*"
      },
      # Step Functions callback for task completion
      {
        Sid    = "StatesTaskCallbackAccess"
        Effect = "Allow"
        Action = [
          "states:GetActivityTask",
          "states:SendTaskSuccess",
          "states:SendTaskHeartbeat",
          "states:SendTaskFailure"
        ]
        Resource = "*"
      },
      # Lambda invoke for cleanup function
      {
        Sid    = "LambdaCleanupInvokeAccess"
        Effect = "Allow"
        Action = [
          "lambda:InvokeFunction"
        ]
        Resource = "arn:aws:lambda:${local.region}:${local.account_id}:function:${var.lambda_function_names.cleanup}"
      },
      # CloudWatch Logs
      {
        Sid    = "CloudWatchLogsAccess"
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "arn:aws:logs:${local.region}:${local.account_id}:log-group:/aws/ec2/renderer*"
      },
      # SSM Parameter Store for job_id
      {
        Sid    = "SSMParameterAccess"
        Effect = "Allow"
        Action = [
          "ssm:GetParameter",
          "ssm:GetParameters"
        ]
        Resource = "arn:aws:ssm:${local.region}:${local.account_id}:parameter/${var.project_name}/*"
      }
    ]
  })
}

# =============================================================================
# 7. Step Functions Role
# =============================================================================
# Purpose: Orchestrate the video processing pipeline
# Permissions: Lambda (InvokeFunction), EC2 (RunInstances, TerminateInstances),
#              IAM (PassRole), CloudWatch Logs
# =============================================================================

resource "aws_iam_role" "step_functions" {
  name        = "${var.project_name}-step-functions"
  description = "IAM role for Step Functions state machine"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "states.amazonaws.com"
        }
        Action = "sts:AssumeRole"
      }
    ]
  })

  tags = merge(
    local.common_tags,
    {
      Name      = "${var.project_name}-step-functions"
      Component = "step-functions"
    }
  )
}

resource "aws_iam_role_policy" "step_functions" {
  name = "${var.project_name}-step-functions-policy"
  role = aws_iam_role.step_functions.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      # Lambda invoke permissions for all pipeline functions
      {
        Sid    = "LambdaInvokeAccess"
        Effect = "Allow"
        Action = [
          "lambda:InvokeFunction"
        ]
        Resource = [
          "arn:aws:lambda:${local.region}:${local.account_id}:function:${var.lambda_function_names.manga_fetcher}",
          "arn:aws:lambda:${local.region}:${local.account_id}:function:${var.lambda_function_names.script_generator}",
          "arn:aws:lambda:${local.region}:${local.account_id}:function:${var.lambda_function_names.tts_processor}",
          "arn:aws:lambda:${local.region}:${local.account_id}:function:${var.lambda_function_names.quota_checker}",
          "arn:aws:lambda:${local.region}:${local.account_id}:function:${var.lambda_function_names.cleanup}"
        ]
      },
      # EC2 permissions for Spot instance management - RunInstances
      {
        Sid    = "EC2RunInstancesAccess"
        Effect = "Allow"
        Action = [
          "ec2:RunInstances"
        ]
        Resource = [
          "arn:aws:ec2:${local.region}:${local.account_id}:instance/*"
        ]
        Condition = {
          StringEquals = {
            "aws:RequestTag/${var.ec2_spot_tag_key}" = var.ec2_spot_tag_value
          }
        }
      },
      # EC2 resources required for RunInstances (no tag conditions needed)
      {
        Sid    = "EC2RunInstancesResourceAccess"
        Effect = "Allow"
        Action = [
          "ec2:RunInstances"
        ]
        Resource = [
          "arn:aws:ec2:${local.region}:${local.account_id}:volume/*",
          "arn:aws:ec2:${local.region}:${local.account_id}:network-interface/*",
          "arn:aws:ec2:${local.region}::image/*",
          "arn:aws:ec2:${local.region}:${local.account_id}:subnet/*",
          "arn:aws:ec2:${local.region}:${local.account_id}:security-group/*",
          "arn:aws:ec2:${local.region}:${local.account_id}:launch-template/*"
        ]
      },
      # EC2 TerminateInstances - only for pipeline-managed instances
      {
        Sid    = "EC2TerminateInstancesAccess"
        Effect = "Allow"
        Action = [
          "ec2:TerminateInstances"
        ]
        Resource = [
          "arn:aws:ec2:${local.region}:${local.account_id}:instance/*"
        ]
        Condition = {
          StringEquals = {
            "ec2:ResourceTag/${var.ec2_spot_tag_key}" = var.ec2_spot_tag_value
          }
        }
      },
      # EC2 CreateTags - required to tag instances at launch
      {
        Sid    = "EC2CreateTagsAccess"
        Effect = "Allow"
        Action = [
          "ec2:CreateTags"
        ]
        Resource = [
          "arn:aws:ec2:${local.region}:${local.account_id}:instance/*",
          "arn:aws:ec2:${local.region}:${local.account_id}:volume/*",
          "arn:aws:ec2:${local.region}:${local.account_id}:network-interface/*"
        ]
        Condition = {
          StringEquals = {
            "ec2:CreateAction" = "RunInstances"
          }
        }
      },
      # Additional EC2 describe permissions (non-resource specific)
      {
        Sid    = "EC2DescribeAccess"
        Effect = "Allow"
        Action = [
          "ec2:DescribeInstances",
          "ec2:DescribeInstanceStatus",
          "ec2:DescribeLaunchTemplates"
        ]
        Resource = "*"
      },
      # IAM PassRole for EC2 instance profile
      {
        Sid    = "IAMPassRoleAccess"
        Effect = "Allow"
        Action = [
          "iam:PassRole"
        ]
        Resource = aws_iam_role.ec2_renderer.arn
        Condition = {
          StringEquals = {
            "iam:PassedToService" = "ec2.amazonaws.com"
          }
        }
      },
      # CloudWatch Logs
      {
        Sid    = "CloudWatchLogsAccess"
        Effect = "Allow"
        Action = [
          "logs:CreateLogDelivery",
          "logs:GetLogDelivery",
          "logs:UpdateLogDelivery",
          "logs:DeleteLogDelivery",
          "logs:ListLogDeliveries",
          "logs:PutResourcePolicy",
          "logs:DescribeResourcePolicies",
          "logs:DescribeLogGroups"
        ]
        Resource = "*"
      }
    ]
  })
}

# =============================================================================
# 8. EventBridge Role
# =============================================================================
# Purpose: Trigger the Step Functions state machine on schedule
# Permissions: States (StartExecution)
# =============================================================================

resource "aws_iam_role" "eventbridge" {
  name        = "${var.project_name}-eventbridge"
  description = "IAM role for EventBridge scheduler"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "events.amazonaws.com"
        }
        Action = "sts:AssumeRole"
      }
    ]
  })

  tags = merge(
    local.common_tags,
    {
      Name      = "${var.project_name}-eventbridge"
      Component = "eventbridge"
    }
  )
}

resource "aws_iam_role_policy" "eventbridge" {
  name = "${var.project_name}-eventbridge-policy"
  role = aws_iam_role.eventbridge.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      # Step Functions start execution permission
      {
        Sid    = "StatesStartExecutionAccess"
        Effect = "Allow"
        Action = [
          "states:StartExecution"
        ]
        Resource = var.state_machine_arn != "" ? var.state_machine_arn : "arn:aws:states:${local.region}:${local.account_id}:stateMachine:${var.project_name}-*"
      }
    ]
  })
}

# =============================================================================
# 9. Dashboard EC2 Role
# =============================================================================
# Purpose: Run the admin dashboard on EC2 instance
# Permissions: DynamoDB (full access on pipeline tables), Secrets Manager,
#              States (StartExecution for retry), CloudWatch Logs
# =============================================================================

resource "aws_iam_role" "dashboard_ec2" {
  name        = "${var.project_name}-dashboard-ec2"
  description = "IAM role for dashboard EC2 instance"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "ec2.amazonaws.com"
        }
        Action = "sts:AssumeRole"
      }
    ]
  })

  tags = merge(
    local.common_tags,
    {
      Name      = "${var.project_name}-dashboard-ec2"
      Component = "dashboard"
    }
  )
}

resource "aws_iam_instance_profile" "dashboard_ec2" {
  name = "${var.project_name}-dashboard-ec2"
  role = aws_iam_role.dashboard_ec2.name

  tags = merge(
    local.common_tags,
    {
      Name      = "${var.project_name}-dashboard-ec2"
      Component = "dashboard"
    }
  )
}

resource "aws_iam_role_policy" "dashboard_ec2" {
  name = "${var.project_name}-dashboard-ec2-policy"
  role = aws_iam_role.dashboard_ec2.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      # DynamoDB full access on manga_jobs table
      {
        Sid    = "DynamoDBJobsFullAccess"
        Effect = "Allow"
        Action = [
          "dynamodb:GetItem",
          "dynamodb:PutItem",
          "dynamodb:UpdateItem",
          "dynamodb:DeleteItem",
          "dynamodb:Query",
          "dynamodb:Scan"
        ]
        Resource = [
          var.dynamodb_jobs_table_arn,
          "${var.dynamodb_jobs_table_arn}/index/${var.dynamodb_jobs_gsi_name}"
        ]
      },
      # DynamoDB full access on processed_manga table
      {
        Sid    = "DynamoDBProcessedMangaFullAccess"
        Effect = "Allow"
        Action = [
          "dynamodb:GetItem",
          "dynamodb:PutItem",
          "dynamodb:UpdateItem",
          "dynamodb:DeleteItem",
          "dynamodb:Query",
          "dynamodb:Scan"
        ]
        Resource = var.dynamodb_processed_manga_table_arn
      },
      # DynamoDB full access on settings table
      {
        Sid    = "DynamoDBSettingsFullAccess"
        Effect = "Allow"
        Action = [
          "dynamodb:GetItem",
          "dynamodb:PutItem",
          "dynamodb:UpdateItem",
          "dynamodb:DeleteItem",
          "dynamodb:Scan"
        ]
        Resource = var.dynamodb_settings_table_arn
      },
      # Secrets Manager for admin credentials
      {
        Sid    = "SecretsManagerAdminAccess"
        Effect = "Allow"
        Action = [
          "secretsmanager:GetSecretValue"
        ]
        Resource = "arn:aws:secretsmanager:${local.region}:${local.account_id}:secret:${var.admin_credentials_secret_name}*"
      },
      # Step Functions for retry functionality
      {
        Sid    = "StatesStartExecutionAccess"
        Effect = "Allow"
        Action = [
          "states:StartExecution"
        ]
        Resource = var.state_machine_arn != "" ? var.state_machine_arn : "arn:aws:states:${local.region}:${local.account_id}:stateMachine:${var.project_name}-*"
      },
      # CloudWatch Logs
      {
        Sid    = "CloudWatchLogsAccess"
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "arn:aws:logs:${local.region}:${local.account_id}:log-group:/aws/ec2/dashboard*"
      },
      # SSM Session Manager (for secure SSH alternative)
      {
        Sid    = "SSMSessionManagerAccess"
        Effect = "Allow"
        Action = [
          "ssm:UpdateInstanceInformation",
          "ssmmessages:CreateControlChannel",
          "ssmmessages:CreateDataChannel",
          "ssmmessages:OpenControlChannel",
          "ssmmessages:OpenDataChannel"
        ]
        Resource = "*"
      },
      # S3 access for downloading deployment packages
      {
        Sid    = "S3DeploymentBucketReadAccess"
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:ListBucket"
        ]
        Resource = [
          "arn:aws:s3:::${var.project_name}-deployments-${local.account_id}",
          "arn:aws:s3:::${var.project_name}-deployments-${local.account_id}/*"
        ]
      }
    ]
  })
}
