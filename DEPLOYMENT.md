# Deployment Guide

This guide covers the complete deployment process for the Manga Video Pipeline, including initial setup and subsequent deployments.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Initial Setup (First-Time Deployment)](#initial-setup-first-time-deployment)
3. [Subsequent Deployments](#subsequent-deployments)
4. [CI/CD Pipeline](#cicd-pipeline)
5. [Manual Deployment](#manual-deployment)
6. [Post-Deployment Configuration](#post-deployment-configuration)
7. [Verification](#verification)
8. [Rollback Procedures](#rollback-procedures)
9. [Troubleshooting](#troubleshooting)

---

## Prerequisites

### Required Tools

Install the following tools on your local machine:

```bash
# AWS CLI v2
curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
unzip awscliv2.zip && sudo ./aws/install

# Terraform (>= 1.5.0)
wget https://releases.hashicorp.com/terraform/1.6.6/terraform_1.6.6_linux_amd64.zip
unzip terraform_1.6.6_linux_amd64.zip && sudo mv terraform /usr/local/bin/

# Python 3.12+
sudo apt install python3.12 python3.12-venv

# jq (for JSON processing)
sudo apt install jq
```

### AWS Account Setup

1. **AWS Account** with administrative access
2. **IAM User** with programmatic access and the following permissions:
   - `AdministratorAccess` (for initial setup) OR
   - Custom policy with: EC2, Lambda, S3, DynamoDB, IAM, Step Functions, EventBridge, CloudWatch, Secrets Manager, Budgets

3. **Configure AWS CLI:**
   ```bash
   aws configure
   # Enter your Access Key ID, Secret Access Key
   # Default region: ap-southeast-1
   # Default output: json
   ```

4. **Verify access:**
   ```bash
   aws sts get-caller-identity
   ```

### External Service Accounts

Before deployment, obtain credentials for:

| Service | Required | How to Get |
|---------|----------|------------|
| DeepInfra | Yes | Sign up at https://deepinfra.com, get API key |
| YouTube API | Yes | Create project at https://console.cloud.google.com, enable YouTube Data API v3, create OAuth credentials |
| MangaDex | No | Public API, no credentials needed |

---

## Initial Setup (First-Time Deployment)

### Step 1: Clone and Configure

```bash
# Clone the repository
git clone https://github.com/your-org/manga-video-pipeline.git
cd manga-video-pipeline

# Create Python virtual environment
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

### Step 2: Get Your AWS Account ID

```bash
export AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
echo "Your AWS Account ID: $AWS_ACCOUNT_ID"
```

### Step 3: Create Terraform Backend Resources

The Terraform state is stored in S3 with DynamoDB locking. Create these resources first:

```bash
# Create S3 bucket for Terraform state
aws s3 mb s3://manga-pipeline-tfstate-${AWS_ACCOUNT_ID} --region ap-southeast-1

# Enable versioning
aws s3api put-bucket-versioning \
  --bucket manga-pipeline-tfstate-${AWS_ACCOUNT_ID} \
  --versioning-configuration Status=Enabled

# Enable encryption
aws s3api put-bucket-encryption \
  --bucket manga-pipeline-tfstate-${AWS_ACCOUNT_ID} \
  --server-side-encryption-configuration '{
    "Rules": [{"ApplyServerSideEncryptionByDefault": {"SSEAlgorithm": "AES256"}}]
  }'

# Block public access
aws s3api put-public-access-block \
  --bucket manga-pipeline-tfstate-${AWS_ACCOUNT_ID} \
  --public-access-block-configuration '{
    "BlockPublicAcls": true,
    "IgnorePublicAcls": true,
    "BlockPublicPolicy": true,
    "RestrictPublicBuckets": true
  }'

# Create DynamoDB table for state locking
aws dynamodb create-table \
  --table-name manga-pipeline-tfstate-lock \
  --attribute-definitions AttributeName=LockID,AttributeType=S \
  --key-schema AttributeName=LockID,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST \
  --region ap-southeast-1
```

### Step 4: Create Lambda Deployment Bucket

```bash
# Create S3 bucket for Lambda packages
aws s3 mb s3://manga-pipeline-deployments-${AWS_ACCOUNT_ID} --region ap-southeast-1
```

### Step 5: Update Terraform Backend Configuration

Edit `infra/backend.tf` with your account ID:

```bash
# Update the bucket name in backend.tf
sed -i "s/123456789012/${AWS_ACCOUNT_ID}/g" infra/backend.tf
```

Or manually edit:
```hcl
# infra/backend.tf
terraform {
  backend "s3" {
    bucket         = "manga-pipeline-tfstate-YOUR_ACCOUNT_ID"  # <-- Update this
    key            = "prod/terraform.tfstate"
    region         = "ap-southeast-1"
    dynamodb_table = "manga-pipeline-tfstate-lock"
    encrypt        = true
  }
}
```

### Step 6: Create Terraform Variables File

Create `infra/prod.tfvars`:

```bash
cat > infra/prod.tfvars << EOF
# Required Variables
project_name             = "manga-video-pipeline"
environment              = "prod"
region                   = "ap-southeast-1"

# Network & Security
admin_ip                 = "YOUR_PUBLIC_IP/32"  # Get with: curl ifconfig.me

# Monitoring & Alerts
budget_alert_email       = "your-email@example.com"
monthly_budget_limit     = 120

# Lambda Deployment
lambda_deployment_bucket = "manga-pipeline-deployments-${AWS_ACCOUNT_ID}"

# Optional: Customize settings
log_retention_days       = 30
spot_instance_type       = "c5.xlarge"
dashboard_instance_type  = "t3.micro"
daily_quota              = 6
EOF
```

**Important:** Replace `YOUR_PUBLIC_IP` with your actual IP:
```bash
MY_IP=$(curl -s ifconfig.me)
sed -i "s/YOUR_PUBLIC_IP/${MY_IP}/g" infra/prod.tfvars
sed -i "s/\${AWS_ACCOUNT_ID}/${AWS_ACCOUNT_ID}/g" infra/prod.tfvars
```

### Step 7: Package Lambda Functions

```bash
# Create deployment packages for each Lambda
mkdir -p dist

# Package each Lambda function
for func in fetcher scriptgen ttsgen cleanup quota_checker; do
  echo "Packaging $func..."
  cd src/$func
  zip -r ../../dist/${func}.zip . -x "*.pyc" -x "__pycache__/*" -x "*.md"
  cd ../..

  # Add common modules
  cd src/common
  zip -ur ../../dist/${func}.zip . -x "*.pyc" -x "__pycache__/*"
  cd ../..
done

# Upload to S3
for func in fetcher scriptgen ttsgen cleanup quota_checker; do
  aws s3 cp dist/${func}.zip \
    s3://manga-pipeline-deployments-${AWS_ACCOUNT_ID}/lambda-packages/${func}-latest.zip
done
```

### Step 8: Initialize and Apply Terraform

```bash
cd infra

# Initialize Terraform
terraform init

# Validate configuration
terraform validate

# Review the plan
terraform plan -var-file=prod.tfvars -out=tfplan

# Apply the infrastructure
terraform apply tfplan
```

This will create:
- S3 bucket for assets
- DynamoDB tables (jobs, processed_manga, settings)
- Lambda functions (5)
- EC2 instances (renderer launch template, dashboard)
- Step Functions state machine
- EventBridge scheduler
- IAM roles and policies
- Security groups
- Secrets Manager secrets (placeholders)
- CloudWatch log groups and alarms
- AWS Budgets

### Step 9: Configure Secrets

After Terraform creates the placeholder secrets, update them with actual values:

```bash
# 1. DeepInfra API Key
aws secretsmanager put-secret-value \
  --secret-id manga-pipeline/deepinfra-api-key \
  --secret-string '{"api_key": "YOUR_DEEPINFRA_API_KEY"}'

# 2. YouTube OAuth Credentials
# First, run the OAuth flow to get tokens
python scripts/youtube_oauth_setup.py

# Then update the secret
aws secretsmanager put-secret-value \
  --secret-id manga-pipeline/youtube-credentials \
  --secret-string '{
    "client_id": "YOUR_CLIENT_ID.apps.googleusercontent.com",
    "client_secret": "YOUR_CLIENT_SECRET",
    "access_token": "YOUR_ACCESS_TOKEN",
    "refresh_token": "YOUR_REFRESH_TOKEN",
    "token_uri": "https://oauth2.googleapis.com/token"
  }'

# 3. Admin Dashboard Credentials
# Generate bcrypt hash for your password
ADMIN_HASH=$(python3 -c "import bcrypt; print(bcrypt.hashpw(b'YOUR_SECURE_PASSWORD', bcrypt.gensalt()).decode())")

aws secretsmanager put-secret-value \
  --secret-id manga-pipeline/admin-credentials \
  --secret-string "{\"username\": \"admin\", \"password_hash\": \"${ADMIN_HASH}\"}"

# 4. JWT Secret
JWT_SECRET=$(openssl rand -base64 32)

aws secretsmanager put-secret-value \
  --secret-id manga-pipeline/jwt-secret \
  --secret-string "{\"secret_key\": \"${JWT_SECRET}\", \"algorithm\": \"HS256\"}"
```

### Step 10: Deploy Dashboard Application

```bash
# Get dashboard instance ID
DASHBOARD_ID=$(aws ec2 describe-instances \
  --filters "Name=tag:Name,Values=manga-video-pipeline-dashboard" "Name=instance-state-name,Values=running" \
  --query 'Reservations[0].Instances[0].InstanceId' \
  --output text)

# Package dashboard
cd src/dashboard
zip -r ../../dist/dashboard.zip . -x "*.pyc" -x "__pycache__/*" -x "*.md" -x "tests/*"
cd ../..

# Add common modules
cd src/common
zip -ur ../../dist/dashboard.zip .
cd ../..

# Upload to S3
aws s3 cp dist/dashboard.zip \
  s3://manga-pipeline-deployments-${AWS_ACCOUNT_ID}/dashboard/dashboard-latest.zip

# Deploy via SSM
# Note: Dashboard runs from /opt/manga-dashboard and uses manga-dashboard.service
# The deployment fixes imports from src.common to common for standalone operation
aws ssm send-command \
  --instance-ids $DASHBOARD_ID \
  --document-name "AWS-RunShellScript" \
  --parameters commands='["cd /opt/manga-dashboard && sudo -u dashboard aws s3 cp s3://manga-pipeline-deployments-'${AWS_ACCOUNT_ID}'/dashboard/dashboard-latest.zip . && sudo -u dashboard unzip -o dashboard-latest.zip && sudo mv db.py config.py logging_config.py models.py secrets.py storage.py common/ 2>/dev/null || true && for f in *.py routes/*.py common/*.py; do sudo sed -i \"s/from src\\.common\\./from common./g\" \"$f\" 2>/dev/null; sudo sed -i \"s/from src\\.dashboard\\./from /g\" \"$f\" 2>/dev/null; done && sudo chown -R dashboard:dashboard . && sudo systemctl restart manga-dashboard"]'
```

---

## Subsequent Deployments

For ongoing deployments after initial setup, use these streamlined processes.

### Option A: Using CI/CD (Recommended)

Simply push to the `main` branch:

```bash
git add .
git commit -m "Your changes"
git push origin main
```

The GitHub Actions workflow will automatically:
1. Run tests and linting
2. Deploy infrastructure changes (Terraform)
3. Package and deploy Lambda functions
4. Deploy dashboard updates

### Option B: Manual Deployment

#### Deploy Infrastructure Changes Only

```bash
cd infra
terraform plan -var-file=prod.tfvars -out=tfplan
terraform apply tfplan
```

#### Deploy Lambda Functions Only

```bash
# Re-package and upload a specific Lambda
FUNC=scriptgen  # Change to: fetcher, scriptgen, ttsgen, cleanup, quota_checker

cd src/$FUNC
zip -r ../../dist/${FUNC}.zip . -x "*.pyc" -x "__pycache__/*"
cd ../common
zip -ur ../../dist/${FUNC}.zip .
cd ../..

aws s3 cp dist/${FUNC}.zip \
  s3://manga-pipeline-deployments-${AWS_ACCOUNT_ID}/lambda-packages/${FUNC}-latest.zip

# Update Lambda function
aws lambda update-function-code \
  --function-name manga-video-pipeline-${FUNC} \
  --s3-bucket manga-pipeline-deployments-${AWS_ACCOUNT_ID} \
  --s3-key lambda-packages/${FUNC}-latest.zip
```

#### Deploy All Lambda Functions

```bash
./scripts/deploy-lambdas.sh
```

Or manually:

```bash
for func in fetcher scriptgen ttsgen cleanup quota_checker; do
  echo "Deploying $func..."
  aws lambda update-function-code \
    --function-name manga-video-pipeline-${func//_/-} \
    --s3-bucket manga-pipeline-deployments-${AWS_ACCOUNT_ID} \
    --s3-key lambda-packages/${func}-latest.zip
done
```

#### Deploy Dashboard Only

```bash
# Set variables
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)

# Package dashboard with common modules
mkdir -p dist
cd src/dashboard
zip -r ../../dist/dashboard.zip . -x "*.pyc" -x "__pycache__/*"
cd ../common && zip -ur ../../dist/dashboard.zip . && cd ../..

# Upload to S3
aws s3 cp dist/dashboard.zip \
  s3://manga-pipeline-deployments-${AWS_ACCOUNT_ID}/dashboard/dashboard-latest.zip

# Get dashboard instance ID
DASHBOARD_ID=$(aws ec2 describe-instances \
  --filters "Name=tag:Name,Values=manga-video-pipeline-dashboard" "Name=instance-state-name,Values=running" \
  --query 'Reservations[0].Instances[0].InstanceId' --output text)

# Deploy and restart service
# Note: The deployment fixes imports from src.common to common for standalone operation
aws ssm send-command \
  --instance-ids $DASHBOARD_ID \
  --document-name "AWS-RunShellScript" \
  --parameters commands='["cd /opt/manga-dashboard && sudo -u dashboard aws s3 cp s3://manga-pipeline-deployments-'${AWS_ACCOUNT_ID}'/dashboard/dashboard-latest.zip . && sudo -u dashboard unzip -o dashboard-latest.zip && sudo mv db.py config.py logging_config.py models.py secrets.py storage.py common/ 2>/dev/null || true && for f in *.py routes/*.py common/*.py; do sudo sed -i \"s/from src\\.common\\./from common./g\" \"$f\" 2>/dev/null; sudo sed -i \"s/from src\\.dashboard\\./from /g\" \"$f\" 2>/dev/null; done && sudo chown -R dashboard:dashboard . && sudo systemctl restart manga-dashboard"]'

# Check deployment status (wait a few seconds first)
sleep 10
aws ssm send-command \
  --instance-ids $DASHBOARD_ID \
  --document-name "AWS-RunShellScript" \
  --parameters commands='["sudo systemctl status manga-dashboard | head -10"]'
```

---

## CI/CD Pipeline

### GitHub Actions Workflows

The project includes two workflows:

#### 1. CI Workflow (`.github/workflows/ci.yml`)

**Triggers:** Push to `main`/`develop`, PRs to `main`

**Jobs:**
- `lint-and-test`: Ruff, MyPy, pytest with coverage
- `integration-test`: E2E tests with mocked services
- `terraform-validate`: Format and validation checks

#### 2. Deploy Workflow (`.github/workflows/deploy.yml`)

**Triggers:** Push to `main`, manual dispatch

**Jobs:**
- `ci-check`: Ensures CI passed
- `deploy-infra`: Terraform apply
- `deploy-lambdas`: Package and deploy all Lambdas
- `deploy-dashboard`: Update dashboard via SSM
- `verify-deployment`: Health checks

### Required GitHub Secrets

Configure these in GitHub repository settings:

| Secret | Description | Example |
|--------|-------------|---------|
| `AWS_ACCESS_KEY_ID` | AWS access key | `AKIAIOSFODNN7EXAMPLE` |
| `AWS_SECRET_ACCESS_KEY` | AWS secret key | `wJalrXUtnFEMI/K7MDENG...` |
| `AWS_ACCOUNT_ID` | AWS account ID | `123456789012` |
| `ADMIN_IP` | Your IP for dashboard | `203.0.113.50/32` |
| `ALERT_EMAIL` | Email for alerts | `alerts@example.com` |

### Setting Up GitHub Secrets

```bash
# Using GitHub CLI
gh secret set AWS_ACCESS_KEY_ID --body "YOUR_ACCESS_KEY"
gh secret set AWS_SECRET_ACCESS_KEY --body "YOUR_SECRET_KEY"
gh secret set AWS_ACCOUNT_ID --body "$(aws sts get-caller-identity --query Account --output text)"
gh secret set ADMIN_IP --body "$(curl -s ifconfig.me)/32"
gh secret set ALERT_EMAIL --body "your-email@example.com"
```

### Manual Workflow Trigger

```bash
# Trigger deploy workflow manually
gh workflow run deploy.yml

# Check workflow status
gh run list --workflow=deploy.yml
```

---

## Manual Deployment

For environments without CI/CD or for debugging.

### Full Manual Deployment Script

```bash
#!/bin/bash
set -e

AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
REGION="ap-southeast-1"
PROJECT="manga-video-pipeline"

echo "=== Deploying Manga Video Pipeline ==="
echo "Account: $AWS_ACCOUNT_ID"
echo "Region: $REGION"

# 1. Package Lambda functions
echo "Packaging Lambda functions..."
mkdir -p dist
for func in fetcher scriptgen ttsgen cleanup quota_checker; do
  cd src/$func
  zip -r ../../dist/${func}.zip . -x "*.pyc" -x "__pycache__/*"
  cd ../common
  zip -ur ../../dist/${func}.zip .
  cd ../..
done

# 2. Upload to S3
# Note: Uses manga-pipeline-deployments bucket (not manga-video-pipeline-deployments)
echo "Uploading to S3..."
for func in fetcher scriptgen ttsgen cleanup quota_checker; do
  aws s3 cp dist/${func}.zip \
    s3://manga-pipeline-deployments-${AWS_ACCOUNT_ID}/lambda-packages/${func}-latest.zip
done

# 3. Apply Terraform
echo "Applying Terraform..."
cd infra
terraform init
terraform apply -var-file=prod.tfvars -auto-approve
cd ..

# 4. Update Lambda functions
echo "Updating Lambda functions..."
for func in fetcher scriptgen ttsgen cleanup quota_checker; do
  func_name="${PROJECT}-$(echo $func | tr '_' '-')"
  aws lambda update-function-code \
    --function-name $func_name \
    --s3-bucket manga-pipeline-deployments-${AWS_ACCOUNT_ID} \
    --s3-key lambda-packages/${func}-latest.zip \
    --region $REGION || true
done

# 5. Deploy dashboard
echo "Deploying dashboard..."
cd src/dashboard
zip -r ../../dist/dashboard.zip . -x "*.pyc" -x "__pycache__/*"
cd ../common && zip -ur ../../dist/dashboard.zip . && cd ../..

# Note: Dashboard uses manga-pipeline-deployments bucket (not manga-video-pipeline-deployments)
aws s3 cp dist/dashboard.zip \
  s3://manga-pipeline-deployments-${AWS_ACCOUNT_ID}/dashboard/dashboard-latest.zip

DASHBOARD_ID=$(aws ec2 describe-instances \
  --filters "Name=tag:Name,Values=${PROJECT}-dashboard" "Name=instance-state-name,Values=running" \
  --query 'Reservations[0].Instances[0].InstanceId' --output text)

if [ "$DASHBOARD_ID" != "None" ] && [ -n "$DASHBOARD_ID" ]; then
  # Deploy dashboard with import fixes for standalone operation
  # The dashboard runs from /opt/manga-dashboard and uses manga-dashboard.service
  aws ssm send-command \
    --instance-ids $DASHBOARD_ID \
    --document-name "AWS-RunShellScript" \
    --parameters commands='["cd /opt/manga-dashboard && sudo -u dashboard aws s3 cp s3://manga-pipeline-deployments-'${AWS_ACCOUNT_ID}'/dashboard/dashboard-latest.zip . && sudo -u dashboard unzip -o dashboard-latest.zip && sudo mv db.py config.py logging_config.py models.py secrets.py storage.py common/ 2>/dev/null || true && for f in *.py routes/*.py common/*.py; do sudo sed -i \"s/from src\\.common\\./from common./g\" \"$f\" 2>/dev/null; sudo sed -i \"s/from src\\.dashboard\\./from /g\" \"$f\" 2>/dev/null; done && sudo chown -R dashboard:dashboard . && sudo systemctl restart manga-dashboard"]'
fi

echo "=== Deployment Complete ==="
```

Save as `scripts/deploy.sh` and run:
```bash
chmod +x scripts/deploy.sh
./scripts/deploy.sh
```

---

## Post-Deployment Configuration

### 1. Verify Dashboard Access

```bash
# Get dashboard IP
DASHBOARD_IP=$(aws ec2 describe-instances \
  --filters "Name=tag:Name,Values=manga-video-pipeline-dashboard" "Name=instance-state-name,Values=running" \
  --query 'Reservations[0].Instances[0].PublicIpAddress' --output text)

echo "Dashboard URL: https://${DASHBOARD_IP}.nip.io"
```

### 2. Initialize Settings in DynamoDB

```bash
# Set default pipeline settings
aws dynamodb put-item \
  --table-name manga-video-pipeline-settings \
  --item '{
    "setting_key": {"S": "daily_quota"},
    "value": {"N": "6"}
  }'

aws dynamodb put-item \
  --table-name manga-video-pipeline-settings \
  --item '{
    "setting_key": {"S": "tts_voice_id"},
    "value": {"S": "vi-VN-HoaiMyNeural"}
  }'

aws dynamodb put-item \
  --table-name manga-video-pipeline-settings \
  --item '{
    "setting_key": {"S": "script_style"},
    "value": {"S": "chapter_walkthrough"}
  }'
```

### 3. Test Pipeline Manually

```bash
# Start a test execution
aws stepfunctions start-execution \
  --state-machine-arn arn:aws:states:ap-southeast-1:${AWS_ACCOUNT_ID}:stateMachine:manga-video-pipeline-pipeline \
  --name "test-$(date +%Y%m%d-%H%M%S)" \
  --input '{}'
```

---

## Verification

### Check All Resources

```bash
# Lambda functions
aws lambda list-functions --query 'Functions[?starts_with(FunctionName, `manga-video-pipeline`)].FunctionName'

# DynamoDB tables
aws dynamodb list-tables --query 'TableNames[?starts_with(@, `manga-video-pipeline`)]'

# S3 buckets
aws s3 ls | grep manga-video-pipeline

# EC2 instances
aws ec2 describe-instances \
  --filters "Name=tag:Name,Values=manga-video-pipeline-*" \
  --query 'Reservations[].Instances[].[Tags[?Key==`Name`].Value|[0],State.Name,PublicIpAddress]' \
  --output table

# Step Functions
aws stepfunctions list-state-machines --query 'stateMachines[?contains(name, `manga-video-pipeline`)]'

# Secrets Manager
aws secretsmanager list-secrets --query 'SecretList[?contains(Name, `manga-pipeline`)].Name'
```

### Health Check Script

```bash
#!/bin/bash

echo "=== Manga Video Pipeline Health Check ==="

# Check Lambda functions
echo -e "\n[Lambda Functions]"
for func in fetcher scriptgen ttsgen cleanup quota-checker; do
  status=$(aws lambda get-function --function-name manga-video-pipeline-${func} --query 'Configuration.State' --output text 2>/dev/null || echo "NOT_FOUND")
  echo "  manga-video-pipeline-${func}: $status"
done

# Check DynamoDB tables
echo -e "\n[DynamoDB Tables]"
for table in jobs processed-manga settings; do
  status=$(aws dynamodb describe-table --table-name manga-video-pipeline-${table} --query 'Table.TableStatus' --output text 2>/dev/null || echo "NOT_FOUND")
  echo "  manga-video-pipeline-${table}: $status"
done

# Check EC2 instances
echo -e "\n[EC2 Instances]"
aws ec2 describe-instances \
  --filters "Name=tag:Name,Values=manga-video-pipeline-*" \
  --query 'Reservations[].Instances[].[Tags[?Key==`Name`].Value|[0],State.Name]' \
  --output text | while read name state; do
  echo "  $name: $state"
done

# Check Step Functions
echo -e "\n[Step Functions]"
aws stepfunctions describe-state-machine \
  --state-machine-arn arn:aws:states:ap-southeast-1:$(aws sts get-caller-identity --query Account --output text):stateMachine:manga-video-pipeline-pipeline \
  --query '[name,status]' --output text 2>/dev/null || echo "  State machine: NOT_FOUND"

# Check recent executions
echo -e "\n[Recent Executions]"
aws stepfunctions list-executions \
  --state-machine-arn arn:aws:states:ap-southeast-1:$(aws sts get-caller-identity --query Account --output text):stateMachine:manga-video-pipeline-pipeline \
  --max-results 5 \
  --query 'executions[].[name,status,startDate]' \
  --output table 2>/dev/null || echo "  No executions found"

echo -e "\n=== Health Check Complete ==="
```

---

## Rollback Procedures

### Rollback Lambda Function

```bash
# List versions
aws lambda list-versions-by-function \
  --function-name manga-video-pipeline-scriptgen \
  --query 'Versions[-5:].Version'

# Rollback to previous version
aws lambda update-alias \
  --function-name manga-video-pipeline-scriptgen \
  --name prod \
  --function-version PREVIOUS_VERSION
```

### Rollback Terraform

```bash
cd infra

# View state history (if using S3 backend with versioning)
aws s3api list-object-versions \
  --bucket manga-pipeline-tfstate-${AWS_ACCOUNT_ID} \
  --prefix prod/terraform.tfstate \
  --max-keys 5

# Restore previous state
aws s3api get-object \
  --bucket manga-pipeline-tfstate-${AWS_ACCOUNT_ID} \
  --key prod/terraform.tfstate \
  --version-id PREVIOUS_VERSION_ID \
  terraform.tfstate.backup

# Apply previous state
terraform apply -state=terraform.tfstate.backup
```

### Rollback Dashboard

```bash
# Dashboard keeps previous versions in S3
aws s3 ls s3://manga-pipeline-deployments-${AWS_ACCOUNT_ID}/dashboard/

# Deploy specific version
# Note: Dashboard runs from /opt/manga-dashboard and uses manga-dashboard.service
aws ssm send-command \
  --instance-ids $DASHBOARD_ID \
  --document-name "AWS-RunShellScript" \
  --parameters commands='["cd /opt/manga-dashboard && sudo -u dashboard aws s3 cp s3://manga-pipeline-deployments-'${AWS_ACCOUNT_ID}'/dashboard/dashboard-PREVIOUS_VERSION.zip . && sudo -u dashboard unzip -o dashboard-PREVIOUS_VERSION.zip && sudo mv db.py config.py logging_config.py models.py secrets.py storage.py common/ 2>/dev/null || true && for f in *.py routes/*.py common/*.py; do sudo sed -i \"s/from src\\.common\\./from common./g\" \"$f\" 2>/dev/null; sudo sed -i \"s/from src\\.dashboard\\./from /g\" \"$f\" 2>/dev/null; done && sudo chown -R dashboard:dashboard . && sudo systemctl restart manga-dashboard"]'
```

---

## Troubleshooting

### Common Issues

#### 1. Terraform Init Fails

**Error:** `Error configuring S3 Backend`

**Solution:**
```bash
# Verify backend resources exist
aws s3 ls s3://manga-pipeline-tfstate-${AWS_ACCOUNT_ID}
aws dynamodb describe-table --table-name manga-pipeline-tfstate-lock

# If missing, create them (see Step 3 of Initial Setup)
```

#### 2. Lambda Deployment Fails

**Error:** `ResourceNotFoundException: Function not found`

**Solution:**
```bash
# Check if Lambda exists
aws lambda get-function --function-name manga-video-pipeline-scriptgen

# If not, run Terraform first
cd infra && terraform apply -var-file=prod.tfvars
```

#### 3. Dashboard Not Accessible

**Checks:**
```bash
# 1. Check instance is running
aws ec2 describe-instances \
  --filters "Name=tag:Name,Values=manga-video-pipeline-dashboard" \
  --query 'Reservations[].Instances[].[State.Name,PublicIpAddress]'

# 2. Check security group allows your IP
aws ec2 describe-security-groups \
  --group-names manga-video-pipeline-dashboard-sg \
  --query 'SecurityGroups[0].IpPermissions'

# 3. Check dashboard service (runs as manga-dashboard.service)
aws ssm send-command \
  --instance-ids $DASHBOARD_ID \
  --document-name "AWS-RunShellScript" \
  --parameters commands='["sudo systemctl status manga-dashboard"]'
```

#### 4. Step Functions Execution Fails

**Debug:**
```bash
# Get execution history
aws stepfunctions get-execution-history \
  --execution-arn arn:aws:states:ap-southeast-1:${AWS_ACCOUNT_ID}:execution:manga-video-pipeline-pipeline:EXECUTION_NAME \
  --query 'events[?type==`TaskFailed` || type==`LambdaFunctionFailed`]'

# Check Lambda logs
aws logs tail /aws/lambda/manga-video-pipeline-scriptgen --since 1h
```

#### 5. Secrets Not Found

**Error:** `ResourceNotFoundException: Secrets Manager can't find the secret`

**Solution:**
```bash
# List secrets
aws secretsmanager list-secrets --query 'SecretList[?contains(Name, `manga-pipeline`)].Name'

# If missing, re-run Terraform or create manually
aws secretsmanager create-secret \
  --name manga-pipeline/deepinfra-api-key \
  --secret-string '{"api_key": "YOUR_KEY"}'
```

#### 6. EC2 Spot Instance Not Starting

**Checks:**
```bash
# Check Spot request status
aws ec2 describe-spot-instance-requests \
  --filters "Name=tag:Name,Values=manga-video-pipeline-renderer"

# Check Spot pricing
aws ec2 describe-spot-price-history \
  --instance-types c5.xlarge \
  --product-descriptions "Linux/UNIX" \
  --start-time $(date -u +%Y-%m-%dT%H:%M:%SZ) \
  --max-items 5
```

#### 7. Lambda Package S3 Key Not Found

**Error:** `InvalidParameterValueException: S3 Error Code: NoSuchKey`

**Cause:** Lambda package naming mismatch between upload and Terraform configuration.

**Solution:** Ensure Lambda packages are uploaded with correct names:
```bash
# Correct naming format (check modules/compute/lambdas.tf for expected names):
# - manga-fetcher-latest.zip
# - script-generator-latest.zip
# - tts-processor-latest.zip
# - cleanup-latest.zip
# - quota-checker-latest.zip

# Re-upload with correct names
aws s3 cp dist/fetcher.zip s3://BUCKET/lambda-packages/manga-fetcher-latest.zip
aws s3 cp dist/scriptgen.zip s3://BUCKET/lambda-packages/script-generator-latest.zip
aws s3 cp dist/ttsgen.zip s3://BUCKET/lambda-packages/tts-processor-latest.zip
aws s3 cp dist/cleanup.zip s3://BUCKET/lambda-packages/cleanup-latest.zip
aws s3 cp dist/quota_checker.zip s3://BUCKET/lambda-packages/quota-checker-latest.zip
```

#### 8. Lambda Concurrency Limit Error

**Error:** `InvalidParameterValueException: Specified ReservedConcurrentExecutions decreases account's UnreservedConcurrentExecution below minimum`

**Cause:** AWS account doesn't have enough unreserved concurrent executions.

**Solution:** Disable reserved concurrency in `prod.tfvars`:
```hcl
lambda_reserved_concurrency = {
  manga_fetcher    = -1
  script_generator = -1
  tts_processor    = -1
  quota_checker    = -1
  cleanup          = -1
}
```

### Logs and Monitoring

```bash
# Lambda logs
aws logs tail /aws/lambda/manga-video-pipeline-fetcher --follow

# EC2 logs
aws logs tail /aws/ec2/manga-video-pipeline-renderer --follow

# Step Functions logs
aws logs tail /aws/states/manga-video-pipeline-pipeline --follow
```

### Getting Help

1. Check CloudWatch Logs for detailed error messages
2. Review Step Functions execution history
3. Check AWS Service Health Dashboard
4. Review this project's GitHub Issues

---

## Quick Reference

### Key Resource Names

| Resource | Name Pattern |
|----------|-------------|
| Deployment S3 Bucket | `manga-pipeline-deployments-${AWS_ACCOUNT_ID}` |
| Terraform State Bucket | `manga-pipeline-tfstate-${AWS_ACCOUNT_ID}` |
| Assets S3 Bucket | `manga-video-pipeline-assets-${AWS_ACCOUNT_ID}` |
| Dashboard Directory | `/opt/manga-dashboard` |
| Dashboard Service | `manga-dashboard.service` |
| Dashboard User | `dashboard` |

### Environment Variables

```bash
export AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
export AWS_REGION=ap-southeast-1
export PROJECT_NAME=manga-video-pipeline
```

### Common Commands

```bash
# Deploy all
./scripts/deploy.sh

# Deploy Lambda only
aws lambda update-function-code --function-name manga-video-pipeline-FUNC \
  --s3-bucket manga-pipeline-deployments-${AWS_ACCOUNT_ID} \
  --s3-key lambda-packages/FUNC-latest.zip

# Deploy infra only
cd infra && terraform apply -var-file=prod.tfvars

# Start pipeline manually
aws stepfunctions start-execution --state-machine-arn arn:aws:states:${AWS_REGION}:${AWS_ACCOUNT_ID}:stateMachine:${PROJECT_NAME}-pipeline

# Check pipeline status
aws stepfunctions list-executions --state-machine-arn ... --max-results 5

# View logs
aws logs tail /aws/lambda/${PROJECT_NAME}-scriptgen --follow
```
