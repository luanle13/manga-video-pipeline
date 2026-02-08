# Dashboard Deployment Guide

Complete guide for deploying the Manga Video Pipeline Admin Dashboard to AWS EC2.

## Overview

The dashboard is deployed on EC2 t3.micro instances with:
- **Uvicorn** serving the FastAPI application on localhost:8000
- **Caddy** as reverse proxy with auto-HTTPS via Let's Encrypt
- **nip.io** for dynamic DNS (e.g., `52.1.2.3.nip.io`)
- **systemd** services for automatic restart on failure

## Prerequisites

1. **AWS CLI** installed and configured
2. **AWS Account** with appropriate permissions:
   - EC2 (launch instances, describe instances)
   - S3 (create/upload to deployment bucket)
   - SSM (send commands to instances)
   - DynamoDB (access to jobs table)
   - Secrets Manager (read admin credentials and JWT secret)
3. **Git** repository access

## Files

- `deploy_dashboard.sh` - Packages code and deploys to instances
- `dashboard_userdata.sh` - EC2 user-data script for initial setup
- `Caddyfile` - Caddy reverse proxy configuration

## Architecture

```
Internet (HTTPS/443)
    ↓
Caddy (auto-HTTPS with Let's Encrypt)
    ↓ (reverse proxy)
Uvicorn (localhost:8000)
    ↓
FastAPI Dashboard App
    ↓
AWS Services (DynamoDB, S3, Secrets Manager, Step Functions)
```

## Initial Deployment

### Step 1: Create Deployment Bucket

```bash
export AWS_REGION=us-east-1
export DEPLOYMENT_BUCKET=manga-pipeline-deployments

aws s3 mb s3://$DEPLOYMENT_BUCKET --region $AWS_REGION
```

### Step 2: Create Secrets in Secrets Manager

**Admin Credentials:**
```bash
aws secretsmanager create-secret \
    --name manga-pipeline/admin-credentials \
    --secret-string '{"username":"admin","password":"CHANGE_THIS_SECURE_PASSWORD"}' \
    --region $AWS_REGION
```

**JWT Secret:**
```bash
aws secretsmanager create-secret \
    --name manga-pipeline/jwt-secret \
    --secret-string "$(openssl rand -hex 32)" \
    --region $AWS_REGION
```

### Step 3: Create IAM Role for EC2

Create an IAM role with the following permissions:

**Trust Policy:**
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "ec2.amazonaws.com"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
```

**Permissions Policy:**
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:ListBucket"
      ],
      "Resource": [
        "arn:aws:s3:::manga-pipeline-deployments/*",
        "arn:aws:s3:::manga-pipeline-deployments",
        "arn:aws:s3:::manga-pipeline-videos/*",
        "arn:aws:s3:::manga-pipeline-videos"
      ]
    },
    {
      "Effect": "Allow",
      "Action": [
        "dynamodb:GetItem",
        "dynamodb:PutItem",
        "dynamodb:UpdateItem",
        "dynamodb:Query",
        "dynamodb:Scan"
      ],
      "Resource": "arn:aws:dynamodb:*:*:table/manga-pipeline-jobs"
    },
    {
      "Effect": "Allow",
      "Action": [
        "secretsmanager:GetSecretValue"
      ],
      "Resource": [
        "arn:aws:secretsmanager:*:*:secret:manga-pipeline/*"
      ]
    },
    {
      "Effect": "Allow",
      "Action": [
        "states:StartExecution",
        "states:DescribeExecution"
      ],
      "Resource": "arn:aws:states:*:*:stateMachine:manga-pipeline*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "ssm:GetParameter",
        "ssm:GetParameters"
      ],
      "Resource": "arn:aws:ssm:*:*:parameter/manga-pipeline/*"
    }
  ]
}
```

Also attach: `AmazonSSMManagedInstanceCore` (for SSM access)

### Step 4: Package and Upload Initial Deployment

```bash
cd /path/to/manga-video-pipeline

# Set environment variables
export AWS_REGION=us-east-1
export DEPLOYMENT_BUCKET=manga-pipeline-deployments

# Run deployment script
./scripts/deploy_dashboard.sh
```

### Step 5: Launch EC2 Instance

**Using AWS Console:**

1. Go to EC2 → Launch Instance
2. **Name:** `manga-dashboard`
3. **AMI:** Ubuntu Server 24.04 LTS (or 22.04)
4. **Instance Type:** t3.micro
5. **Key Pair:** Select or create
6. **Network Settings:**
   - Allow HTTPS (443) from anywhere (0.0.0.0/0)
   - Allow HTTP (80) from anywhere (for ACME challenge)
   - Allow SSH (22) from your IP (for debugging)
