{
  "Comment": "Review Video Pipeline - Scrapes manga sites, generates review scripts, renders video with Vietnamese narration",
  "StartAt": "FetchReviewContent",
  "States": {
    "FetchReviewContent": {
      "Type": "Task",
      "Resource": "${review_fetcher_arn}",
      "Comment": "Fetch manga content from Vietnamese sites and extract chapter text",
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
      "Next": "CheckFetchContinuation"
    },
    "CheckFetchContinuation": {
      "Type": "Choice",
      "Comment": "Check if fetching needs continuation (for manga with many chapters)",
      "Choices": [
        {
          "Variable": "$.fetchResult.continuation_needed",
          "BooleanEquals": true,
          "Next": "PrepareFetchContinuation"
        },
        {
          "Variable": "$.fetchResult.status",
          "StringEquals": "error",
          "Next": "HandleError"
        }
      ],
      "Default": "PrepareScriptInput"
    },
    "PrepareFetchContinuation": {
      "Type": "Pass",
      "Comment": "Prepare input for fetch continuation",
      "Parameters": {
        "job_id.$": "$.fetchResult.job_id",
        "source_url.$": "$.fetchResult.source_url",
        "chapter_offset.$": "$.fetchResult.next_chapter_offset"
      },
      "Next": "FetchReviewContent"
    },
    "PrepareScriptInput": {
      "Type": "Pass",
      "Comment": "Prepare input for review script generation",
      "Parameters": {
        "job_id.$": "$.fetchResult.job_id",
        "manga_title.$": "$.fetchResult.manga_title",
        "review_manifest_s3_key.$": "$.fetchResult.review_manifest_s3_key"
      },
      "Next": "GenerateReviewScript"
    },
    "GenerateReviewScript": {
      "Type": "Task",
      "Resource": "${review_scriptgen_arn}",
      "Comment": "Generate Vietnamese review script using LLM",
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
          "Next": "PrepareScriptContinuation"
        }
      ],
      "Default": "PrepareTTSInput"
    },
    "PrepareScriptContinuation": {
      "Type": "Pass",
      "Comment": "Prepare input for script continuation",
      "Parameters": {
        "job_id.$": "$.scriptResult.job_id",
        "manga_title.$": "$.manga_title",
        "review_manifest_s3_key.$": "$.fetchResult.review_manifest_s3_key",
        "chapter_offset.$": "$.scriptResult.next_chapter_offset"
      },
      "Next": "GenerateReviewScript"
    },
    "PrepareTTSInput": {
      "Type": "Pass",
      "Comment": "Prepare input for TTS generation",
      "Parameters": {
        "job_id.$": "$.fetchResult.job_id",
        "script_s3_key.$": "$.scriptResult.script_s3_key",
        "segment_offset": 0
      },
      "ResultPath": "$.ttsInput",
      "Next": "GenerateTTS"
    },
    "GenerateTTS": {
      "Type": "Task",
      "Resource": "${ttsgen_arn}",
      "Comment": "Generate Vietnamese TTS audio using Edge TTS",
      "InputPath": "$.ttsInput",
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
          "Next": "PrepareTTSContinuation"
        }
      ],
      "Default": "UpdateSSMForRenderer"
    },
    "PrepareTTSContinuation": {
      "Type": "Pass",
      "Comment": "Prepare input for TTS continuation",
      "Parameters": {
        "job_id.$": "$.fetchResult.job_id",
        "script_s3_key.$": "$.scriptResult.script_s3_key",
        "segment_offset.$": "$.ttsResult.next_segment_offset"
      },
      "ResultPath": "$.ttsInput",
      "Next": "GenerateTTS"
    },
    "UpdateSSMForRenderer": {
      "Type": "Task",
      "Resource": "arn:aws:states:::aws-sdk:ssm:putParameter",
      "Comment": "Store job_id in SSM for renderer instance",
      "Parameters": {
        "Name": "/${project_name}/renderer/current-job-id",
        "Value.$": "$.fetchResult.job_id",
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
      "Comment": "Wait for rendering to complete",
      "HeartbeatSeconds": 300,
      "TimeoutSeconds": 14400,
      "ResultPath": "$.renderResult",
      "Retry": [
        {
          "ErrorEquals": ["States.Timeout", "States.HeartbeatTimeout"],
          "IntervalSeconds": 60,
          "MaxAttempts": 2,
          "BackoffRate": 1.5
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
        "job_id.$": "$.fetchResult.job_id"
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
            "S.$": "$.fetchResult.job_id"
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
      "Next": "Done"
    },
    "HandleError": {
      "Type": "Choice",
      "Comment": "Check if job_id exists before updating DynamoDB",
      "Choices": [
        {
          "Variable": "$.fetchResult.job_id",
          "IsPresent": true,
          "Next": "UpdateJobFailed"
        },
        {
          "Variable": "$.job_id",
          "IsPresent": true,
          "Next": "UpdateJobFailedFromInput"
        }
      ],
      "Default": "LogErrorAndFail"
    },
    "UpdateJobFailed": {
      "Type": "Task",
      "Resource": "arn:aws:states:::dynamodb:updateItem",
      "Comment": "Update job to failed status",
      "Parameters": {
        "TableName": "${project_name}-jobs",
        "Key": {
          "job_id": {
            "S.$": "$.fetchResult.job_id"
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
      "Next": "FailExecution"
    },
    "UpdateJobFailedFromInput": {
      "Type": "Task",
      "Resource": "arn:aws:states:::dynamodb:updateItem",
      "Comment": "Update job to failed status using input job_id",
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
      "Next": "FailExecution"
    },
    "LogErrorAndFail": {
      "Type": "Pass",
      "Comment": "No job_id exists, log and fail",
      "Result": {"logged": true, "error": "No job_id available"},
      "ResultPath": "$.errorResult",
      "Next": "FailExecution"
    },
    "FailExecution": {
      "Type": "Fail",
      "Comment": "Review pipeline failed",
      "Error": "ReviewPipelineError",
      "Cause": "Review video pipeline encountered an error"
    },
    "Done": {
      "Type": "Succeed",
      "Comment": "Review pipeline completed successfully"
    }
  }
}
