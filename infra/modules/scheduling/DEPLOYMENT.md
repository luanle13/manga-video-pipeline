# EventBridge Scheduling Module - Deployment Guide

This guide provides step-by-step instructions for deploying the EventBridge scheduling module.

## Prerequisites

- ✅ Terraform >= 1.0 installed
- ✅ AWS CLI configured with appropriate credentials
- ✅ Step Functions state machine deployed (manga-pipeline)
- ✅ IAM permissions to create EventBridge rules and IAM roles

## Quick Start

### 1. Validate Module

```bash
cd infra/modules/scheduling
./validate.sh
```

Expected output:
```
✅ All checks passed!
```

### 2. Create Variables File

Create `terraform.tfvars`:

```hcl
state_machine_arn = "arn:aws:states:us-east-1:123456789012:stateMachine:manga-pipeline"
environment       = "prod"
enabled           = true
```

### 3. Initialize Terraform

```bash
terraform init
```

### 4. Plan Deployment

```bash
terraform plan -out=tfplan
```

Review the plan carefully. You should see:
- 1 EventBridge rule to create
- 1 EventBridge target to create
- 1 IAM role to create
- 1 IAM role policy to create

### 5. Apply Changes

```bash
terraform apply tfplan
```

### 6. Verify Deployment

```bash
# Check EventBridge rule
aws events describe-rule --name manga-pipeline-daily-trigger-prod

# List targets
aws events list-targets-by-rule --rule manga-pipeline-daily-trigger-prod

# Check IAM role
aws iam get-role --role-name EventBridgeStepFunctionsRole-prod
```

## Configuration Options

### Default Schedule (Midnight Vietnam Time)

```hcl
module "scheduling" {
  source = "./infra/modules/scheduling"

  state_machine_arn = aws_sfn_state_machine.manga_pipeline.arn
  environment       = "prod"
  # Uses default: cron(0 17 * * ? *)
}
```

### Custom Schedule

```hcl
module "scheduling" {
  source = "./infra/modules/scheduling"

  state_machine_arn   = aws_sfn_state_machine.manga_pipeline.arn
  environment         = "prod"
  schedule_expression = "cron(0 12 * * ? *)"  # Noon UTC
}
```

### Disabled (Manual Trigger Only)

```hcl
module "scheduling" {
  source = "./infra/modules/scheduling"

  state_machine_arn = aws_sfn_state_machine.manga_pipeline.arn
  environment       = "staging"
  enabled           = false  # Disabled for testing
}
```

## Timezone Reference

Vietnam is UTC+7. Convert desired Vietnam time to UTC:

| Vietnam Time | UTC Time | Cron Expression |
|--------------|----------|-----------------|
| 00:00 (midnight) | 17:00 (previous day) | `cron(0 17 * * ? *)` |
| 01:00 | 18:00 (previous day) | `cron(0 18 * * ? *)` |
| 06:00 | 23:00 (previous day) | `cron(0 23 * * ? *)` |
| 08:00 | 01:00 (same day) | `cron(0 1 * * ? *)` |
| 12:00 (noon) | 05:00 (same day) | `cron(0 5 * * ? *)` |

## Manual Testing

### Trigger State Machine Manually

```bash
aws stepfunctions start-execution \
  --state-machine-arn arn:aws:states:us-east-1:123456789012:stateMachine:manga-pipeline \
  --input '{}' \
  --name test-execution-$(date +%s)
```

### Check Execution Status

```bash
aws stepfunctions list-executions \
  --state-machine-arn arn:aws:states:us-east-1:123456789012:stateMachine:manga-pipeline \
  --max-results 5
```

### View Execution Details

```bash
aws stepfunctions describe-execution \
  --execution-arn <execution-arn>
```

## Monitoring

### CloudWatch Metrics

Monitor in AWS Console:
- EventBridge: `AWS/Events` namespace
  - Metric: `Invocations` (should be 1/day)
  - Metric: `FailedInvocations` (should be 0)

- Step Functions: `AWS/States` namespace
  - Metric: `ExecutionsStarted` (should increase daily)
  - Metric: `ExecutionsFailed` (monitor for issues)

### CloudWatch Logs

EventBridge doesn't log by default, but Step Functions does:
- Log Group: `/aws/states/manga-pipeline`

### AWS Console URLs

After deployment, get console URLs from outputs:

```bash
terraform output -raw eventbridge_console_url
# Opens EventBridge rule in console

terraform output -raw state_machine_console_url
# Opens Step Functions state machine in console
```

## Troubleshooting

### Rule Not Triggering

**Symptom**: No Step Functions executions at scheduled time

**Check**:
1. Verify rule is enabled:
   ```bash
   aws events describe-rule --name manga-pipeline-daily-trigger-prod
   # State should be "ENABLED"
   ```

2. Check schedule expression:
   ```bash
   terraform output schedule_expression
   # Should be: cron(0 17 * * ? *)
   ```

3. Verify IAM permissions:
   ```bash
   aws iam get-role-policy \
     --role-name EventBridgeStepFunctionsRole-prod \
     --policy-name StartStepFunctionsExecution
   ```

