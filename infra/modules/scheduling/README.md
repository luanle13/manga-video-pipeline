# EventBridge Scheduling Module

Terraform module for scheduling the manga video pipeline using AWS EventBridge.

## Features

- 🕐 **Timezone-aware scheduling**: Triggers at midnight Vietnam time (UTC+7)
- 🔒 **Least privilege IAM**: EventBridge role can only start the specific state machine
- 🔄 **Retry policy**: Automatically retries failed triggers
- 🏷️ **Tagging support**: Consistent resource tagging
- ⚙️ **Configurable**: Override schedule, enable/disable, custom tags

## Architecture

```
┌─────────────────┐
│  EventBridge    │
│  Rule           │  Triggers daily at 00:00 UTC+7
│  (cron)         │  (17:00 UTC previous day)
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  IAM Role       │  Least privilege:
│  (EventBridge)  │  - states:StartExecution
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Step Functions  │  manga-pipeline
│ State Machine   │  execution starts
└─────────────────┘
```

## Usage

### Basic Usage

```hcl
module "pipeline_scheduling" {
  source = "./infra/modules/scheduling"

  state_machine_arn = aws_sfn_state_machine.manga_pipeline.arn
  environment       = "prod"
}
```

### Custom Schedule

```hcl
module "pipeline_scheduling" {
  source = "./infra/modules/scheduling"

  state_machine_arn = aws_sfn_state_machine.manga_pipeline.arn
  environment       = "dev"

  # Run every 6 hours instead of daily
  schedule_expression = "rate(6 hours)"
}
```

### Disabled by Default (Manual Trigger Only)

```hcl
module "pipeline_scheduling" {
  source = "./infra/modules/scheduling"

  state_machine_arn = aws_sfn_state_machine.manga_pipeline.arn
  environment       = "staging"

  # Disable automatic triggering
  enabled = false
}
```

### With Custom Tags

```hcl
module "pipeline_scheduling" {
  source = "./infra/modules/scheduling"

  state_machine_arn = aws_sfn_state_machine.manga_pipeline.arn
  environment       = "prod"

  tags = {
    Team        = "Content"
    CostCenter  = "Marketing"
    Compliance  = "PII-Safe"
  }
}
```

## Inputs

| Name | Description | Type | Default | Required |
|------|-------------|------|---------|:--------:|
| state_machine_arn | ARN of the Step Functions state machine to trigger | `string` | n/a | yes |
| environment | Environment name (dev, staging, prod) | `string` | `"prod"` | no |
| enabled | Whether the EventBridge rule is enabled | `bool` | `true` | no |
| schedule_expression | Cron expression for the EventBridge rule | `string` | `"cron(0 17 * * ? *)"` | no |
| tags | Additional tags to apply to all resources | `map(string)` | `{}` | no |

## Outputs

| Name | Description |
|------|-------------|
| eventbridge_rule_name | Name of the EventBridge rule |
| eventbridge_rule_arn | ARN of the EventBridge rule |
| eventbridge_rule_id | ID of the EventBridge rule |
| eventbridge_role_name | Name of the IAM role used by EventBridge |
| eventbridge_role_arn | ARN of the IAM role used by EventBridge |
| schedule_expression | Cron expression for the EventBridge rule |
| schedule_description | Human-readable schedule description |
| enabled | Whether the EventBridge rule is enabled |
| target_state_machine_arn | ARN of the Step Functions state machine being triggered |

## Schedule Expression

### Default Schedule

The default cron expression is `cron(0 17 * * ? *)`, which triggers:
- **Vietnam time**: 00:00 (midnight)
- **UTC time**: 17:00 (5 PM previous day)

### Cron Format

EventBridge uses 6-field cron expressions:

```
cron(Minutes Hours Day-of-month Month Day-of-week Year)
```

Examples:
```hcl
# Daily at midnight Vietnam time
schedule_expression = "cron(0 17 * * ? *)"

# Every weekday at 8 AM Vietnam time (1 AM UTC)
schedule_expression = "cron(0 1 ? * MON-FRI *)"

# First day of every month at midnight Vietnam time
schedule_expression = "cron(0 17 1 * ? *)"

# Every 12 hours
schedule_expression = "rate(12 hours)"

# Every 30 minutes
schedule_expression = "rate(30 minutes)"
```

### Timezone Calculation

Vietnam is UTC+7, so:
```
Vietnam 00:00 = UTC 17:00 (previous day)
Vietnam 01:00 = UTC 18:00 (previous day)
Vietnam 12:00 = UTC 05:00 (same day)
```

**Important**: EventBridge cron expressions use UTC. Always convert from Vietnam time to UTC when setting schedules.

## IAM Permissions

### EventBridge Role

The module creates an IAM role with **least privilege** permissions:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": "states:StartExecution",
      "Resource": "arn:aws:states:region:account:stateMachine:manga-pipeline"
    }
  ]
}
```

**Security Features**:
- ✅ Only `states:StartExecution` (not DescribeExecution, StopExecution, etc.)
- ✅ Restricted to specific state machine ARN
- ✅ Source account validation in assume role policy

### Trust Policy

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "events.amazonaws.com"
      },
      "Action": "sts:AssumeRole",
      "Condition": {
        "StringEquals": {
          "aws:SourceAccount": "123456789012"
        }
      }
    }
  ]
}
```

## Deployment

### 1. Plan

```bash
terraform plan \
  -var="state_machine_arn=arn:aws:states:us-east-1:123456789012:stateMachine:manga-pipeline"
```

### 2. Apply

```bash
terraform apply \
  -var="state_machine_arn=arn:aws:states:us-east-1:123456789012:stateMachine:manga-pipeline"
```

