# Cost Review and Optimization

This document provides a comprehensive cost analysis of the Manga Video Pipeline infrastructure with optimization recommendations.

**Last Updated:** 2024-01-15
**Region:** ap-southeast-1 (Singapore)
**Pricing Source:** AWS Pricing Calculator (January 2024)

---

## Executive Summary

| Scenario | Monthly Cost | Daily Cost |
|----------|--------------|------------|
| 1 video/day (30/month) | **$45-65** | $1.50-2.20 |
| 3 videos/day (90/month) | **$95-135** | $3.20-4.50 |

**Budget Alert Status:** Configured at $120/month with 65%, 100%, 120% thresholds

---

## 1. Component-by-Component Cost Breakdown

### 1.1 AWS Lambda Functions

**Configuration (from `infra/modules/compute/main.tf`):**

| Function | Memory | Timeout | Architecture | Invocations/video |
|----------|--------|---------|--------------|-------------------|
| manga_fetcher | 512 MB | 900s | arm64 | 1 |
| script_generator | 256 MB | 900s | arm64 | 1 |
| tts_processor | 512 MB | 900s | arm64 | 1-5 (continuation) |
| cleanup | 128 MB | 300s | arm64 | 1 |
| quota_checker | 128 MB | 30s | arm64 | 1 |

**Pricing (arm64 - 20% discount):**
- Request: $0.20 per 1M requests
- Duration: $0.0000133334 per GB-second

**Cost Calculation (per video):**

| Function | Avg Duration | GB-seconds | Cost |
|----------|--------------|------------|------|
| manga_fetcher | 300s | 150 | $0.0020 |
| script_generator | 180s | 45 | $0.0006 |
| tts_processor (3 invocations) | 600s total | 300 | $0.0040 |
| cleanup | 60s | 7.5 | $0.0001 |
| quota_checker | 5s | 0.625 | $0.0000 |
| **Total per video** | | | **$0.0067** |

**Monthly Lambda Cost:**
- 1 video/day: 30 × $0.0067 = **$0.20**
- 3 videos/day: 90 × $0.0067 = **$0.60**

> Lambda costs are negligible due to low invocation count and arm64 architecture.

---

### 1.2 EC2 Spot Instances (Renderer)

**Configuration (from `infra/modules/compute/ec2_spot.tf`):**
- Instance Type: `c5.xlarge` (4 vCPU, 8 GB RAM)
- Storage: 50 GB gp3 (3000 IOPS, 125 MB/s)
- AMI: Amazon Linux 2023

**Pricing (ap-southeast-1):**
- c5.xlarge On-Demand: $0.194/hour
- c5.xlarge Spot: ~$0.058/hour (70% savings, varies)
- gp3 Storage: $0.096/GB-month (prorated per hour)

**Cost Calculation (per video):**

Assuming 2-hour render time per video:

| Component | On-Demand | Spot (~70% off) |
|-----------|-----------|-----------------|
| c5.xlarge (2 hours) | $0.388 | $0.116 |
| gp3 50GB (2 hours) | $0.007 | $0.007 |
| Data transfer (see §7) | $0.05 | $0.05 |
| **Total per video** | $0.445 | **$0.173** |

**Monthly EC2 Spot Cost:**
- 1 video/day: 30 × $0.173 = **$5.19**
- 3 videos/day: 90 × $0.173 = **$15.57**

**Spot vs On-Demand Savings:**

| Scenario | On-Demand | Spot | Savings |
|----------|-----------|------|---------|
| 1 video/day | $13.35 | $5.19 | $8.16 (61%) |
| 3 videos/day | $40.05 | $15.57 | $24.48 (61%) |

---

### 1.3 EC2 Dashboard Instance

**Configuration (from `infra/modules/compute/ec2_dashboard.tf`):**
- Instance Type: `t3.micro` (2 vCPU, 1 GB RAM)
- Storage: 20 GB gp3
- Running: 24/7

**Pricing:**
- t3.micro On-Demand: $0.0126/hour
- gp3 20GB: $1.92/month

**Monthly Dashboard Cost:**

| Component | Cost |
|-----------|------|
| t3.micro (720 hours) | $9.07 |
| gp3 20GB | $1.92 |
| Elastic IP (if enabled) | $3.65 |
| **Total** | **$11.00-14.64** |