7. **IAM Instance Profile:** Select the role created in Step 3
8. **Advanced Details → User Data:** Paste contents of `scripts/dashboard_userdata.sh`
9. **Environment variables in User Data:** Update these values:
   ```bash
   AWS_REGION="us-east-1"
   DYNAMODB_TABLE="manga-pipeline-jobs"
   S3_BUCKET="manga-pipeline-videos"
   DEPLOYMENT_BUCKET="manga-pipeline-deployments"
   ADMIN_SECRET_NAME="manga-pipeline/admin-credentials"
   JWT_SECRET_NAME="manga-pipeline/jwt-secret"
   STATE_MACHINE_ARN="arn:aws:states:us-east-1:123456789012:stateMachine:manga-pipeline"
   ```
10. **Tags:** Add tag `Name=manga-dashboard` (used by deploy script)
11. Launch!

**Using AWS CLI:**

```bash
# Create launch template (recommended for auto-scaling)
aws ec2 create-launch-template \
    --launch-template-name manga-dashboard-template \
    --version-description "Initial version" \
    --launch-template-data '{
      "ImageId": "ami-0c7217cdde317cfec",
      "InstanceType": "t3.micro",
      "IamInstanceProfile": {
        "Name": "manga-dashboard-role"
      },
      "SecurityGroupIds": ["sg-xxxxxxxxx"],
      "UserData": "'"$(base64 -w 0 scripts/dashboard_userdata.sh)"'",
      "TagSpecifications": [{
        "ResourceType": "instance",
        "Tags": [{"Key": "Name", "Value": "manga-dashboard"}]
      }]
    }'

# Launch instance from template
aws ec2 run-instances \
    --launch-template LaunchTemplateName=manga-dashboard-template
```

### Step 6: Verify Deployment

1. **Get Instance Public IP:**
   ```bash
   aws ec2 describe-instances \
       --filters "Name=tag:Name,Values=manga-dashboard" \
                 "Name=instance-state-name,Values=running" \
       --query 'Reservations[0].Instances[0].PublicIpAddress' \
       --output text
   ```

2. **Access Dashboard:**
   ```
   https://<PUBLIC_IP>.nip.io
   ```

3. **Check Logs:**
   ```bash
   ssh ubuntu@<PUBLIC_IP>

   # Setup logs
   tail -f /var/log/dashboard-setup.log

   # Application logs
   tail -f /var/log/manga-dashboard/dashboard.log

   # Caddy logs
   tail -f /var/log/caddy/dashboard.log

   # Service status
   systemctl status manga-dashboard
   systemctl status caddy
   ```

## Updating the Dashboard

To deploy code updates to running instances:

```bash
# Make your code changes
git add .
git commit -m "Update dashboard"

# Deploy to instances
./scripts/deploy_dashboard.sh
```

The script will:
1. Package the application code
2. Upload to S3
3. Find all running instances tagged `Name=manga-dashboard`
4. Send SSM commands to update each instance
5. Restart services automatically

**Manual Update:**

If SSM is not available, you can manually update:

```bash
ssh ubuntu@<PUBLIC_IP>

cd /opt/manga-pipeline

# Download latest
aws s3 cp s3://manga-pipeline-deployments/dashboard-latest.zip dashboard.zip

# Stop service
sudo systemctl stop manga-dashboard

# Extract
unzip -o dashboard.zip

# Update dependencies
./venv/bin/pip install -r requirements.txt

# Restart
sudo systemctl start manga-dashboard
```

## Configuration

### Environment Variables

Set in `/etc/manga-dashboard.env`:

- `AWS_REGION` - AWS region
- `DYNAMODB_TABLE` - DynamoDB table name
- `S3_BUCKET` - S3 bucket for videos
- `ADMIN_SECRET_NAME` - Secrets Manager secret name for admin credentials
- `JWT_SECRET_NAME` - Secrets Manager secret name for JWT secret
- `STATE_MACHINE_ARN` - Step Functions state machine ARN

### Caddy Configuration

Edit `/etc/caddy/Caddyfile` and reload:

```bash
sudo caddy reload --config /etc/caddy/Caddyfile
```

### Security Headers

The Caddyfile includes these security headers:
- HSTS (HTTP Strict Transport Security)
- X-Frame-Options: DENY
- X-Content-Type-Options: nosniff
- X-XSS-Protection
- Referrer-Policy
- Content-Security-Policy

## Troubleshooting

### Dashboard Not Accessible

1. **Check Security Groups:**
   - Ensure ports 80 and 443 are open
   - HTTP (80) is required for Let's Encrypt ACME challenge

