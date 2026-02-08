# Required Lambda Functions for Step Functions

This document lists all Lambda functions required by the Step Functions state machine.

## Status Legend

- ✅ **Implemented** - Handler code exists in `src/`
- 🔨 **To Implement** - Needs to be created
- 📝 **Signature Only** - Interface defined, needs implementation

---

## Lambda Functions

### 1. manga-pipeline-check-quota 🔨

**Purpose**: Check if daily video quota has been reached

**Handler**: `src/quota/check_handler.py`

**Input**:
```json
{}
```

**Output**:
```json
{
  "quota_reached": false,
  "daily_count": 3,
  "daily_quota": 10
}
```

**Logic**:
1. Read `daily_quota` from settings (environment variable)
2. Query DynamoDB for today's video count
3. Return comparison result

**Environment Variables**:
- `DYNAMODB_COUNTER_TABLE` - Counter table name
- `DAILY_QUOTA` - Maximum videos per day (default: 10)

---

### 2. manga-pipeline-fetcher ✅

**Purpose**: Fetch manga chapters and download panel images

**Handler**: `src/fetcher/handler.py` (exists)

**Input**:
```json
{}
```

**Output**:
```json
{
  "status": "success",
  "job_id": "job-abc123",
  "manga_id": "manga-456",
  "manga_title": "Sample Manga"
}
```

Or:
```json
{
  "status": "no_manga_available"
}
```

**Status**: ✅ Implemented

---

### 3. manga-pipeline-scriptgen ✅

**Purpose**: Generate Vietnamese narration script using LLM

**Handler**: `src/scriptgen/handler.py` (exists)

**Input**:
```json
{
  "job_id": "job-abc123"
}
```

**Output**:
```json
{
  "job_id": "job-abc123",
  "script_generated": true,
  "segment_count": 45
}
```

**Status**: ✅ Implemented

---

### 4. manga-pipeline-ttsgen ✅

**Purpose**: Generate Vietnamese TTS audio using Edge TTS

**Handler**: `src/ttsgen/handler.py` (exists)

**Input**:
```json
{
  "job_id": "job-abc123"
}
```

**Output**:
```json
{
  "job_id": "job-abc123",
  "audio_generated": true,
  "segment_count": 45,
  "continuation_token": null
}
```

**Status**: ✅ Implemented

---

### 5. manga-pipeline-start-renderer 🔨

**Purpose**: Launch EC2 Spot instance for video rendering

**Handler**: `src/renderer/start_handler.py`

**Input**:
```json
{
  "job_id": "job-abc123",
  "task_token": "AQCEAAAAKgAAAA..."
}
```

**Output**:
```json
{
  "job_id": "job-abc123",
  "instance_id": "i-0abcd1234efgh5678",
  "instance_type": "c5.2xlarge",
  "spot_request_id": "sir-abc123"
}
```

**Logic**:
1. Create user-data script that:
   - Sets `JOB_ID` and `TASK_TOKEN` environment variables
   - Clones repository
   - Installs dependencies
   - Runs `python -m src.renderer.main`
2. Request EC2 Spot instance with user-data
3. Return instance details

**IAM Permissions**:
- `ec2:RequestSpotInstances`
- `ec2:CreateTags`
- `ec2:DescribeSpotInstanceRequests`
- `iam:PassRole` (for instance profile)

**Environment Variables**:
- `RENDERER_AMI_ID` - AMI with Python/FFmpeg pre-installed
- `RENDERER_INSTANCE_TYPE` - Instance type (default: c5.2xlarge)
- `RENDERER_SECURITY_GROUP_ID` - Security group
- `RENDERER_SUBNET_ID` - Subnet for instance
- `RENDERER_IAM_INSTANCE_PROFILE` - IAM instance profile ARN

---

### 6. manga-pipeline-renderer-callback 📝

**Purpose**: Placeholder for renderer callback (actual callback happens from EC2)

**Handler**: Not used (callback is sent from EC2 instance)

**Notes**:
- The EC2 instance running `src/renderer/main.py` calls `SendTaskSuccess`/`SendTaskFailure` directly
- This function name is referenced in ASL but never invoked
- Can be removed or used as a wrapper if needed

**EC2 Callback Code** (in `src/renderer/main.py`):
```python
import boto3
import json
import os

sfn = boto3.client('stepfunctions')
task_token = os.environ.get('TASK_TOKEN')

try:
    # ... render video ...
    sfn.send_task_success(
        taskToken=task_token,
        output=json.dumps({
            "job_id": job_id,
            "status": "completed"
        })
    )
except Exception as e:
    sfn.send_task_failure(
        taskToken=task_token,
        error="RenderError",
        cause=str(e)
    )
```