**Fix**:
```bash
# Enable rule
terraform apply -var="enabled=true"

# Or manually
aws events enable-rule --name manga-pipeline-daily-trigger-prod
```

### Failed Invocations

**Symptom**: EventBridge metric `FailedInvocations` > 0

**Check**:
1. Verify state machine ARN:
   ```bash
   aws events list-targets-by-rule --rule manga-pipeline-daily-trigger-prod
   # Compare ARN with actual state machine
   ```

2. Check state machine status:
   ```bash
   aws stepfunctions describe-state-machine \
     --state-machine-arn <arn>
   # Status should be "ACTIVE"
   ```

**Fix**:
```bash
# Update state machine ARN
terraform apply -var="state_machine_arn=<correct-arn>"
```

### IAM Permission Denied

**Symptom**: Step Functions execution fails with "AccessDenied"

**Check**:
```bash
# Verify EventBridge role can assume
aws sts assume-role \
  --role-arn <eventbridge-role-arn> \
  --role-session-name test

# Check policy
aws iam get-role-policy \
  --role-name EventBridgeStepFunctionsRole-prod \
  --policy-name StartStepFunctionsExecution
```

**Fix**:
```bash
# Re-apply Terraform to fix IAM
terraform apply
```

### Wrong Timezone

**Symptom**: Pipeline triggers at wrong time

**Debug**:
```bash
# Check current UTC time
date -u

# Check Vietnam time (should be UTC+7)
TZ=Asia/Ho_Chi_Minh date

# Verify cron expression
terraform output schedule_expression
```

**Fix**:
```bash
# Recalculate: Vietnam 00:00 = UTC 17:00
terraform apply -var='schedule_expression=cron(0 17 * * ? *)'
```

## Rollback

### Disable Rule (Keep Infrastructure)

```bash
terraform apply -var="enabled=false"
```

### Destroy All Resources

```bash
terraform destroy
```

**Warning**: This removes the EventBridge rule and IAM role. The Step Functions state machine is NOT destroyed.

## Cost Estimate

### EventBridge
- Rule creation: Free
- Event delivery: First 1 million events/month free
- Daily trigger: 30 events/month = **FREE**

### IAM
- No charge for IAM roles and policies

### Total Monthly Cost
**$0.00** (assuming <1M EventBridge events)

## Security Checklist

Before deploying to production:

- [ ] State machine ARN is correct
- [ ] IAM role follows least privilege (only `states:StartExecution`)
- [ ] Schedule expression is correct for Vietnam timezone
- [ ] Tags include required compliance/cost tracking tags
- [ ] CloudWatch alarms configured for failed invocations
- [ ] Manual test execution successful

## Environment-Specific Deployments

### Development

```hcl
# dev.tfvars
environment         = "dev"
enabled             = false  # Manual trigger only
schedule_expression = "rate(1 hour)"  # More frequent testing
```

### Staging

```hcl
# staging.tfvars
environment         = "staging"
enabled             = true
schedule_expression = "cron(0 18 * * ? *)"  # Offset by 1 hour
```

### Production

```hcl
# prod.tfvars
environment         = "prod"
enabled             = true
schedule_expression = "cron(0 17 * * ? *)"  # Midnight Vietnam
```

## Outputs Reference

After deployment, useful outputs:

```bash
# EventBridge rule name
terraform output eventbridge_rule_name
# manga-pipeline-daily-trigger-prod

# EventBridge rule ARN
terraform output eventbridge_rule_arn
# arn:aws:events:us-east-1:123456789012:rule/manga-pipeline-daily-trigger-prod

# IAM role ARN
terraform output eventbridge_role_arn
# arn:aws:iam::123456789012:role/EventBridgeStepFunctionsRole-prod

# Schedule expression
terraform output schedule_expression
# cron(0 17 * * ? *)

# Schedule description
terraform output schedule_description
# Daily at midnight Vietnam time (00:00 UTC+7 / 17:00 UTC)
```

## Next Steps

After successful deployment:

1. **Monitor first execution**: Wait for the next scheduled time and verify execution
2. **Set up alarms**: Configure CloudWatch alarms for failures
3. **Document runbook**: Update team runbook with trigger schedule
4. **Test manual trigger**: Verify manual execution works
5. **Review costs**: Check AWS billing after first month

## Support

For issues or questions:
- Review logs: CloudWatch Logs (`/aws/states/manga-pipeline`)
- Check metrics: CloudWatch Metrics (EventBridge, Step Functions)
- Validate config: Run `./validate.sh`
- Terraform docs: https://registry.terraform.io/providers/hashicorp/aws/latest/docs

## Additional Resources

- [AWS EventBridge Documentation](https://docs.aws.amazon.com/eventbridge/)
- [EventBridge Cron Expressions](https://docs.aws.amazon.com/eventbridge/latest/userguide/eb-create-rule-schedule.html)
- [Step Functions Best Practices](https://docs.aws.amazon.com/step-functions/latest/dg/best-practices.html)
- [Terraform AWS Provider](https://registry.terraform.io/providers/hashicorp/aws/latest/docs)
