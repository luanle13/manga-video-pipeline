# Terraform Infrastructure Configuration

Infrastructure as Code (IaC) for the Manga Video Pipeline using Terraform.

## Overview

This Terraform configuration deploys the complete AWS infrastructure for the manga-to-video pipeline:

- **Compute**: Lambda functions, EC2 Spot instances, ECS/Fargate (optional)
- **Storage**: S3 buckets, DynamoDB tables
- **Orchestration**: Step Functions state machine
- **Networking**: VPC, subnets, security groups
- **Monitoring**: CloudWatch, SNS, Budgets
- **Security**: IAM roles/policies, Secrets Manager, KMS

## Directory Structure

```
infra/
├── README.md                    # This file
├── provider.tf                  # AWS provider and Terraform configuration
├── backend.tf                   # S3 backend for remote state
├── variables.tf                 # Input variables with validation
├── outputs.tf                   # Output values
├── terraform.tfvars.example     # Example variable values (copy to terraform.tfvars)
├── setup-backend.sh            # Script to create S3/DynamoDB backend resources
├── modules/                     # Reusable Terraform modules
│   ├── lambda/
│   ├── s3/
│   ├── dynamodb/
│   └── ec2/
└── environments/               # Environment-specific configurations (optional)
    ├── dev/
    ├── staging/
    └── prod/
```

## Prerequisites

1. **Terraform** >= 1.5.0
   ```bash
   # macOS
   brew install terraform

   # Linux
   wget https://releases.hashicorp.com/terraform/1.6.0/terraform_1.6.0_linux_amd64.zip
   unzip terraform_1.6.0_linux_amd64.zip
   sudo mv terraform /usr/local/bin/
   ```

2. **AWS CLI** v2
   ```bash
   # Verify installation
   aws --version

   # Configure credentials
   aws configure
   ```

3. **AWS Account** with administrator access

## Initial Setup

### 1. Create Backend Resources

The S3 bucket and DynamoDB table for Terraform state must be created before running `terraform init`.

```bash
cd infra

# Run setup script
./setup-backend.sh
```

This creates:
- S3 bucket: `manga-pipeline-tfstate-{account_id}`
- DynamoDB table: `manga-pipeline-tfstate-lock`

The script automatically:
- Enables bucket versioning
- Enables encryption (AES256)
- Blocks public access
- Enforces HTTPS-only
- Enables point-in-time recovery for DynamoDB

### 2. Configure Variables

```bash
# Copy example to actual file
cp terraform.tfvars.example terraform.tfvars

# Edit with your values
vim terraform.tfvars
```

**Required variables:**
- `admin_ip` - Your public IP for SSH access (get with `curl ifconfig.me`)
- `budget_alert_email` - Email for cost alerts

**Important variables:**
- `region` - AWS region (default: ap-southeast-1)
- `monthly_budget_limit` - Budget alert threshold
- `daily_quota` - Default video quota per day

See `terraform.tfvars.example` for all available variables.

### 3. Initialize Terraform

```bash
terraform init
```

This will:
- Download required providers (AWS, Random, Archive)
- Configure the S3 backend
- Initialize the working directory

### 4. Review Plan

```bash
terraform plan
```

Review the resources that will be created. Expected resources:
- ~50-60 resources depending on configuration

### 5. Deploy Infrastructure

```bash
terraform apply
```

Type `yes` to confirm and deploy.

Deployment takes approximately 10-15 minutes.

## Configuration

### Backend Configuration

The backend is configured in `backend.tf` with:
- **Bucket**: `manga-pipeline-tfstate-{account_id}`
- **Key**: `prod/terraform.tfstate`
- **Region**: `ap-southeast-1`
- **DynamoDB Table**: `manga-pipeline-tfstate-lock`
- **Encryption**: Enabled (AES256)

### Provider Configuration

AWS provider settings in `provider.tf`:
- **Region**: Configurable via `var.region`
- **Default Tags**: Applied to all resources
  - Project: manga-video-pipeline
  - Environment: prod
  - ManagedBy: terraform

### Variables

