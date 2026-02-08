# Step Functions State Machine

This directory contains the AWS Step Functions state machine definition for the manga-to-video pipeline.

## State Machine Overview

The `pipeline.asl.json` file defines a state machine that orchestrates the entire manga-to-video pipeline:

```
CheckQuota → FetchManga → GenerateScript → GenerateTTS →
StartRenderer → WaitForRender → StartUploader → WaitForUpload →
Cleanup → IncrementCounter → CheckMoreVideos (loop or Done)
```

## State Details

### 1. CheckQuota
- **Type**: Lambda Task
- **Purpose**: Check if daily video quota has been reached
- **Output**: `quota_reached` boolean and `daily_quota` count
- **Next**: QuotaChoice → QuotaReached or FetchManga

### 2. FetchManga
- **Type**: Lambda Task (fetcher handler)
- **Purpose**: Fetch manga chapters and download panel images to S3
- **Timeout**: 900s (15 min)
- **Retry**: 2 attempts with 60s interval
- **Output**: `status` ("no_manga_available" or "success") and `job_id`
- **Next**: FetchChoice → NoMangaAvailable or GenerateScript

### 3. GenerateScript
- **Type**: Lambda Task (scriptgen handler)
- **Purpose**: Generate Vietnamese narration script using LLM
- **Timeout**: 900s (15 min)
- **Retry**: 2 attempts with 60s interval
- **Next**: GenerateTTS

### 4. GenerateTTS
- **Type**: Lambda Task (ttsgen handler)
- **Purpose**: Generate Vietnamese TTS audio using Edge TTS
- **Timeout**: 900s (15 min)
- **Retry**: 2 attempts with 60s interval
- **Next**: StartRenderer

### 5. StartRenderer
- **Type**: Lambda Task
- **Purpose**: Launch EC2 Spot instance for video rendering
- **Timeout**: 300s (5 min)
- **Retry**: 3 attempts with 30s interval
- **Next**: WaitForRender

### 6. WaitForRender
- **Type**: Task with waitForTaskToken (callback pattern)
- **Purpose**: Wait for rendering to complete on EC2
- **Timeout**: 14400s (4 hours)
- **Heartbeat**: 300s (5 min)
- **Retry**: 2 attempts on timeout (handles Spot interruption)
- **Next**: StartUploader

### 7. StartUploader
- **Type**: Lambda Task
- **Purpose**: Launch EC2 Spot instance for YouTube upload
- **Timeout**: 300s (5 min)
- **Retry**: 3 attempts with 30s interval
- **Next**: WaitForUpload

### 8. WaitForUpload
- **Type**: Task with waitForTaskToken (callback pattern)
- **Purpose**: Wait for YouTube upload to complete on EC2
- **Timeout**: 7200s (2 hours)
- **Heartbeat**: 300s (5 min)
- **Retry**: 2 attempts on timeout (handles Spot interruption)
- **Special**: Catches YouTubeQuotaError and goes to QuotaReached
- **Next**: Cleanup

### 9. Cleanup
- **Type**: Lambda Task (cleanup handler)
- **Purpose**: Delete temporary S3 artifacts for the job
- **Timeout**: 300s (5 min)
- **Retry**: 3 attempts with 30s interval
- **Catch**: Continues even if cleanup fails
- **Next**: IncrementCounter

### 10. IncrementCounter
- **Type**: Lambda Task
- **Purpose**: Increment daily video counter in DynamoDB
- **Timeout**: 60s
- **Retry**: 5 attempts with 5s interval
- **Catch**: Continues even if increment fails
- **Next**: CheckMoreVideos

### 11. CheckMoreVideos
- **Type**: Choice State
- **Purpose**: Decide whether to process another video
- **Condition**: If `daily_count < daily_quota` → FetchManga (loop)
- **Default**: Done

### 12. HandleError
- **Type**: Lambda Task
- **Purpose**: Update job to failed status and log error details
- **Next**: CheckMoreVideos (continue with next video)

### Terminal States

- **QuotaReached**: Success state when daily quota is reached
- **NoMangaAvailable**: Success state when no manga is available
- **Done**: Success state when pipeline completes

## Required Lambda Functions

The state machine requires these Lambda functions to be deployed:

1. `manga-pipeline-check-quota` - Checks daily quota
2. `manga-pipeline-fetcher` - Fetches manga (exists: src/fetcher/handler.py)
3. `manga-pipeline-scriptgen` - Generates script (exists: src/scriptgen/handler.py)
4. `manga-pipeline-ttsgen` - Generates TTS (exists: src/ttsgen/handler.py)
5. `manga-pipeline-start-renderer` - Starts renderer EC2 instance
6. `manga-pipeline-renderer-callback` - Callback for renderer completion
7. `manga-pipeline-start-uploader` - Starts uploader EC2 instance
8. `manga-pipeline-uploader-callback` - Callback for uploader completion
9. `manga-pipeline-cleanup` - Cleanup handler (exists: src/cleanup/handler.py)
10. `manga-pipeline-increment-counter` - Increments daily counter
11. `manga-pipeline-handle-error` - Error handler

## Callback Pattern

The renderer and uploader use the Step Functions callback pattern:

1. StartRenderer/StartUploader Lambda receives a task token from Step Functions
2. Lambda launches EC2 instance and passes the task token via user-data or SSM
3. EC2 instance runs renderer/uploader main.py
4. When complete, EC2 sends task token back using SendTaskSuccess/SendTaskFailure
5. Step Functions continues to next state