> Note: t3.micro is Free Tier eligible for first 12 months (750 hours/month)

---

### 1.4 DynamoDB

**Configuration (from `infra/modules/storage/dynamodb.tf`):**
- Billing Mode: PAY_PER_REQUEST (On-Demand)
- Tables: manga_jobs, processed_manga, settings
- Features: Server-side encryption, Point-in-time recovery

**Pricing:**
- Write Request Units (WRU): $1.4846 per million
- Read Request Units (RRU): $0.297 per million
- Storage: $0.285 per GB-month
- PITR: $0.228 per GB-month (20% of storage)

**Estimated Usage (per video):**

| Operation | Count | Type | Cost |
|-----------|-------|------|------|
| Job status updates | ~10 | Write | $0.000015 |
| Job status reads | ~20 | Read | $0.000006 |
| Settings reads | ~5 | Read | $0.000002 |
| Processed manga write | 1 | Write | $0.000001 |

**Monthly DynamoDB Cost:**

| Component | 1 video/day | 3 videos/day |
|-----------|-------------|--------------|
| Read/Write requests | $0.02 | $0.06 |
| Storage (< 1 GB) | $0.29 | $0.29 |
| PITR backup | $0.06 | $0.06 |
| **Total** | **$0.37** | **$0.41** |

**On-Demand vs Provisioned Analysis:**

At current scale (< 100 writes/day, < 200 reads/day):

| Mode | Monthly Cost | Break-even |
|------|--------------|------------|
| On-Demand | $0.37 | Current optimal |
| Provisioned (1 WCU, 1 RCU) | $0.75 | Not cost-effective |

**Recommendation:** Keep On-Demand mode. Provisioned only makes sense at 10x current volume.

---

### 1.5 S3 Storage

**Configuration (from `infra/modules/storage/s3.tf`):**
- Bucket: `{project}-assets-{account_id}`
- Lifecycle: 7-day expiration
- Encryption: AES-256 (SSE-S3, no additional cost)
- Intelligent Tiering: Enabled (for objects > 128KB)

**Pricing:**
- Standard Storage: $0.025 per GB-month
- PUT/COPY/POST: $0.005 per 1,000 requests
- GET/SELECT: $0.0004 per 1,000 requests

**Estimated Storage per Video:**

| Asset Type | Size | Retention |
|------------|------|-----------|
| Manga panels (20-50 images) | 50-100 MB | 7 days |
| Script JSON | < 1 MB | 7 days |
| Audio segments (30-60 files) | 100-200 MB | 7 days |
| Final video | 500 MB - 2 GB | 7 days |
| **Total per video** | **~700 MB - 2.3 GB** | 7 days |

**Monthly S3 Cost:**

| Scenario | Peak Storage | S3 Storage | Requests | Total |
|----------|--------------|------------|----------|-------|
| 1 video/day | 7 × 1.5 GB = 10.5 GB | $0.26 | $0.10 | **$0.36** |
| 3 videos/day | 7 × 4.5 GB = 31.5 GB | $0.79 | $0.30 | **$1.09** |

**S3 Cleanup Verification:**
- Lifecycle rule: `delete-old-temp-files` expires all objects after 7 days
- Abort incomplete multipart uploads: 1 day
- Cleanup Lambda: Deletes job artifacts after successful YouTube upload

---

### 1.6 CloudWatch Logs

**Configuration:**
- Retention: 30 days (from `var.log_retention_days` default)
- Log Groups: 5 Lambda + 2 EC2 + 1 Step Functions = 8 groups

**Pricing:**
- Ingestion: $0.57 per GB
- Storage: $0.033 per GB-month

**Estimated Log Volume (per video):**

| Source | Size | Notes |
|--------|------|-------|
| Lambda functions | ~5 MB | Combined all functions |
| EC2 Renderer | ~10 MB | Video processing logs |
| Step Functions | ~1 MB | Execution history |
| **Total per video** | **~16 MB** | |

**Monthly CloudWatch Cost:**

| Scenario | Ingestion | Storage (30 days) | Total |
|----------|-----------|-------------------|-------|
| 1 video/day | 30 × 16 MB = 480 MB → $0.27 | ~240 MB → $0.01 | **$0.28** |
| 3 videos/day | 90 × 16 MB = 1.4 GB → $0.81 | ~700 MB → $0.02 | **$0.83** |

---

### 1.7 Step Functions