---

### 7. manga-pipeline-start-uploader 🔨

**Purpose**: Launch EC2 Spot instance for YouTube upload

**Handler**: `src/uploader/start_handler.py`

**Input**:
```json
{
  "job_id": "job-abc123",
  "task_token": "AQCEAAAAKgAAAA..."
}
```

**Output**:
```json
{
  "job_id": "job-abc123",
  "instance_id": "i-0abcd1234efgh5678",
  "instance_type": "t3.medium",
  "spot_request_id": "sir-xyz789"
}
```

**Logic**:
1. Create user-data script that:
   - Sets `JOB_ID` and `TASK_TOKEN` environment variables
   - Clones repository
   - Installs dependencies
   - Runs `python -m src.uploader.main`
2. Request EC2 Spot instance with user-data
3. Return instance details

**IAM Permissions**:
- `ec2:RequestSpotInstances`
- `ec2:CreateTags`
- `ec2:DescribeSpotInstanceRequests`
- `iam:PassRole` (for instance profile)

**Environment Variables**:
- `UPLOADER_AMI_ID` - AMI with Python pre-installed
- `UPLOADER_INSTANCE_TYPE` - Instance type (default: t3.medium)
- `UPLOADER_SECURITY_GROUP_ID` - Security group
- `UPLOADER_SUBNET_ID` - Subnet for instance
- `UPLOADER_IAM_INSTANCE_PROFILE` - IAM instance profile ARN

---

### 8. manga-pipeline-uploader-callback 📝

**Purpose**: Placeholder for uploader callback (actual callback happens from EC2)

**Handler**: Not used (callback is sent from EC2 instance)

**Notes**:
- Similar to renderer-callback, the EC2 instance calls Step Functions directly
- The instance running `src/uploader/main.py` already triggers cleanup Lambda

**EC2 Callback Code** (in `src/uploader/main.py`):
```python
import boto3
import json
import os

sfn = boto3.client('stepfunctions')
task_token = os.environ.get('TASK_TOKEN')

try:
    # ... upload video ...
    sfn.send_task_success(
        taskToken=task_token,
        output=json.dumps({
            "job_id": job_id,
            "youtube_url": youtube_url,
            "status": "completed"
        })
    )
except YouTubeQuotaError as e:
    sfn.send_task_failure(
        taskToken=task_token,
        error="YouTubeQuotaError",
        cause=str(e)
    )
except Exception as e:
    sfn.send_task_failure(
        taskToken=task_token,
        error="UploadError",
        cause=str(e)
    )
```

---

### 9. manga-pipeline-cleanup ✅

**Purpose**: Clean up temporary S3 artifacts

**Handler**: `src/cleanup/handler.py` (exists)

**Input**:
```json
{
  "job_id": "job-abc123"
}
```

**Output**:
```json
{
  "job_id": "job-abc123",
  "objects_deleted": 157,
  "bytes_freed": 524288000
}
```

**Status**: ✅ Implemented

---

### 10. manga-pipeline-increment-counter 🔨

**Purpose**: Increment daily video counter in DynamoDB

**Handler**: `src/quota/increment_handler.py`

**Input**:
```json
{
  "job_id": "job-abc123"
}
```

**Output**:
```json
{
  "daily_count": 4,
  "date": "2026-02-07",
  "job_id": "job-abc123"
}
```

**Logic**:
1. Get current date (YYYY-MM-DD)
2. Increment counter for today in DynamoDB using atomic counter
3. Return new count

**DynamoDB Table**: `manga-pipeline-counters`

**Table Schema**:
```
PK: date (String) - "2026-02-07"
Attributes:
  - count (Number) - Number of videos processed today
  - updated_at (String) - ISO timestamp of last update
```

**DynamoDB Operation**:
```python
table.update_item(
    Key={"date": today},
    UpdateExpression="ADD #count :inc SET updated_at = :now",
    ExpressionAttributeNames={"#count": "count"},
    ExpressionAttributeValues={
        ":inc": 1,
        ":now": datetime.now(UTC).isoformat()
    },
    ReturnValues="UPDATED_NEW"
)
```

**Environment Variables**:
- `DYNAMODB_COUNTER_TABLE` - Counter table name

---

### 11. manga-pipeline-handle-error 🔨

**Purpose**: Update job to failed status and log error details