2. **Check Service Status:**
   ```bash
   ssh ubuntu@<PUBLIC_IP>
   sudo systemctl status manga-dashboard
   sudo systemctl status caddy
   ```

3. **Check Logs:**
   ```bash
   # Application errors
   sudo tail -f /var/log/manga-dashboard/dashboard-error.log

   # Caddy errors
   sudo journalctl -u caddy -f
   ```

### TLS Certificate Issues

If Caddy can't provision TLS certificate:

1. **Check nip.io resolves:**
   ```bash
   dig <PUBLIC_IP>.nip.io
   ```

2. **Check Let's Encrypt rate limits:**
   - Max 5 duplicate certificates per week
   - Use staging environment for testing

3. **Manual certificate check:**
   ```bash
   sudo caddy trust
   sudo caddy validate --config /etc/caddy/Caddyfile
   ```

### Service Crashes

If the dashboard service keeps crashing:

1. **Check logs for errors:**
   ```bash
   sudo journalctl -u manga-dashboard -n 100
   ```

2. **Check environment variables:**
   ```bash
   sudo cat /etc/manga-dashboard.env
   ```

3. **Test manually:**
   ```bash
   cd /opt/manga-pipeline
   source venv/bin/activate
   export $(cat /etc/manga-dashboard.env | xargs)
   uvicorn src.dashboard.app:app --host 127.0.0.1 --port 8000
   ```

### SSM Commands Failing

If deployment via SSM fails:

1. **Check SSM agent:**
   ```bash
   ssh ubuntu@<PUBLIC_IP>
   sudo systemctl status snap.amazon-ssm-agent.amazon-ssm-agent
   ```

2. **Check IAM role:**
   - Ensure `AmazonSSMManagedInstanceCore` is attached
   - Check instance profile is assigned

3. **Manual deployment:**
   - Use manual update steps above

## Maintenance

### Rotate Secrets

**Admin Password:**
```bash
aws secretsmanager update-secret \
    --secret-id manga-pipeline/admin-credentials \
    --secret-string '{"username":"admin","password":"NEW_SECURE_PASSWORD"}'
```

**JWT Secret:**
```bash
aws secretsmanager update-secret \
    --secret-id manga-pipeline/jwt-secret \
    --secret-string "$(openssl rand -hex 32)"
```

After rotating, restart dashboard:
```bash
ssh ubuntu@<PUBLIC_IP>
sudo systemctl restart manga-dashboard
```

### Update Python Dependencies

```bash
ssh ubuntu@<PUBLIC_IP>
cd /opt/manga-pipeline

sudo systemctl stop manga-dashboard
./venv/bin/pip install --upgrade -r requirements.txt
sudo systemctl start manga-dashboard
```

### Backup

The deployment creates automatic backups in `/tmp/dashboard-backup-*.tar.gz` on each update.

To create manual backup:
```bash
ssh ubuntu@<PUBLIC_IP>
cd /opt/manga-pipeline
tar -czf /tmp/dashboard-backup-manual.tar.gz .
```

## Cost Optimization

- **t3.micro:** ~$8/month
- **Data transfer:** ~$0.09/GB (first 1GB free/month)
- **S3 storage:** Minimal for deployment packages
- **Total:** ~$10-15/month for low-traffic dashboard

For production with high availability, consider:
- Application Load Balancer + Auto Scaling Group
- Multi-AZ deployment
- CloudFront CDN for static assets

## Security Best Practices

1. **Rotate secrets regularly** (every 90 days)
2. **Use strong admin password** (generated, not dictionary words)
3. **Restrict SSH access** to specific IPs only
4. **Enable CloudWatch Logs** for audit trail
5. **Set up CloudWatch Alarms** for service health
6. **Regular security updates:**
   ```bash
   ssh ubuntu@<PUBLIC_IP>
   sudo apt update && sudo apt upgrade -y
   ```

## Production Recommendations

For production deployment:

1. **Use Route 53** instead of nip.io for custom domain
2. **Enable AWS Shield** for DDoS protection
3. **Set up CloudWatch dashboards** for monitoring
4. **Configure SNS alerts** for service failures
5. **Enable VPC Flow Logs** for network monitoring
6. **Use AWS WAF** for web application firewall
7. **Implement rate limiting** in Caddy
8. **Regular automated backups** to S3
9. **Blue-green deployment** for zero-downtime updates
10. **Load testing** before production traffic

## Support

For issues or questions:
- Check logs first (see Troubleshooting section)
- Review AWS service status: https://status.aws.amazon.com/
- Check Caddy documentation: https://caddyserver.com/docs/
