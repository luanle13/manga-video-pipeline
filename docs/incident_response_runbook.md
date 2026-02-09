# Incident Response Runbook

This runbook provides step-by-step procedures for responding to security incidents affecting the Manga Video Pipeline.

**Last Updated:** 2024-01-15
**Owner:** Security Team
**Review Frequency:** Quarterly

---

## Table of Contents

1. [Scenario 1: YouTube OAuth Token Compromised](#scenario-1-youtube-oauth-token-compromised)
2. [Scenario 2: DeepInfra API Key Leaked](#scenario-2-deepinfra-api-key-leaked)
3. [Scenario 3: AWS Credentials Compromised](#scenario-3-aws-credentials-compromised)
4. [Scenario 4: Dashboard Breach](#scenario-4-dashboard-breach)
5. [Scenario 5: EC2 Spot Instance Compromised](#scenario-5-ec2-spot-instance-compromised)
6. [General Incident Response](#general-incident-response)
7. [Contact Information](#contact-information)

---

## Scenario 1: YouTube OAuth Token Compromised

### Indicators of Compromise
- Unauthorized video uploads to channel
- Unexpected quota usage alerts
- YouTube API errors indicating token revocation
- Reports of unauthorized channel modifications

### Severity: HIGH

### Immediate Actions (0-15 minutes)

#### 1.1 Revoke Compromised Tokens

**Google Cloud Console:**
1. Go to https://console.cloud.google.com/apis/credentials
2. Select the OAuth 2.0 Client ID used by the pipeline
3. Click "Reset Secret" to invalidate all existing tokens

**Or via gcloud CLI:**
```bash
gcloud auth revoke --all
```

#### 1.2 Disable Pipeline Uploads

```bash
# Stop any running Step Functions executions
aws stepfunctions list-executions \
  --state-machine-arn arn:aws:states:ap-southeast-1:ACCOUNT_ID:stateMachine:manga-video-pipeline-pipeline \
  --status-filter RUNNING \
  --query 'executions[].executionArn' \
  --output text | xargs -I {} aws stepfunctions stop-execution --execution-arn {}

# Terminate any running EC2 renderer instances
aws ec2 describe-instances \
  --filters "Name=tag:ManagedBy,Values=manga-pipeline" "Name=instance-state-name,Values=running" \
  --query 'Reservations[].Instances[].InstanceId' \
  --output text | xargs -I {} aws ec2 terminate-instances --instance-ids {}
```

### Investigation (15-60 minutes)

#### 1.3 Audit Token Usage

**Check YouTube API logs:**
1. Go to Google Cloud Console > APIs & Services > YouTube Data API v3
2. Review quota usage and API calls
3. Note any unusual patterns or unauthorized uploads

**Check CloudWatch Logs:**
```bash
# Search for upload activities
aws logs filter-log-events \
  --log-group-name /aws/ec2/renderer \
  --filter-pattern "YouTube upload" \
  --start-time $(date -d '7 days ago' +%s000) \
  --query 'events[].message'
```

#### 1.4 Identify Leak Source

Check for:
- [ ] Logs containing tokens (should be redacted)
- [ ] Unauthorized access to Secrets Manager
- [ ] Compromised EC2 instances
- [ ] Third-party integrations with access

### Remediation (1-4 hours)

#### 1.5 Generate New OAuth Tokens

```bash
# Run OAuth flow to get new tokens
python scripts/youtube_oauth_setup.py

# Update Secrets Manager
aws secretsmanager put-secret-value \
  --secret-id manga-pipeline/youtube-oauth \
  --secret-string '{
    "client_id": "NEW_CLIENT_ID",
    "client_secret": "NEW_CLIENT_SECRET",
    "access_token": "NEW_ACCESS_TOKEN",
    "refresh_token": "NEW_REFRESH_TOKEN",
    "token_uri": "https://oauth2.googleapis.com/token",
    "expiry": "2024-12-31T23:59:59Z"
  }'
```

#### 1.6 Clear Caches and Resume

```bash
# Redeploy Lambda functions to clear any cached credentials
aws lambda update-function-configuration \
  --function-name manga-video-pipeline-cleanup \
  --environment "Variables={FORCE_REFRESH=true}"
```

### Post-Incident

- [ ] Document timeline and actions taken
- [ ] Update token rotation schedule
- [ ] Review access controls on Secrets Manager
- [ ] Consider enabling YouTube API key restrictions

---

## Scenario 2: DeepInfra API Key Leaked

### Indicators of Compromise
- Unexpected DeepInfra billing charges
- API rate limit errors
- Alert from DeepInfra about unusual activity
- Key found in public repository or logs

### Severity: MEDIUM

### Immediate Actions (0-15 minutes)

#### 2.1 Rotate API Key

**DeepInfra Dashboard:**
1. Go to https://deepinfra.com/dash/api_keys
2. Generate a new API key
3. Revoke the compromised key

#### 2.2 Update Secrets Manager

```bash
aws secretsmanager put-secret-value \
  --secret-id manga-pipeline/deepinfra-api-key \
  --secret-string '{"api_key": "NEW_API_KEY_HERE"}'
```

#### 2.3 Clear Secret Caches

```bash
# Force Lambda functions to refresh cached secrets
# Update an environment variable to trigger cache clear

for func in manga-video-pipeline-script-generator; do
  aws lambda update-function-configuration \
    --function-name $func \
    --environment "Variables={SECRET_CACHE_BUST=$(date +%s)}"
done
```

### Investigation (15-60 minutes)

#### 2.4 Audit API Usage

**DeepInfra Dashboard:**
1. Review API usage logs
2. Check for unusual request patterns
3. Note IP addresses and request volumes

**CloudWatch Logs:**
```bash
aws logs filter-log-events \
  --log-group-name /aws/lambda/manga-video-pipeline-script-generator \
  --filter-pattern "DeepInfra" \
  --start-time $(date -d '7 days ago' +%s000)
```

#### 2.5 Identify Leak Source

Common sources:
- [ ] Committed to git repository
- [ ] Exposed in error logs
- [ ] Shared in communications
- [ ] Accessed by compromised system

```bash
# Check git history for accidental commits
git log -p --all -S 'DEEPINFRA' -- .

# Check logs don't contain API key
grep -r "api_key" /var/log/
```

### Remediation

#### 2.6 Prevent Future Leaks

- Add pre-commit hook to detect API keys
- Enable git-secrets or trufflehog scanning
- Review logging configuration

### Post-Incident

- [ ] Document incident and root cause
- [ ] Update secret rotation procedures
- [ ] Review DeepInfra billing for unauthorized charges
- [ ] Request billing adjustment if applicable

---

## Scenario 3: AWS Credentials Compromised

### Indicators of Compromise
- Unauthorized AWS resources created
- Unusual CloudTrail events
- AWS billing alerts
- GuardDuty findings
- Access from unusual IP addresses

### Severity: CRITICAL

### Immediate Actions (0-5 minutes)

#### 3.1 Disable Compromised Credentials

**For IAM User:**
```bash
# Identify the compromised user
aws iam list-access-keys --user-name COMPROMISED_USER

# Deactivate all access keys
aws iam update-access-key \
  --user-name COMPROMISED_USER \
  --access-key-id AKIAXXXXXXXXXXXXXXXX \
  --status Inactive

# Alternatively, delete the key
aws iam delete-access-key \
  --user-name COMPROMISED_USER \
  --access-key-id AKIAXXXXXXXXXXXXXXXX
```

**For IAM Role (if instance profile compromised):**
```bash
# Revoke all active sessions for the role
aws iam put-role-policy \
  --role-name COMPROMISED_ROLE \
  --policy-name DenyAllPolicy \
  --policy-document '{
    "Version": "2012-10-17",
    "Statement": [{
      "Effect": "Deny",
      "Action": "*",
      "Resource": "*"
    }]
  }'
```

#### 3.2 Preserve Evidence

```bash
# Export CloudTrail logs before any cleanup
aws s3 sync s3://cloudtrail-bucket/AWSLogs/ACCOUNT_ID/ ./incident-evidence/

# Snapshot any potentially compromised EC2 instances
aws ec2 create-snapshot \
  --volume-id vol-XXXXXXXXX \
  --description "Incident evidence - $(date +%Y%m%d)"
```

### Investigation (5-60 minutes)

#### 3.3 Review CloudTrail

```bash
# Get recent events for the compromised credentials
aws cloudtrail lookup-events \
  --lookup-attributes AttributeKey=Username,AttributeValue=COMPROMISED_USER \
  --start-time $(date -d '7 days ago' +%Y-%m-%dT%H:%M:%SZ) \
  --max-results 50

# Look for resource creation
aws cloudtrail lookup-events \
  --lookup-attributes AttributeKey=EventName,AttributeValue=RunInstances \
  --start-time $(date -d '7 days ago' +%Y-%m-%dT%H:%M:%SZ)
```

#### 3.4 Check for Unauthorized Resources

```bash
# List all EC2 instances
aws ec2 describe-instances --query 'Reservations[].Instances[].[InstanceId,LaunchTime,Tags]'

# List all Lambda functions
aws lambda list-functions --query 'Functions[].[FunctionName,LastModified]'

# List all IAM users and roles created recently
aws iam list-users --query 'Users[?CreateDate>`2024-01-01`]'
aws iam list-roles --query 'Roles[?CreateDate>`2024-01-01`]'

# Check for cryptocurrency mining indicators
aws ec2 describe-instances \
  --filters "Name=instance-type,Values=p3.*,p4d.*,g4dn.*" \
  --query 'Reservations[].Instances[].[InstanceId,InstanceType,LaunchTime]'
```

#### 3.5 Check for Persistence Mechanisms

```bash
# Check for new IAM policies
aws iam list-policies --scope Local --query 'Policies[?CreateDate>`2024-01-01`]'

# Check for Lambda functions with external triggers
aws lambda list-event-source-mappings

# Check for new security groups with open access
aws ec2 describe-security-groups \
  --query 'SecurityGroups[?IpPermissions[?IpRanges[?CidrIp==`0.0.0.0/0`]]]'
```

### Remediation (1-24 hours)

#### 3.6 Remove Unauthorized Resources

```bash
# Terminate unauthorized EC2 instances
aws ec2 terminate-instances --instance-ids i-XXXXXXXXX

# Delete unauthorized IAM resources
aws iam delete-user --user-name UNAUTHORIZED_USER
aws iam delete-role --role-name UNAUTHORIZED_ROLE
```

#### 3.7 Rotate All Credentials

```bash
# Rotate all IAM user access keys
for user in $(aws iam list-users --query 'Users[].UserName' --output text); do
  echo "Rotating keys for $user"
  # Create new key, update applications, delete old key
done

# Rotate all Secrets Manager secrets
aws secretsmanager rotate-secret --secret-id manga-pipeline/youtube-oauth
aws secretsmanager rotate-secret --secret-id manga-pipeline/deepinfra-api-key
aws secretsmanager rotate-secret --secret-id manga-pipeline/admin-credentials
aws secretsmanager rotate-secret --secret-id manga-pipeline/jwt-secret
```

### Post-Incident

- [ ] Complete incident report with timeline
- [ ] Enable MFA on all IAM users
- [ ] Enable GuardDuty if not already active
- [ ] Review and tighten IAM policies
- [ ] Implement AWS Organizations SCPs
- [ ] Consider AWS Access Analyzer findings

---

## Scenario 4: Dashboard Breach

### Indicators of Compromise
- Unauthorized login attempts in logs
- Unexpected configuration changes
- User reports of unauthorized access
- Modified job settings or queue manipulation

### Severity: HIGH

### Immediate Actions (0-15 minutes)

#### 4.1 Disable Dashboard Access

```bash
# Update security group to block all access
aws ec2 revoke-security-group-ingress \
  --group-id sg-XXXXXXXXX \
  --protocol tcp \
  --port 443 \
  --cidr 0.0.0.0/0
```

#### 4.2 Invalidate All Sessions

**Rotate JWT Secret:**
```bash
# Generate new JWT secret
NEW_SECRET=$(openssl rand -base64 32)

# Update Secrets Manager
aws secretsmanager put-secret-value \
  --secret-id manga-pipeline/jwt-secret \
  --secret-string "{\"secret_key\": \"$NEW_SECRET\", \"algorithm\": \"HS256\"}"

# Restart dashboard to pick up new secret
aws ssm send-command \
  --instance-ids i-XXXXXXXXX \
  --document-name "AWS-RunShellScript" \
  --parameters 'commands=["sudo systemctl restart dashboard"]'
```

#### 4.3 Change Admin Password

```bash
# Generate new bcrypt hash
NEW_HASH=$(python3 -c "import bcrypt; print(bcrypt.hashpw(b'NEW_STRONG_PASSWORD', bcrypt.gensalt()).decode())")

# Update Secrets Manager
aws secretsmanager put-secret-value \
  --secret-id manga-pipeline/admin-credentials \
  --secret-string "{\"username\": \"admin\", \"password_hash\": \"$NEW_HASH\"}"
```

### Investigation (15-60 minutes)

#### 4.4 Review Access Logs

```bash
# Check dashboard application logs
aws logs filter-log-events \
  --log-group-name /aws/ec2/dashboard \
  --filter-pattern "login" \
  --start-time $(date -d '7 days ago' +%s000)

# Look for failed login attempts
aws logs filter-log-events \
  --log-group-name /aws/ec2/dashboard \
  --filter-pattern "Login failed" \
  --start-time $(date -d '24 hours ago' +%s000)

# Check for unusual IP addresses
aws logs filter-log-events \
  --log-group-name /aws/ec2/dashboard \
  --filter-pattern "authenticated" \
  --start-time $(date -d '7 days ago' +%s000) \
  | jq '.events[].message' | sort | uniq -c
```

#### 4.5 Audit Configuration Changes

```bash
# Check DynamoDB settings table for modifications
aws dynamodb scan \
  --table-name manga-video-pipeline-settings \
  --projection-expression "setting_key,updated_at,updated_by"

# Review job history for anomalies
aws dynamodb query \
  --table-name manga-video-pipeline-jobs \
  --index-name status-created-index \
  --key-condition-expression "#status = :status" \
  --expression-attribute-names '{"#status": "status"}' \
  --expression-attribute-values '{":status": {"S": "completed"}}' \
  --scan-index-forward false \
  --limit 50
```

### Remediation

#### 4.6 Restore Legitimate Access

```bash
# Re-enable access from admin IP only
aws ec2 authorize-security-group-ingress \
  --group-id sg-XXXXXXXXX \
  --protocol tcp \
  --port 443 \
  --cidr YOUR_IP/32
```

#### 4.7 Implement Additional Controls

- Enable rate limiting on login endpoint
- Add IP allowlisting at application level
- Consider adding 2FA for admin access

### Post-Incident

- [ ] Document attacker activities
- [ ] Restore any modified configurations
- [ ] Review and strengthen password policy
- [ ] Implement failed login alerting
- [ ] Consider VPN-only access for dashboard

---

## Scenario 5: EC2 Spot Instance Compromised

### Indicators of Compromise
- Unusual outbound network traffic
- Unexpected processes running
- Instance metadata access from unusual paths
- GuardDuty findings for the instance

### Severity: HIGH

### Immediate Actions (0-10 minutes)

#### 5.1 Terminate Compromised Instance

```bash
# Get instance ID
INSTANCE_ID=$(aws ec2 describe-instances \
  --filters "Name=tag:ManagedBy,Values=manga-pipeline" "Name=instance-state-name,Values=running" \
  --query 'Reservations[0].Instances[0].InstanceId' \
  --output text)

# Terminate immediately
aws ec2 terminate-instances --instance-ids $INSTANCE_ID
```

#### 5.2 Preserve Evidence (if time permits)

```bash
# Create AMI for forensics before terminating
aws ec2 create-image \
  --instance-id $INSTANCE_ID \
  --name "Incident-$(date +%Y%m%d-%H%M)-$INSTANCE_ID" \
  --description "Forensic image - potential compromise"

# Get console output
aws ec2 get-console-output --instance-id $INSTANCE_ID > console-output.txt
```

### Investigation (10-60 minutes)

#### 5.3 Review Security Group

```bash
# Check if security group was modified
aws ec2 describe-security-groups \
  --group-names manga-video-pipeline-renderer-sg \
  --query 'SecurityGroups[0].IpPermissions'

# Check security group rule changes in CloudTrail
aws cloudtrail lookup-events \
  --lookup-attributes AttributeKey=EventName,AttributeValue=AuthorizeSecurityGroupIngress \
  --start-time $(date -d '7 days ago' +%Y-%m-%dT%H:%M:%SZ)
```

#### 5.4 Check for Lateral Movement

```bash
# Check if instance accessed other AWS resources
aws cloudtrail lookup-events \
  --lookup-attributes AttributeKey=ResourceName,AttributeValue=$INSTANCE_ID \
  --start-time $(date -d '24 hours ago' +%Y-%m-%dT%H:%M:%SZ)

# Verify no new IAM credentials were created
aws iam list-access-keys --user-name ec2-renderer

# Check S3 access patterns
aws s3api list-objects-v2 \
  --bucket manga-video-pipeline-assets \
  --prefix jobs/ \
  --query 'Contents[?LastModified>`2024-01-14`]'
```

#### 5.5 Analyze VPC Flow Logs

```bash
# Check for unusual destinations
aws logs filter-log-events \
  --log-group-name /vpc/flow-logs \
  --filter-pattern "[version, account, eni, source, dest, srcport, destport, proto, packets, bytes, start, end, action, status]" \
  --start-time $(date -d '24 hours ago' +%s000)
```

### Remediation

#### 5.6 Rotate Instance Profile Credentials

```bash
# Update instance profile to revoke sessions
aws iam put-role-policy \
  --role-name manga-video-pipeline-ec2-renderer \
  --policy-name TemporaryDeny \
  --policy-document '{
    "Version": "2012-10-17",
    "Statement": [{
      "Sid": "DenyUntilRemediated",
      "Effect": "Deny",
      "Action": "*",
      "Resource": "*",
      "Condition": {
        "DateLessThan": {"aws:TokenIssueTime": "'$(date -u +%Y-%m-%dT%H:%M:%SZ)'"}
      }
    }]
  }'

# After new instances launch, remove the deny policy
aws iam delete-role-policy \
  --role-name manga-video-pipeline-ec2-renderer \
  --policy-name TemporaryDeny
```

#### 5.7 Harden Security Group

```bash
# Verify no inbound rules exist
aws ec2 describe-security-groups \
  --group-names manga-video-pipeline-renderer-sg \
  --query 'SecurityGroups[0].IpPermissions'

# If any found, remove them
aws ec2 revoke-security-group-ingress \
  --group-id sg-XXXXXXXXX \
  --protocol -1 \
  --cidr 0.0.0.0/0
```

### Post-Incident

- [ ] Update AMI with latest security patches
- [ ] Enable IMDSv2 requirement on launch template
- [ ] Consider Systems Manager Session Manager instead of SSH
- [ ] Implement instance metadata service restrictions
- [ ] Enable GuardDuty runtime monitoring

---

## General Incident Response

### Incident Classification

| Severity | Response Time | Examples |
|----------|---------------|----------|
| CRITICAL | 15 minutes | AWS credentials compromised, data breach |
| HIGH | 1 hour | OAuth token leak, dashboard breach |
| MEDIUM | 4 hours | API key leaked, single instance compromise |
| LOW | 24 hours | Failed login attempts, configuration drift |

### Communication Template

```
Subject: [SEVERITY] Security Incident - Manga Video Pipeline

Incident ID: INC-YYYY-MM-DD-XXX
Severity: [CRITICAL/HIGH/MEDIUM/LOW]
Status: [Investigating/Contained/Remediated/Closed]
Discovered: YYYY-MM-DD HH:MM UTC
Reported By: [Name]

Summary:
[Brief description of the incident]

Impact:
[What systems/data were affected]

Current Actions:
1. [Action taken]
2. [Action in progress]

Next Steps:
1. [Planned action]

Timeline:
- HH:MM - Event occurred
- HH:MM - Incident detected
- HH:MM - Response initiated
```

### Evidence Collection Checklist

- [ ] CloudTrail logs exported
- [ ] CloudWatch logs exported
- [ ] EC2 instance snapshots created
- [ ] Security group configurations documented
- [ ] IAM policy changes captured
- [ ] Timeline documented
- [ ] Affected resources inventoried

---

## Contact Information

### Internal

| Role | Contact | Escalation Time |
|------|---------|-----------------|
| On-Call Engineer | [pager] | Immediate |
| Security Lead | [email] | 15 minutes |
| Engineering Manager | [email] | 30 minutes |
| CTO | [email] | 1 hour (CRITICAL only) |

### External

| Service | Contact | Purpose |
|---------|---------|---------|
| AWS Support | Premium support case | AWS account issues |
| Google Cloud | support.google.com | YouTube API issues |
| DeepInfra | support@deepinfra.com | API key issues |

### Useful Links

- AWS Security Hub: https://console.aws.amazon.com/securityhub/
- CloudTrail: https://console.aws.amazon.com/cloudtrail/
- GuardDuty: https://console.aws.amazon.com/guardduty/
- Google Security: https://myaccount.google.com/security