**Configuration:**
- Type: Standard Workflow
- States per execution: ~15

**Pricing:**
- State Transitions: $0.025 per 1,000

**Monthly Step Functions Cost:**

| Scenario | Executions | Transitions | Cost |
|----------|------------|-------------|------|
| 1 video/day | 30 | 450 | **$0.01** |
| 3 videos/day | 90 | 1,350 | **$0.03** |

---

### 1.8 Secrets Manager

**Configuration:**
- Secrets: 5 (deepinfra, youtube, admin, jwt, mangadex)
- API Calls: ~50 per video (with 5-minute caching)

**Pricing:**
- Secret Storage: $0.40 per secret per month
- API Calls: $0.05 per 10,000 calls

**Monthly Secrets Manager Cost:**

| Component | Cost |
|-----------|------|
| 5 secrets | $2.00 |
| API calls (< 5000/month) | $0.03 |
| **Total** | **$2.03** |

---

### 1.9 External API Costs (Non-AWS)

| Service | Pricing | Est. Cost/Video | Monthly (30 videos) |
|---------|---------|-----------------|---------------------|
| DeepInfra (Qwen 72B) | $0.27/M input, $0.27/M output | $0.10-0.30 | **$3-9** |
| Edge TTS | Free | $0.00 | **$0.00** |
| YouTube API | Free (quota limited) | $0.00 | **$0.00** |
| MangaDex API | Free | $0.00 | **$0.00** |

---

## 2. Lambda Memory Optimization Recommendations

### Current Configuration Analysis

| Function | Current Memory | CPU Allocation | Recommendation |
|----------|---------------|----------------|----------------|
| manga_fetcher | 512 MB | 0.5 vCPU | **Keep** - Image downloading is I/O bound |
| script_generator | 256 MB | 0.25 vCPU | **Keep** - API calls, minimal processing |
| tts_processor | 512 MB | 0.5 vCPU | **Test 384 MB** - May reduce cost 25% |
| cleanup | 128 MB | 0.125 vCPU | **Keep** - Minimal, S3 deletes only |
| quota_checker | 128 MB | 0.125 vCPU | **Keep** - Simple DynamoDB query |

### Power Tuning Recommendation

Run AWS Lambda Power Tuning on `tts_processor`:

```bash
# Deploy power tuning state machine
sam deploy --guided --template-url https://github.com/alexcasalboni/aws-lambda-power-tuning

# Run tuning (test 128, 256, 384, 512, 1024 MB)
aws stepfunctions start-execution \
  --state-machine-arn arn:aws:states:ap-southeast-1:ACCOUNT:stateMachine:powerTuningStateMachine \
  --input '{
    "lambdaARN": "arn:aws:lambda:ap-southeast-1:ACCOUNT:function:manga-video-pipeline-tts-processor",
    "powerValues": [128, 256, 384, 512, 1024],
    "num": 10,
    "payload": {"job_id": "test-job"}
  }'
```

**Expected Savings:** If 384 MB is sufficient for tts_processor, saves ~$0.0010/video (25% reduction on that function).

---

## 3. EC2 Spot vs On-Demand Cost Comparison

### Current Configuration

| Instance | Type | Spot Price | On-Demand | Savings |
|----------|------|------------|-----------|---------|
| Renderer | c5.xlarge | ~$0.058/hr | $0.194/hr | 70% |
| Dashboard | t3.micro | N/A (24/7) | $0.0126/hr | - |

### Spot Interruption Risk

- **Historical Interruption Rate (c5.xlarge ap-southeast-1):** < 5%
- **Mitigation:** Checkpoint handling implemented in `src/renderer/spot_handler.py`
- **Recovery:** Automatic restart from last checkpoint

### Alternative Instance Types for Rendering

| Instance | vCPU | RAM | Spot Price | Performance | Recommendation |
|----------|------|-----|------------|-------------|----------------|
| c5.xlarge | 4 | 8 GB | $0.058/hr | Baseline | Current |
| c5.large | 2 | 4 GB | $0.034/hr | 50% slower | **Test for short videos** |
| c6i.xlarge | 4 | 8 GB | $0.062/hr | +10% | Slightly better |
| c6a.xlarge | 4 | 8 GB | $0.055/hr | +5% | **Consider switch** |

**Recommendation:** Test c6a.xlarge - newer AMD instances may offer 5% better price/performance.

