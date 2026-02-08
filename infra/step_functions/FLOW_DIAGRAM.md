# Step Functions State Machine Flow Diagram

## Overview Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│                    Manga-to-Video Pipeline                          │
│                  (Step Functions State Machine)                     │
└─────────────────────────────────────────────────────────────────────┘

  EventBridge
  (Daily Cron)
      │
      ▼
┌─────────────┐
│ CheckQuota  │ ◄─────────────────────────────────────┐
└──────┬──────┘                                        │
       │                                               │
       ├─── quota_reached = true ──► [QuotaReached]   │
       │                             (Succeed)         │
       │                                               │
       ├─── quota_reached = false                      │
       ▼                                               │
┌─────────────┐                                        │
│ FetchManga  │                                        │
└──────┬──────┘                                        │
       │                                               │
       ├─── no_manga_available ──► [NoMangaAvailable] │
       │                           (Succeed)           │
       │                                               │
       ├─── success                                    │
       ▼                                               │
┌──────────────────┐                                   │
│ PrepareScriptInput│                                  │
└──────┬───────────┘                                   │
       │                                               │
       ▼                                               │
┌─────────────────┐                                    │
│ GenerateScript  │                                    │
└──────┬──────────┘                                    │
       │                                               │
       ▼                                               │
┌─────────────┐                                        │
│ GenerateTTS │                                        │
└──────┬──────┘                                        │
       │                                               │
       ▼                                               │
┌────────────────┐                                     │
│ StartRenderer  │                                     │
└──────┬─────────┘                                     │
       │                                               │
       ▼                                               │
┌────────────────┐                                     │
│ WaitForRender  │ (Callback Pattern)                 │
│  ⏱ 4 hours     │ Retry on timeout (Spot interrupt)  │
│  💓 5 min      │                                     │
└──────┬─────────┘                                     │
       │                                               │
       ▼                                               │
┌────────────────┐                                     │
│ StartUploader  │                                     │
└──────┬─────────┘                                     │
       │                                               │
       ▼                                               │
┌────────────────┐                                     │
│ WaitForUpload  │ (Callback Pattern)                 │
│  ⏱ 2 hours     │ Retry on timeout (Spot interrupt)  │
│  💓 5 min      │                                     │
└──────┬─────────┘                                     │
       │                                               │
       ├─── YouTubeQuotaError ──► [QuotaReached]      │
       │                         (Succeed)             │
       │                                               │
       ▼                                               │
┌─────────────┐                                        │
│   Cleanup   │                                        │
└──────┬──────┘                                        │
       │                                               │
       ▼                                               │
┌──────────────────┐                                   │
│ IncrementCounter │                                   │
└──────┬───────────┘                                   │
       │                                               │
       ▼                                               │
┌──────────────────┐                                   │
│ CheckMoreVideos  │                                   │
└──────┬───────────┘                                   │
       │                                               │
       ├─── count < quota ────────────────────────────┘
       │                                        (Loop)
       │
       ├─── count >= quota ──► [Done]
       │                      (Succeed)
       ▼

  Error Path (Any state with Catch)
       │
       ▼
┌─────────────┐
│ HandleError │ Update job to failed, log error
└──────┬──────┘
       │
       └─────────────────────────────────────────────┐
                                                     │
                                                     ▼
                                          ┌──────────────────┐
                                          │ CheckMoreVideos  │
                                          └──────────────────┘
                                          (Continue with next video)
```

## Detailed State Transitions

### 1. Quota Check Flow

```
CheckQuota
    │
    ├─ Query DynamoDB counter table
    ├─ Get today's count
    ├─ Compare with daily_quota setting
    │
    ▼
QuotaChoice (Choice State)
    │
    ├─ IF quota_reached = true
    │  └──► QuotaReached (Succeed) ■
    │
    └─ ELSE
       └──► FetchManga
```

### 2. Fetch and Process Flow

```
FetchManga
    │
    ├─ Call NetTruyen API
    ├─ Download chapter images to S3
    ├─ Create job record in DynamoDB
    │
    ▼