### 3. Verify

```bash
# Check rule exists
aws events describe-rule \
  --name manga-pipeline-daily-trigger-prod

# List targets
aws events list-targets-by-rule \
  --rule manga-pipeline-daily-trigger-prod

# Manually trigger (for testing)
aws stepfunctions start-execution \
  --state-machine-arn arn:aws:states:region:account:stateMachine:manga-pipeline \
  --input '{}'
```

## Monitoring

### CloudWatch Metrics

Monitor these metrics in CloudWatch:

- `Invocations` - Number of times rule triggered
- `TriggeredRules` - Rules that matched events
- `FailedInvocations` - Failed triggers
- `ThrottledRules` - Rate-limited triggers

### CloudWatch Alarms

Recommended alarms:

```hcl
resource "aws_cloudwatch_metric_alarm" "eventbridge_failed_invocations" {
  alarm_name          = "manga-pipeline-eventbridge-failures"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "1"
  metric_name         = "FailedInvocations"
  namespace           = "AWS/Events"
  period              = "300"
  statistic           = "Sum"
  threshold           = "0"
  alarm_description   = "Alert when EventBridge fails to trigger pipeline"

  dimensions = {
    RuleName = module.pipeline_scheduling.eventbridge_rule_name
  }
}
```

### Step Functions Integration

After EventBridge triggers, monitor Step Functions:

```bash
# List recent executions
aws stepfunctions list-executions \
  --state-machine-arn arn:aws:states:region:account:stateMachine:manga-pipeline \
  --max-results 10

# Get execution details
aws stepfunctions describe-execution \
  --execution-arn <execution-arn>

# Get execution history
aws stepfunctions get-execution-history \
  --execution-arn <execution-arn>
```

## Troubleshooting

### Rule Not Triggering

1. **Check rule is enabled**:
   ```bash
   aws events describe-rule --name manga-pipeline-daily-trigger-prod
   # State should be "ENABLED"
   ```

2. **Verify schedule expression**:
   ```bash
   # Test cron expression at: https://cronexpressiondescriptor.azurewebsites.net/
   ```

3. **Check IAM permissions**:
   ```bash
   aws iam get-role-policy \
     --role-name EventBridgeStepFunctionsRole-prod \
     --policy-name StartStepFunctionsExecution
   ```

### Failed Invocations

1. **Check CloudWatch Logs**:
   - EventBridge logs: `/aws/events/rules/manga-pipeline-daily-trigger`
   - Step Functions logs: `/aws/states/manga-pipeline`

2. **Verify target configuration**:
   ```bash
   aws events list-targets-by-rule \
     --rule manga-pipeline-daily-trigger-prod
   ```

3. **Test manual trigger**:
   ```bash
   aws stepfunctions start-execution \
     --state-machine-arn <arn> \
     --input '{}'
   ```

### Wrong Timezone

If pipeline triggers at wrong time:

1. **Verify current UTC offset**:
   ```bash
   date -u  # UTC time
   TZ=Asia/Ho_Chi_Minh date  # Vietnam time
   ```

2. **Recalculate cron expression**:
   ```
   Desired Vietnam time: 00:00
   UTC offset: +7 hours
   UTC time: 00:00 - 7 = 17:00 (previous day)
   Cron: cron(0 17 * * ? *)
   ```

3. **Update schedule**:
   ```bash
   terraform apply -var="schedule_expression=cron(0 17 * * ? *)"
   ```

## Cost

### EventBridge Pricing (us-east-1)

- **Event delivery**: First 1 million events free, then $1.00 per million
- **Daily trigger**: 1 event/day × 30 days = 30 events/month
- **Monthly cost**: FREE (under 1 million free tier)

### Step Functions Pricing

The module only triggers Step Functions. See Step Functions costs:
- State transitions: $0.025 per 1,000 transitions
- Typical pipeline: ~200 transitions = $0.005 per execution

## Examples

### Development Environment

```hcl
# dev.tfvars
environment         = "dev"
enabled             = false  # Manual trigger only
schedule_expression = "rate(1 hour)"  # More frequent for testing

tags = {
  Environment = "development"
  AutoShutdown = "true"
}
```

### Production Environment

```hcl
# prod.tfvars
environment         = "prod"
enabled             = true
schedule_expression = "cron(0 17 * * ? *)"  # Midnight Vietnam

tags = {
  Environment  = "production"
  CriticalPath = "true"
  OnCall       = "content-team"
}
```

### Multi-Region Deployment

```hcl
# Deploy in multiple regions for redundancy
module "pipeline_scheduling_primary" {
  source = "./infra/modules/scheduling"

  providers = {
    aws = aws.us-east-1
  }

  state_machine_arn = aws_sfn_state_machine.manga_pipeline_us_east_1.arn
  environment       = "prod"
}

module "pipeline_scheduling_failover" {
  source = "./infra/modules/scheduling"

  providers = {
    aws = aws.ap-southeast-1
  }

  state_machine_arn = aws_sfn_state_machine.manga_pipeline_ap_southeast_1.arn
  environment       = "prod"

  # Offset by 5 minutes to avoid conflicts
  schedule_expression = "cron(5 17 * * ? *)"
}
```

## Requirements

| Name | Version |
|------|---------|
| terraform | >= 1.0 |
| aws | ~> 5.0 |

## Resources Created

This module creates the following resources:

- `aws_cloudwatch_event_rule.daily_pipeline_trigger`
- `aws_cloudwatch_event_target.step_functions`
- `aws_iam_role.eventbridge_sfn`
- `aws_iam_role_policy.eventbridge_sfn_execution`

## License

See project LICENSE file.