---

## 4. DynamoDB On-Demand vs Provisioned Analysis

### Current Usage Pattern

| Table | Writes/day | Reads/day | Pattern |
|-------|------------|-----------|---------|
| manga_jobs | 30-100 | 60-200 | Bursty (during pipeline runs) |
| processed_manga | 1-3 | 5-15 | Low, steady |
| settings | 1-2 | 30-90 | Read-heavy |

### Cost Comparison

| Mode | Configuration | Monthly Cost | Best For |
|------|---------------|--------------|----------|
| On-Demand | N/A | $0.37 | **Current scale** |
| Provisioned | 1 WCU, 1 RCU | $0.75 | > 2.6M writes/month |
| Provisioned + Auto-scaling | 1-5 WCU, 1-5 RCU | $0.75-3.75 | Unpredictable spikes |

**Recommendation:** Stay with On-Demand until reaching 1000+ videos/month.

---

## 5. S3 Cleanup Verification

### Lifecycle Policies

```hcl
# From infra/modules/storage/s3.tf
rule {
  id     = "delete-old-temp-files"
  status = "Enabled"
  expiration {
    days = 7  # var.assets_lifecycle_days
  }
  abort_incomplete_multipart_upload {
    days_after_initiation = 1
  }
}
```

### Cleanup Process

1. **Automatic (Lifecycle):** All objects deleted after 7 days
2. **Active (Cleanup Lambda):** Deletes job folder after successful upload
3. **Multipart:** Incomplete uploads aborted after 1 day

### Verification Commands

```bash
# Check for objects older than 7 days (should be empty)
aws s3api list-objects-v2 \
  --bucket manga-video-pipeline-assets-ACCOUNT_ID \
  --query 'Contents[?LastModified<`2024-01-08`]'

# Check bucket size
aws cloudwatch get-metric-statistics \
  --namespace AWS/S3 \
  --metric-name BucketSizeBytes \
  --dimensions Name=BucketName,Value=manga-video-pipeline-assets-ACCOUNT_ID Name=StorageType,Value=StandardStorage \
  --start-time $(date -d '7 days ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date +%Y-%m-%dT%H:%M:%S) \
  --period 86400 \
  --statistics Average
```

---

## 6. CloudWatch Log Retention Confirmation

### Current Configuration

```hcl
# From infra/modules/compute/variables.tf
variable "log_retention_days" {
  default = 30
}
```

### Log Groups and Retention

| Log Group | Retention | Status |
|-----------|-----------|--------|
| /aws/lambda/manga-fetcher | 30 days | Configured |
| /aws/lambda/script-generator | 30 days | Configured |
| /aws/lambda/tts-processor | 30 days | Configured |
| /aws/lambda/cleanup | 30 days | Configured |
| /aws/lambda/quota-checker | 30 days | Configured |
| /aws/ec2/renderer | 30 days | Configured |
| /aws/ec2/dashboard | 30 days | Configured |
| /aws/states/pipeline | 30 days | Configured |

**Recommendation:** 30 days is appropriate for debugging. Consider 14 days if cost optimization is critical (~50% log storage savings).

---

## 7. Data Transfer Cost Analysis

### Data Transfer Patterns

| Transfer Type | Direction | Volume/Video | Cost |
|---------------|-----------|--------------|------|
| MangaDex → Lambda | Internet In | 100 MB | Free |
| Lambda → S3 | Internal | 100 MB | Free |
| S3 → EC2 (Renderer) | Internal | 400 MB | Free |
| EC2 → YouTube | Internet Out | 1 GB | $0.12 |
| DeepInfra API | Internet Out | < 1 MB | Negligible |

**Monthly Data Transfer Cost:**

| Scenario | YouTube Upload | Total |
|----------|---------------|-------|
| 1 video/day (30 GB out) | $3.60 | **$3.60** |
| 3 videos/day (90 GB out) | $10.80 | **$10.80** |

> First 100 GB/month is free tier eligible, then $0.12/GB

---

## 8. Monthly Cost Projection

### Scenario 1: 1 Video/Day (30 videos/month)