**Handler**: `src/error/handler.py`

**Input**:
```json
{
  "job_id": "job-abc123",
  "error": {
    "Error": "States.TaskFailed",
    "Cause": "{\"errorMessage\": \"Timeout\", ...}"
  },
  "state": "GenerateScript",
  "execution_id": "arn:aws:states:us-east-1:123:execution:manga-pipeline:abc"
}
```

**Output**:
```json
{
  "job_id": "job-abc123",
  "status": "failed",
  "error_logged": true
}
```

**Logic**:
1. Parse error details
2. Update job record in DynamoDB:
   - Set `status = "failed"`
   - Set `error_message = error.Cause`
   - Set `failed_at = current_timestamp`
   - Set `failed_state = state`
3. Log error to CloudWatch with structured format
4. Optionally send notification (SNS/SES)

**Environment Variables**:
- `DYNAMODB_JOBS_TABLE` - Jobs table name
- `ERROR_NOTIFICATION_TOPIC_ARN` - (Optional) SNS topic for alerts

---

## Summary

| Status | Count | Functions |
|--------|-------|-----------|
| ✅ Implemented | 4 | fetcher, scriptgen, ttsgen, cleanup |
| 🔨 To Implement | 4 | check-quota, start-renderer, start-uploader, increment-counter, handle-error |
| 📝 Signature Only | 2 | renderer-callback, uploader-callback (not needed) |

---

## Implementation Priority

### High Priority (Required for MVP)
1. **manga-pipeline-check-quota** - Needed to prevent quota violations
2. **manga-pipeline-increment-counter** - Needed for quota tracking
3. **manga-pipeline-handle-error** - Needed for proper error handling

### Medium Priority (Needed for EC2 orchestration)
4. **manga-pipeline-start-renderer** - Can test locally first
5. **manga-pipeline-start-uploader** - Can test locally first

### Low Priority (Optional)
6. **renderer-callback** - Not needed if EC2 calls Step Functions directly
7. **uploader-callback** - Not needed if EC2 calls Step Functions directly

---

## Testing Strategy

### Unit Tests
Each Lambda function should have unit tests in `tests/unit/`:
- `test_check_quota_handler.py`
- `test_increment_counter_handler.py`
- `test_handle_error_handler.py`
- `test_start_renderer_handler.py`
- `test_start_uploader_handler.py`

### Integration Tests
Test the full state machine execution:
1. Mock all Lambda functions
2. Execute state machine with test input
3. Verify state transitions
4. Verify error handling and retries

### Local Testing
Use Step Functions Local:
```bash
docker run -p 8083:8083 amazon/aws-stepfunctions-local

aws stepfunctions create-state-machine \
  --endpoint-url http://localhost:8083 \
  --definition file://pipeline.asl.json \
  --name manga-pipeline-local \
  --role-arn arn:aws:iam::123456789012:role/DummyRole
```

---

## Deployment Order

1. Deploy DynamoDB tables (jobs, counters)
2. Deploy existing Lambda functions (fetcher, scriptgen, ttsgen, cleanup)
3. Deploy new Lambda functions (check-quota, increment-counter, handle-error)
4. Deploy EC2 launcher functions (start-renderer, start-uploader)
5. Create IAM roles and policies
6. Deploy Step Functions state machine
7. Set up EventBridge scheduled rule
8. Test end-to-end execution

---

## IAM Roles Required

### StepFunctionsExecutionRole
Permissions:
- `lambda:InvokeFunction` (all pipeline Lambda functions)
- `logs:CreateLogGroup`, `logs:CreateLogStream`, `logs:PutLogEvents`
- `xray:PutTraceSegments`, `xray:PutTelemetryRecords`

### Lambda Execution Roles
Each Lambda needs:
- `logs:CreateLogGroup`, `logs:CreateLogStream`, `logs:PutLogEvents`
- `dynamodb:GetItem`, `dynamodb:PutItem`, `dynamodb:UpdateItem`
- `s3:GetObject`, `s3:PutObject`, `s3:DeleteObject`
- `secretsmanager:GetSecretValue` (for API keys)

### EC2 Instance Profile
For renderer/uploader instances:
- `s3:GetObject`, `s3:PutObject`
- `dynamodb:GetItem`, `dynamodb:UpdateItem`
- `secretsmanager:GetSecretValue`
- `states:SendTaskSuccess`, `states:SendTaskFailure`, `states:SendTaskHeartbeat`
- `lambda:InvokeFunction` (cleanup)