Example callback code:
```python
import boto3

sfn = boto3.client('stepfunctions')

# On success
sfn.send_task_success(
    taskToken=task_token,
    output=json.dumps({"job_id": job_id, "status": "completed"})
)

# On failure
sfn.send_task_failure(
    taskToken=task_token,
    error="RenderError",
    cause=str(error)
)
```

## Error Handling

### Retry Strategy
- All Lambda tasks: Exponential backoff (2x) with 2-5 attempts
- Long-running tasks (render/upload): Retry on timeout to handle Spot interruption
- Counter increment: 5 attempts to ensure count accuracy

### Catch Strategy
- Failed videos go to HandleError → CheckMoreVideos (next video)
- YouTubeQuotaError → QuotaReached (stop processing)
- Cleanup and counter errors are logged but don't fail the pipeline

### Spot Interruption Handling
- WaitForRender and WaitForUpload have heartbeat monitoring (300s)
- On timeout, retry automatically launches new Spot instance
- Renderer/uploader checkpoints allow resuming from interruption

## Quota Loop

The state machine processes multiple videos until quota is reached:

```
Start → CheckQuota (count=0)
  → FetchManga → ... → IncrementCounter (count=1)
  → CheckMoreVideos (1 < quota?) → Yes → FetchManga
  → ... → IncrementCounter (count=2)
  → CheckMoreVideos (2 < quota?) → Yes → FetchManga
  → ... → IncrementCounter (count=3)
  → CheckMoreVideos (3 < quota?) → No → Done
```

## Deployment

### Using AWS CLI

1. Replace placeholders in ASL JSON:
```bash
REGION="us-east-1"
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)

sed -e "s/\${AWS::Region}/$REGION/g" \
    -e "s/\${AWS::AccountId}/$ACCOUNT_ID/g" \
    pipeline.asl.json > pipeline-deployed.asl.json
```

2. Create the state machine:
```bash
aws stepfunctions create-state-machine \
  --name manga-pipeline \
  --role-arn arn:aws:iam::$ACCOUNT_ID:role/StepFunctionsExecutionRole \
  --definition file://pipeline-deployed.asl.json
```

3. Start execution:
```bash
aws stepfunctions start-execution \
  --state-machine-arn arn:aws:states:$REGION:$ACCOUNT_ID:stateMachine:manga-pipeline \
  --input '{}'
```

### Using Terraform/CloudFormation

See `infra/terraform/` or `infra/cloudformation/` for IaC templates.

## Monitoring

### CloudWatch Metrics
- `ExecutionsFailed` - Failed executions
- `ExecutionsTimedOut` - Timed out executions
- `ExecutionThrottled` - Throttled executions

### CloudWatch Logs
Each Lambda function logs to CloudWatch Logs with structured JSON logging.

### X-Ray Tracing
Enable X-Ray tracing for end-to-end visibility:
```bash
aws stepfunctions update-state-machine \
  --state-machine-arn <arn> \
  --tracing-configuration enabled=true
```

## Testing

### Manual Testing
```bash
# Start execution with test input
aws stepfunctions start-execution \
  --state-machine-arn <arn> \
  --name test-execution-$(date +%s) \
  --input '{}'

# Get execution status
aws stepfunctions describe-execution \
  --execution-arn <execution-arn>

# Get execution history
aws stepfunctions get-execution-history \
  --execution-arn <execution-arn>
```

### Integration Testing
See `tests/integration/test_step_functions.py` for automated tests.

## Cost Optimization

- State transitions: ~$0.000025 per transition
- Typical execution: ~20 state transitions = $0.0005
- Daily cost (10 videos): ~$0.005
- Monthly cost: ~$0.15

Most cost comes from Lambda, EC2 Spot, and S3 storage, not Step Functions.

## Troubleshooting

### Common Issues

**Execution stuck in WaitForRender/WaitForUpload**
- Check EC2 instance logs: `/var/log/user-data.log`
- Verify task token is passed correctly
- Check heartbeat is being sent every 5 minutes

**YouTubeQuotaError on first video**
- Check YouTube API quota in Google Console
- Verify quota reset time (Pacific Time midnight)
- Check counter was reset properly

**Retry loop on FetchManga**
- Check if manga source API is down
- Verify network connectivity from Lambda
- Check rate limiting on manga source

**HandleError not updating job**
- Check DynamoDB permissions
- Verify job_id is passed correctly through states
- Check error handler Lambda logs

## Architecture Diagram

```
┌─────────────────┐
│  EventBridge    │ (Scheduled trigger)
│  Rule (Daily)   │
└────────┬────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────┐
│              Step Functions State Machine                │
├─────────────────────────────────────────────────────────┤
│  CheckQuota ──► FetchManga ──► GenerateScript ──►       │
│  GenerateTTS ──► StartRenderer ──► WaitForRender ──►    │
│  StartUploader ──► WaitForUpload ──► Cleanup ──►        │
│  IncrementCounter ──► CheckMoreVideos                    │
│                         │         │                      │
│                         │         └──► Done (Succeed)    │
│                         └──────► FetchManga (Loop)       │
└─────────────────────────────────────────────────────────┘
         │                    │                   │
         ▼                    ▼                   ▼
    ┌────────┐          ┌──────────┐        ┌─────────┐
    │ Lambda │          │ EC2 Spot │        │   S3    │
    └────────┘          └──────────┘        └─────────┘
         │                    │                   │
         ▼                    ▼                   ▼
    ┌─────────────────────────────────────────────────┐
    │              DynamoDB (Jobs Table)               │
    └─────────────────────────────────────────────────┘
```
