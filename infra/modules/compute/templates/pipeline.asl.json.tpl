{
  "Comment": "Manga-to-Video Pipeline - Fetches manga, generates scripts/audio, renders video, uploads to YouTube",
  "StartAt": "CheckQuota",
  "States": {
    "CheckQuota": {
      "Type": "Task",
      "Resource": "${quota_checker_arn}",
      "Comment": "Check if daily video quota has been reached",
      "ResultPath": "$.quotaCheck",
      "Retry": [
        {
          "ErrorEquals": ["States.TaskFailed", "States.Timeout"],
          "IntervalSeconds": 2,
          "MaxAttempts": 3,
          "BackoffRate": 2.0
        }
      ],
      "Catch": [
        {
          "ErrorEquals": ["States.ALL"],
          "ResultPath": "$.error",
          "Next": "HandleError"
        }
      ],
      "Next": "QuotaChoice"
    },
    "QuotaChoice": {
      "Type": "Choice",
      "Comment": "Determine if quota has been reached",
      "Choices": [
        {
          "Variable": "$.quotaCheck.quota_reached",
          "BooleanEquals": true,
          "Next": "QuotaReached"
        }
      ],
      "Default": "FetchManga"
    },
    "QuotaReached": {
      "Type": "Succeed",
      "Comment": "Daily quota reached, stop processing"
    },
    "FetchManga": {
      "Type": "Task",
      "Resource": "${fetcher_arn}",
      "Comment": "Fetch manga chapters and download panel images",
      "ResultPath": "$.fetchResult",
      "TimeoutSeconds": 900,
      "Retry": [
        {
          "ErrorEquals": ["States.TaskFailed", "States.Timeout"],
          "IntervalSeconds": 60,
          "MaxAttempts": 2,
          "BackoffRate": 2.0
        }
      ],
      "Catch": [
        {
          "ErrorEquals": ["States.ALL"],
          "ResultPath": "$.error",
          "Next": "HandleError"
        }
      ],
      "Next": "FetchChoice"
    },
    "FetchChoice": {
      "Type": "Choice",
      "Comment": "Check if manga was available",
      "Choices": [
        {
          "Variable": "$.fetchResult.status",
          "StringEquals": "no_manga_available",
          "Next": "NoMangaAvailable"
        }
      ],
      "Default": "PrepareScriptInput"
    },
    "NoMangaAvailable": {
      "Type": "Succeed",
      "Comment": "No manga available to process"
    },
    "PrepareScriptInput": {
      "Type": "Pass",
      "Comment": "Prepare input for script generation",
      "Parameters": {
        "job_id.$": "$.fetchResult.job_id"
      },
      "Next": "GenerateScript"
    },
    "GenerateScript": {
      "Type": "Task",
      "Resource": "${scriptgen_arn}",
      "Comment": "Generate Vietnamese narration script using LLM",
      "ResultPath": "$.scriptResult",
      "TimeoutSeconds": 900,
      "Retry": [
        {
          "ErrorEquals": ["States.TaskFailed", "States.Timeout"],
          "IntervalSeconds": 60,
          "MaxAttempts": 2,
          "BackoffRate": 2.0
        }
      ],
      "Catch": [
        {
          "ErrorEquals": ["States.ALL"],
          "ResultPath": "$.error",
          "Next": "HandleError"
        }
      ],
      "Next": "CheckScriptContinuation"
    },
    "CheckScriptContinuation": {
      "Type": "Choice",
      "Comment": "Check if script generation needs continuation",
      "Choices": [
        {
          "Variable": "$.scriptResult.continuation_needed",
          "BooleanEquals": true,
          "Next": "GenerateScript"
        }
      ],
      "Default": "GenerateTTS"
    },
    "GenerateTTS": {
      "Type": "Task",
      "Resource": "${ttsgen_arn}",
      "Comment": "Generate Vietnamese TTS audio using Edge TTS",
      "ResultPath": "$.ttsResult",
      "TimeoutSeconds": 900,
      "Retry": [
        {
          "ErrorEquals": ["States.TaskFailed", "States.Timeout"],
          "IntervalSeconds": 60,
          "MaxAttempts": 2,
          "BackoffRate": 2.0
        }
      ],
      "Catch": [
        {
          "ErrorEquals": ["States.ALL"],
          "ResultPath": "$.error",
          "Next": "HandleError"
        }
      ],
      "Next": "CheckTTSContinuation"
    },
    "CheckTTSContinuation": {
      "Type": "Choice",
      "Comment": "Check if TTS generation needs continuation",
      "Choices": [
        {
          "Variable": "$.ttsResult.continuation_needed",
          "BooleanEquals": true,
          "Next": "GenerateTTS"
        }
      ],
      "Default": "UpdateSSMForRenderer"
    },
    "UpdateSSMForRenderer": {
      "Type": "Task",
      "Resource": "arn:aws:states:::aws-sdk:ssm:putParameter",
      "Comment": "Store job_id in SSM for renderer instance",
      "Parameters": {
        "Name": "/${project_name}/renderer/current-job-id",
        "Value.$": "$.job_id",
        "Type": "String",
        "Overwrite": true
      },
      "ResultPath": "$.ssmResult",
      "Next": "LaunchRenderer"
    },
    "LaunchRenderer": {
      "Type": "Task",
      "Resource": "arn:aws:states:::aws-sdk:ec2:runInstances",
      "Comment": "Launch EC2 Spot instance for video rendering",
      "Parameters": {
        "LaunchTemplate": {
          "LaunchTemplateId": "${renderer_launch_template}",
          "Version": "$Latest"
        },
        "MinCount": 1,
        "MaxCount": 1
      },
      "ResultPath": "$.rendererInstance",
      "Retry": [
        {
          "ErrorEquals": ["States.TaskFailed"],
          "IntervalSeconds": 30,
          "MaxAttempts": 3,
          "BackoffRate": 2.0
        }
      ],
      "Catch": [
        {
          "ErrorEquals": ["States.ALL"],
          "ResultPath": "$.error",
          "Next": "HandleError"
        }
      ],
      "Next": "WaitForRender"
    },
    "WaitForRender": {
      "Type": "Task",
      "Resource": "${renderer_activity_arn}",
      "Comment": "Wait for rendering to complete (EC2 instance calls GetActivityTask then SendTaskSuccess)",
      "HeartbeatSeconds": 300,
      "TimeoutSeconds": 14400,
      "ResultPath": "$.renderResult",
      "Retry": [
        {
          "ErrorEquals": ["States.Timeout", "States.HeartbeatTimeout"],
          "IntervalSeconds": 60,
          "MaxAttempts": 2,
          "BackoffRate": 1.5,
          "Comment": "Retry on timeout (Spot interruption)"
        }
      ],
      "Catch": [
        {
          "ErrorEquals": ["States.ALL"],
          "ResultPath": "$.error",
          "Next": "HandleError"
        }
      ],
      "Next": "Cleanup"
    },
    "Cleanup": {
      "Type": "Task",
      "Resource": "${cleanup_arn}",
      "Comment": "Clean up temporary S3 artifacts",
      "Parameters": {
        "job_id.$": "$.job_id"
      },
      "ResultPath": "$.cleanupResult",
      "TimeoutSeconds": 300,
      "Retry": [
        {
          "ErrorEquals": ["States.TaskFailed", "States.Timeout"],
          "IntervalSeconds": 30,
          "MaxAttempts": 3,
          "BackoffRate": 2.0
        }
      ],
      "Catch": [
        {
          "ErrorEquals": ["States.ALL"],
          "ResultPath": "$.cleanupError",
          "Comment": "Continue even if cleanup fails",
          "Next": "UpdateJobComplete"
        }
      ],
      "Next": "UpdateJobComplete"
    },
    "UpdateJobComplete": {
      "Type": "Task",
      "Resource": "arn:aws:states:::dynamodb:updateItem",
      "Comment": "Mark job as completed in DynamoDB",
      "Parameters": {
        "TableName": "${project_name}-jobs",
        "Key": {
          "job_id": {
            "S.$": "$.job_id"
          }
        },
        "UpdateExpression": "SET #status = :status, completed_at = :completed_at, progress_pct = :progress",
        "ExpressionAttributeNames": {
          "#status": "status"
        },
        "ExpressionAttributeValues": {
          ":status": {
            "S": "completed"
          },
          ":completed_at": {
            "S.$": "$$.State.EnteredTime"
          },
          ":progress": {
            "N": "100"
          }
        }
      },
      "ResultPath": "$.updateResult",
      "Next": "CheckMoreVideos"
    },
    "CheckMoreVideos": {
      "Type": "Choice",
      "Comment": "Check if we should process more videos",
      "Choices": [
        {
          "And": [
            {
              "Variable": "$.quotaCheck.daily_count",
              "IsPresent": true
            },
            {
              "Variable": "$.quotaCheck.daily_count",
              "NumericLessThanPath": "$.quotaCheck.daily_quota"
            }
          ],
          "Next": "FetchManga"
        }
      ],
      "Default": "Done"
    },
    "HandleError": {
      "Type": "Task",
      "Resource": "arn:aws:states:::dynamodb:updateItem",
      "Comment": "Update job to failed status",
      "Parameters": {
        "TableName": "${project_name}-jobs",
        "Key": {
          "job_id": {
            "S.$": "$.job_id"
          }
        },
        "UpdateExpression": "SET #status = :status, error_message = :error, failed_at = :failed_at",
        "ExpressionAttributeNames": {
          "#status": "status"
        },
        "ExpressionAttributeValues": {
          ":status": {
            "S": "failed"
          },
          ":error": {
            "S.$": "States.Format('Error in state {}: {}', $$.State.Name, $.error.Cause)"
          },
          ":failed_at": {
            "S.$": "$$.State.EnteredTime"
          }
        }
      },
      "ResultPath": "$.errorResult",
      "Next": "CheckMoreVideos"
    },
    "Done": {
      "Type": "Succeed",
      "Comment": "Pipeline completed successfully"
    }
  }
}