All variables are defined in `variables.tf` with:
- Type constraints
- Default values
- Validation rules
- Descriptions

See [Variables Documentation](#variables-documentation) below.

## Usage

### Common Commands

```bash
# Format code
terraform fmt

# Validate configuration
terraform validate

# Show current state
terraform show

# List resources
terraform state list

# View specific resource
terraform state show aws_s3_bucket.videos

# View outputs
terraform output

# View specific output
terraform output s3_bucket_name

# Refresh state
terraform refresh

# Plan with detailed output
terraform plan -out=tfplan

# Apply saved plan
terraform apply tfplan

# Destroy all resources (BE CAREFUL!)
terraform destroy
```

### Updating Infrastructure

```bash
# 1. Make changes to .tf files

# 2. Review changes
terraform plan

# 3. Apply changes
terraform apply

# 4. Commit changes
git add .
git commit -m "Update infrastructure"
git push
```

### Managing State

```bash
# View state
terraform show

# List all resources
terraform state list

# Remove resource from state (doesn't delete actual resource)
terraform state rm aws_s3_bucket.example

# Move resource in state (rename)
terraform state mv aws_s3_bucket.old aws_s3_bucket.new

# Pull remote state
terraform state pull

# Push local state (rarely needed)
terraform state push
```

### Importing Existing Resources

```bash
# Import S3 bucket
terraform import aws_s3_bucket.videos bucket-name

# Import DynamoDB table
terraform import aws_dynamodb_table.jobs table-name

# Import Lambda function
terraform import aws_lambda_function.fetcher function-name
```

## Outputs

After deployment, Terraform outputs useful information:

```bash
terraform output
```

Key outputs:
- `s3_bucket_name` - S3 bucket for videos
- `dynamodb_table_names` - DynamoDB table names
- `lambda_function_arns` - Lambda function ARNs
- `step_function_arn` - Step Functions state machine ARN
- `dashboard_url` - Dashboard access URL template
- `useful_commands` - AWS CLI commands for management

## Variables Documentation

### Required Variables

| Variable | Type | Description |
|----------|------|-------------|
| `admin_ip` | string | Admin IP CIDR for SSH access (e.g., `203.0.113.0/32`) |
| `budget_alert_email` | string | Email for budget and CloudWatch alerts |

### Optional Variables (with defaults)

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `project_name` | string | `manga-video-pipeline` | Project name for resources |
| `environment` | string | `prod` | Environment (dev/staging/prod) |
| `region` | string | `ap-southeast-1` | AWS region |
| `monthly_budget_limit` | number | `100` | Monthly budget limit (USD) |
| `daily_quota` | number | `10` | Default daily video quota |
| `spot_instance_type` | string | `c5.2xlarge` | EC2 Spot instance type |
| `dashboard_instance_type` | string | `t3.micro` | Dashboard instance type |
| `lambda_runtime` | string | `python3.12` | Python runtime version |

See `variables.tf` for complete list with validation rules.

## Security

### Secrets Management

Secrets are stored in AWS Secrets Manager:

```bash
# Create DeepInfra API key secret
aws secretsmanager create-secret \
    --name manga-pipeline/deepinfra-api-key \
    --secret-string "YOUR_API_KEY"

# Create admin credentials
aws secretsmanager create-secret \
    --name manga-pipeline/admin-credentials \
    --secret-string '{"username":"admin","password":"SECURE_PASSWORD"}'

# Create JWT secret
aws secretsmanager create-secret \
    --name manga-pipeline/jwt-secret \
    --secret-string "$(openssl rand -hex 32)"
```

### IAM Roles

The infrastructure creates least-privilege IAM roles:
- Lambda execution roles (per function)
- Step Functions execution role
- EC2 instance profiles
- Service-specific policies

### Encryption

- **S3**: Server-side encryption (AES256)
- **DynamoDB**: Encryption at rest enabled
- **Secrets Manager**: Encrypted by default
- **State**: Encrypted in S3

## Cost Management

### Budget Alerts

Terraform creates an AWS Budget with email alerts:
- Alert at 80% of monthly limit
- Alert at 100% of monthly limit
- Email sent to `budget_alert_email`

### Cost Optimization

**Included:**
- S3 lifecycle policies (Standard-IA → Glacier → Deep Archive)
- DynamoDB on-demand billing
- Lambda reserved concurrency limits
- EC2 Spot instances for rendering
- CloudWatch log retention policies

**Estimated Monthly Cost (low usage):**
- Lambda: ~$5-10
- DynamoDB: ~$2-5
- S3: ~$5-10
- EC2 t3.micro (dashboard): ~$8
- EC2 Spot (rendering, intermittent): ~$10-20
- **Total: ~$30-50/month**

## Troubleshooting

### State Lock Issues

If state is locked due to a failed operation:

```bash
# Force unlock (use carefully!)
terraform force-unlock LOCK_ID
```

### Backend Configuration Issues

```bash
# Re-initialize backend
terraform init -reconfigure

# Migrate from local to remote state
terraform init -migrate-state
```

### Provider Issues

```bash
# Upgrade providers
terraform init -upgrade

# Show provider requirements
terraform providers
```

### Common Errors

**Error: AccessDenied on S3 bucket**
```bash
# Check bucket exists
aws s3 ls s3://manga-pipeline-tfstate-{account_id}

# Verify AWS credentials
aws sts get-caller-identity
```

**Error: Error locking state**
```bash
# Check DynamoDB table exists
aws dynamodb describe-table --table-name manga-pipeline-tfstate-lock

# Force unlock if needed
terraform force-unlock LOCK_ID
```

## Best Practices

1. **Always review plan before apply**
   ```bash
   terraform plan -out=tfplan
   terraform apply tfplan
   ```

2. **Use workspaces for environments**
   ```bash
   terraform workspace new staging
   terraform workspace select prod
   ```

3. **Version control everything except terraform.tfvars**
   ```bash
   # Add to .gitignore
   echo "**/*.tfvars" >> .gitignore
   echo "**/.terraform/" >> .gitignore
   echo "**/*.tfstate*" >> .gitignore
   ```

4. **Use modules for reusability**
   - See `modules/` directory
   - Create modules for repeated patterns

5. **Enable state locking**
   - Already configured with DynamoDB
   - Prevents concurrent modifications

6. **Regular backups**
   - S3 bucket versioning enabled
   - DynamoDB point-in-time recovery enabled

## Multi-Environment Setup

For multiple environments (dev/staging/prod):

### Option 1: Terraform Workspaces

```bash
# Create workspaces
terraform workspace new dev
terraform workspace new staging
terraform workspace new prod

# Switch workspace
terraform workspace select dev

# Apply with workspace-specific variables
terraform apply -var-file="environments/dev.tfvars"
```

### Option 2: Separate Directories

```
infra/
├── environments/
│   ├── dev/
│   │   ├── main.tf -> ../../provider.tf
│   │   ├── variables.tf -> ../../variables.tf
│   │   └── terraform.tfvars
│   ├── staging/
│   └── prod/
```

## Maintenance

### Regular Tasks

1. **Update providers** (monthly)
   ```bash
   terraform init -upgrade
   terraform plan
   terraform apply
   ```

2. **Review state** (weekly)
   ```bash
   terraform state list
   terraform show
   ```

3. **Clean up orphaned resources**
   ```bash
   terraform refresh
   terraform plan
   ```

4. **Rotate secrets** (quarterly)
   ```bash
   aws secretsmanager update-secret --secret-id ... --secret-string ...
   ```

## Support

For issues:
1. Check [Troubleshooting](#troubleshooting) section
2. Review Terraform logs: `TF_LOG=DEBUG terraform apply`
3. Check AWS Console for resource status
4. Review CloudWatch logs

## References

- [Terraform AWS Provider](https://registry.terraform.io/providers/hashicorp/aws/latest/docs)
- [AWS Best Practices](https://docs.aws.amazon.com/wellarchitected/latest/framework/welcome.html)
- [Terraform Best Practices](https://www.terraform-best-practices.com/)