FetchChoice (Choice State)
    │
    ├─ IF status = "no_manga_available"
    │  └──► NoMangaAvailable (Succeed) ■
    │
    └─ ELSE (status = "success")
       └──► PrepareScriptInput
              │
              └──► GenerateScript (LLM)
                      │
                      └──► GenerateTTS (Edge TTS)
```

### 3. Rendering Flow

```
GenerateTTS
    │
    ▼
StartRenderer
    │
    ├─ Request EC2 Spot instance
    ├─ Pass job_id and task_token via user-data
    ├─ EC2 boots and runs src/renderer/main.py
    │
    ▼
WaitForRender (Callback Pattern)
    │
    ├─ EC2 sends heartbeat every 5 min
    ├─ Timeout: 4 hours
    │
    ├─ ON SUCCESS:
    │  └─ EC2 calls SendTaskSuccess(task_token)
    │     └──► StartUploader
    │
    ├─ ON TIMEOUT (Spot Interruption):
    │  └─ Retry (2x) → Launch new instance
    │
    └─ ON ERROR:
       └─ EC2 calls SendTaskFailure(task_token)
          └──► HandleError
```

### 4. Upload Flow

```
StartUploader
    │
    ├─ Request EC2 Spot instance
    ├─ Pass job_id and task_token via user-data
    ├─ EC2 boots and runs src/uploader/main.py
    │
    ▼
WaitForUpload (Callback Pattern)
    │
    ├─ EC2 sends heartbeat every 5 min
    ├─ Timeout: 2 hours
    │
    ├─ ON SUCCESS:
    │  └─ EC2 calls SendTaskSuccess(task_token)
    │     └──► Cleanup
    │
    ├─ ON QUOTA ERROR:
    │  └─ EC2 calls SendTaskFailure(error="YouTubeQuotaError")
    │     └──► QuotaReached (Succeed) ■
    │
    ├─ ON TIMEOUT (Spot Interruption):
    │  └─ Retry (2x) → Launch new instance
    │
    └─ ON OTHER ERROR:
       └─ EC2 calls SendTaskFailure(task_token)
          └──► HandleError
