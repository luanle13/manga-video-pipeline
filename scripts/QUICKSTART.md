# Dashboard Deployment Quick Start

Fast track to deploy the admin dashboard to AWS EC2.

## Prerequisites

```bash
# Install AWS CLI v2
curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
unzip awscliv2.zip
sudo ./aws/install

# Configure AWS credentials
aws configure
```

## 1-Minute Setup

```bash
# Set variables
export AWS_REGION=us-east-1
export DEPLOYMENT_BUCKET=manga-pipeline-deployments
export DYNAMODB_TABLE=manga-pipeline-jobs
export S3_BUCKET=manga-pipeline-videos

# Create deployment bucket
aws s3 mb s3://$DEPLOYMENT_BUCKET --region $AWS_REGION

# Create secrets
aws secretsmanager create-secret \
    --name manga-pipeline/admin-credentials \
    --secret-string '{"username":"admin","password":"'$(openssl rand -base64 32)'"}' \
    --region $AWS_REGION

aws secretsmanager create-secret \
    --name manga-pipeline/jwt-secret \
    --secret-string "$(openssl rand -hex 32)" \
    --region $AWS_REGION

# Deploy package
./scripts/deploy_dashboard.sh
```

## Launch Instance

**Option 1: AWS Console**

1. Go to EC2 → Launch Instance
2. **Name:** `manga-dashboard`
3. **AMI:** Ubuntu Server 24.04 LTS
4. **Instance Type:** t3.micro
5. **Security Group:**
   - SSH (22) from Your IP
   - HTTP (80) from 0.0.0.0/0
   - HTTPS (443) from 0.0.0.0/0
6. **IAM Role:** Create role with policies:
   - `AmazonSSMManagedInstanceCore`
   - Custom policy for S3, DynamoDB, Secrets Manager (see DEPLOYMENT.md)
7. **User Data:** Copy from `scripts/dashboard_userdata.sh` and update variables
8. **Tags:** `Name=manga-dashboard`
9. **Launch!**

**Option 2: AWS CLI**

```bash
# Get Ubuntu 24.04 AMI ID
AMI_ID=$(aws ec2 describe-images \
    --owners 099720109477 \
    --filters "Name=name,Values=ubuntu/images/hvm-ssd-gp3/ubuntu-noble-24.04-amd64-server-*" \
    --query 'sort_by(Images, &CreationDate)[-1].ImageId' \
    --output text \
    --region $AWS_REGION)

# Launch instance
aws ec2 run-instances \
    --image-id $AMI_ID \
    --instance-type t3.micro \
    --iam-instance-profile Name=manga-dashboard-role \
    --security-group-ids sg-xxxxxxxxx \
    --user-data file://scripts/dashboard_userdata.sh \
    --tag-specifications 'ResourceType=instance,Tags=[{Key=Name,Value=manga-dashboard}]' \
    --region $AWS_REGION
```

## Access Dashboard

```bash
# Get instance public IP
PUBLIC_IP=$(aws ec2 describe-instances \
    --filters "Name=tag:Name,Values=manga-dashboard" \
              "Name=instance-state-name,Values=running" \
    --query 'Reservations[0].Instances[0].PublicIpAddress' \
    --output text \
    --region $AWS_REGION)

echo "Dashboard URL: https://${PUBLIC_IP}.nip.io"
```

Wait 5-10 minutes for setup to complete, then access the dashboard.

## Deploy Updates

```bash
# After code changes
git add .
git commit -m "Update dashboard"

# Deploy to all running instances
./scripts/deploy_dashboard.sh
```

## Monitor

```bash
# SSH to instance
ssh ubuntu@$PUBLIC_IP

# Check logs
tail -f /var/log/dashboard-setup.log      # Initial setup
tail -f /var/log/manga-dashboard/dashboard.log  # Application
tail -f /var/log/caddy/dashboard.log      # Caddy

# Check service status
sudo systemctl status manga-dashboard
sudo systemctl status caddy
```

## Troubleshooting

**Dashboard not accessible:**
```bash
# Check security groups allow ports 80 and 443
# Check services are running
ssh ubuntu@$PUBLIC_IP
sudo systemctl status manga-dashboard caddy

# Check Caddy can get certificate
sudo journalctl -u caddy -n 50
```

**Certificate errors:**
```bash
# Verify nip.io resolves
dig ${PUBLIC_IP}.nip.io

# Check Caddy logs
ssh ubuntu@$PUBLIC_IP
sudo journalctl -u caddy -f
```

**Service crashes:**
```bash
# Check application logs
ssh ubuntu@$PUBLIC_IP
sudo journalctl -u manga-dashboard -n 100

# Check environment variables
sudo cat /etc/manga-dashboard.env

# Restart service
sudo systemctl restart manga-dashboard
```

## Cost

- **EC2 t3.micro:** ~$8.50/month (1 vCPU, 1 GB RAM)
- **Data transfer:** ~$0.09/GB (first 1 GB free)
- **S3 storage:** Negligible for deployment packages
- **Total:** ~$10-15/month for low-traffic dashboard

## Next Steps

See [DEPLOYMENT.md](DEPLOYMENT.md) for:
- Production recommendations
- Security hardening
- High availability setup
- Monitoring and alerts
- Backup strategies