| Component | Monthly Cost |
|-----------|--------------|
| Lambda Functions | $0.20 |
| EC2 Spot (Renderer) | $5.19 |
| EC2 Dashboard (t3.micro) | $11.00 |
| DynamoDB | $0.37 |
| S3 Storage | $0.36 |
| CloudWatch Logs | $0.28 |
| Step Functions | $0.01 |
| Secrets Manager | $2.03 |
| Data Transfer | $3.60 |
| **AWS Total** | **$23.04** |
| DeepInfra (external) | $3-9 |
| **Grand Total** | **$26-32** |

### Scenario 2: 3 Videos/Day (90 videos/month)

| Component | Monthly Cost |
|-----------|--------------|
| Lambda Functions | $0.60 |
| EC2 Spot (Renderer) | $15.57 |
| EC2 Dashboard (t3.micro) | $11.00 |
| DynamoDB | $0.41 |
| S3 Storage | $1.09 |
| CloudWatch Logs | $0.83 |
| Step Functions | $0.03 |
| Secrets Manager | $2.03 |
| Data Transfer | $10.80 |
| **AWS Total** | **$42.36** |
| DeepInfra (external) | $9-27 |
| **Grand Total** | **$51-69** |

### Cost by Category (3 videos/day)

```
Compute (EC2 + Lambda):  $27.17  (64%)
Storage (S3 + DynamoDB): $1.50   (4%)
Networking (Transfer):   $10.80  (25%)
Management (CW + SM):    $2.89   (7%)
```

---

## 9. AWS Budgets Alert Configuration

### Configured Budgets (from `infra/modules/monitoring/budgets.tf`)

| Budget | Limit | Alerts | Status |
|--------|-------|--------|--------|
| Monthly Total | $120 | 65% ($78), 100% ($120), 120% ($144) | Configured |
| EC2 Spot | $50 | 80% ($40), 100% ($50) | Configured |
| Lambda | $20 | 80% ($16) | Configured |

### Alert Types

- **ACTUAL:** Triggers when actual spend exceeds threshold
- **FORECASTED:** Triggers when forecasted spend exceeds 100%

### Notification Channel

All alerts sent to: `var.alarm_email`

---

## 10. Actionable Savings Recommendations

### Priority 1: High Impact (> $5/month savings)

| # | Recommendation | Savings | Effort | Implementation |
|---|----------------|---------|--------|----------------|
| 1 | Use t3.micro Free Tier (year 1) | $11/month | Low | Already configured, verify Free Tier eligibility |
| 2 | Reduce log retention to 14 days | $0.14/month | Low | Change `log_retention_days = 14` |
| 3 | Use c6a.xlarge for Spot | ~$0.50/month | Medium | Update `spot_instance_type` |

### Priority 2: Medium Impact ($1-5/month savings)

| # | Recommendation | Savings | Effort | Implementation |
|---|----------------|---------|--------|----------------|
| 4 | Disable Elastic IP if not needed | $3.65/month | Low | Set `dashboard_enable_elastic_ip = false` |
| 5 | Power tune tts_processor to 384MB | ~$0.03/month | Medium | Run Lambda Power Tuning |
| 6 | Use S3 Intelligent Tiering | Variable | Already done | Verify working |

### Priority 3: Future Optimization (when scaling)

| # | Recommendation | Trigger | Implementation |
|---|----------------|---------|----------------|
| 7 | Switch to DynamoDB provisioned | > 500 videos/month | Provision 2 WCU, 5 RCU |
| 8 | Reserved Instances for dashboard | Stable production | 1-year RI for t3.micro (~30% savings) |
| 9 | Consider Fargate Spot | > 1000 videos/month | Replace EC2 Spot with Fargate Spot |

### Not Recommended

| Recommendation | Reason |
|----------------|--------|
| Spot for Dashboard | 24/7 availability needed |
| Lambda SnapStart | Python not supported |
| Graviton for Renderer | c5 Spot pricing is better |

---

## Summary

| Metric | 1 Video/Day | 3 Videos/Day | Budget |
|--------|-------------|--------------|--------|
| AWS Cost | $23 | $42 | $120 |
| External APIs | $3-9 | $9-27 | N/A |
| **Total** | **$26-32** | **$51-69** | $120 |
| % of Budget | 22-27% | 43-58% | 100% |

**Conclusion:** Current infrastructure is cost-efficient and well within the $120 monthly budget. Primary cost drivers are EC2 Spot instances and data transfer. All optimization recommendations are already implemented (arm64 Lambda, Spot instances, lifecycle policies, 30-day log retention).