```

### 5. Cleanup and Counter Flow

```
Cleanup
    │
    ├─ Delete S3 objects: jobs/{job_id}/*
    ├─ Update job record with cleanup_at
    ├─ Return metrics (objects_deleted, bytes_freed)
    │
    ▼
IncrementCounter
    │
    ├─ Atomic increment DynamoDB counter for today
    ├─ Return new count
    │
    ▼
CheckMoreVideos (Choice State)
    │
    ├─ IF daily_count < daily_quota
    │  └──► FetchManga (LOOP - process next video)
    │
    └─ ELSE daily_count >= daily_quota
       └──► Done (Succeed) ■
```

### 6. Error Handling Flow

```
Any State Error (Catch Block)
    │
    ▼
HandleError
    │
    ├─ Parse error details
    ├─ Update job status = "failed"
    ├─ Set error_message and failed_at
    ├─ Log to CloudWatch
    ├─ (Optional) Send SNS notification
    │
    ▼
CheckMoreVideos
    │
    └─ Continue with next video (don't let one failure stop pipeline)
```

## Retry Strategies

### Lambda Tasks (Transient Errors)

```
Retry Configuration:
- ErrorEquals: ["States.TaskFailed", "States.Timeout"]
- IntervalSeconds: 60
- MaxAttempts: 2
- BackoffRate: 2.0

Example:
Attempt 1: Fail at 10:00:00
Attempt 2: Retry at 10:01:00 (60s wait)
Attempt 3: Retry at 10:03:00 (120s wait)
Final: Catch → HandleError
```

### EC2 Spot Interruption

```
Retry Configuration:
- ErrorEquals: ["States.Timeout", "States.HeartbeatTimeout"]
- IntervalSeconds: 60
- MaxAttempts: 2
- BackoffRate: 1.5

Scenario:
1. Instance i-abc123 starts rendering
2. Spot interruption at 50% progress
3. Instance saves checkpoint to S3
4. Step Functions detects heartbeat timeout
5. Retry → Launch new instance i-def456
6. New instance loads checkpoint, resumes rendering
```

### YouTube Quota Error (No Retry)

```
Special Catch:
- ErrorEquals: ["YouTubeQuotaError"]
- Next: QuotaReached (Succeed)
- MaxAttempts: 0 (Don't retry quota errors)

Reason: YouTube quota resets at midnight Pacific Time.
Retrying won't help until next day.
```

## Loop Mechanism

The state machine processes multiple videos in a single execution:

```
Daily Quota = 10

Execution Flow:
┌──────────────────────────────────────────────┐
│ Video 1: FetchManga → ... → Increment (1)   │
│          CheckMoreVideos: 1 < 10 → Loop     │
├──────────────────────────────────────────────┤
│ Video 2: FetchManga → ... → Increment (2)   │
│          CheckMoreVideos: 2 < 10 → Loop     │
├──────────────────────────────────────────────┤
│ Video 3: FetchManga (no_manga_available)    │
│          NoMangaAvailable → Succeed ■       │
└──────────────────────────────────────────────┘

OR

┌──────────────────────────────────────────────┐
│ Video 1: FetchManga → ... → Increment (1)   │
│          CheckMoreVideos: 1 < 10 → Loop     │
├──────────────────────────────────────────────┤
│ ...                                          │
├──────────────────────────────────────────────┤
│ Video 10: FetchManga → ... → Increment (10) │
│           CheckMoreVideos: 10 >= 10 → Done ■│
└──────────────────────────────────────────────┘
```

## Execution Time Estimates

```
Single Video (Success):
├─ CheckQuota:         ~1s
├─ FetchManga:         ~60-300s (1-5 min)
├─ GenerateScript:     ~120-600s (2-10 min)
├─ GenerateTTS:        ~180-600s (3-10 min)
├─ StartRenderer:      ~30-120s (0.5-2 min)
├─ WaitForRender:      ~1800-10800s (30min-3hr)
├─ StartUploader:      ~30-120s (0.5-2 min)
├─ WaitForUpload:      ~600-5400s (10min-1.5hr)
├─ Cleanup:            ~10-60s
├─ IncrementCounter:   ~1s
└─ CheckMoreVideos:    ~1s
    ──────────────────────────────────────
    Total: ~45-120 min per video

10 Videos (Quota):
└─ Total: ~7.5-20 hours
```

## State Machine Limits

AWS Step Functions Standard Workflow Limits:
- Max execution time: 1 year
- Max execution history: 25,000 events
- Max input/output size: 262,144 bytes (256 KB)

Pipeline Compliance:
✓ Execution time: ~20 hours max (well under limit)
✓ State transitions: ~200 per execution (well under limit)
✓ Data size: <10 KB per state (well under limit)

## Monitoring Points

Key metrics to monitor:

```
CloudWatch Alarms:
├─ ExecutionsFailed > 0
├─ ExecutionsTimedOut > 0
├─ RenderTimeoutRetries > 2 (Spot issues)
├─ UploadTimeoutRetries > 2 (Spot issues)
├─ YouTubeQuotaErrors > 0 (Quota management)
└─ HandleErrorInvocations > 5 (Overall failures)

CloudWatch Dashboards:
├─ Execution duration by state
├─ Success rate by video
├─ Daily video count vs quota
├─ Cost per video (Lambda + EC2 + S3)
└─ Error distribution by state
```

## Cost Breakdown

Per execution (10 videos):

```
Step Functions:
├─ State transitions: ~200 @ $0.000025 = $0.005

Lambda:
├─ CheckQuota: 10 @ $0.0000002 = $0.000002
├─ FetchManga: 10 @ $0.001 = $0.01
├─ GenerateScript: 10 @ $0.005 = $0.05
├─ GenerateTTS: 10 @ $0.003 = $0.03
├─ StartRenderer: 10 @ $0.0001 = $0.001
├─ StartUploader: 10 @ $0.0001 = $0.001
├─ Cleanup: 10 @ $0.0001 = $0.001
├─ IncrementCounter: 10 @ $0.00001 = $0.0001
└─ HandleError: ~1 @ $0.0001 = $0.0001

EC2 Spot:
├─ Renderer: 10 * 2hr * $0.10/hr = $2.00
└─ Uploader: 10 * 1hr * $0.02/hr = $0.20

S3:
└─ Storage + Transfer: ~$0.50

Total: ~$2.85 per execution (10 videos)
Monthly (30 days): ~$85.50
```
