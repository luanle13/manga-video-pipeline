#!/bin/bash
set -e

# EC2 User Data Script for Manga Video Pipeline Admin Dashboard
# This script runs once when the EC2 instance is first launched
# It sets up Python, Caddy, and the dashboard application as systemd services

# =============================================================================
# Configuration
# =============================================================================

# These should be set via EC2 instance tags or Launch Template environment variables
AWS_REGION="${AWS_REGION:-us-east-1}"
DYNAMODB_TABLE="${DYNAMODB_TABLE:-manga-pipeline-jobs}"
S3_BUCKET="${S3_BUCKET:-manga-pipeline-videos}"
DEPLOYMENT_BUCKET="${DEPLOYMENT_BUCKET:-manga-pipeline-deployments}"
ADMIN_SECRET_NAME="${ADMIN_SECRET_NAME:-manga-pipeline/admin-credentials}"
JWT_SECRET_NAME="${JWT_SECRET_NAME:-manga-pipeline/jwt-secret}"
STATE_MACHINE_ARN="${STATE_MACHINE_ARN}"

# Application settings
APP_USER="ubuntu"
APP_DIR="/opt/manga-pipeline"
LOG_DIR="/var/log/manga-dashboard"

# =============================================================================
# Logging
# =============================================================================

exec > >(tee -a /var/log/dashboard-setup.log)
exec 2>&1

echo "==================================================="
echo "Dashboard Setup Started: $(date)"
echo "==================================================="

# =============================================================================
# Install System Dependencies
# =============================================================================

echo "[1/8] Installing system dependencies..."

# Update package list
apt-get update

# Install Python 3.12 (Ubuntu 24.04 has it by default, for 22.04 use deadsnakes PPA)
if ! python3.12 --version &>/dev/null; then
    echo "Installing Python 3.12 from deadsnakes PPA..."
    apt-get install -y software-properties-common
    add-apt-repository -y ppa:deadsnakes/ppa
    apt-get update
    apt-get install -y python3.12 python3.12-venv python3.12-dev
fi

# Install pip for Python 3.12
apt-get install -y python3-pip

# Install Caddy
echo "Installing Caddy..."
apt-get install -y debian-keyring debian-archive-keyring apt-transport-https curl
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | tee /etc/apt/sources.list.d/caddy-stable.list
apt-get update
apt-get install -y caddy

# Install AWS CLI v2
if ! aws --version &>/dev/null; then
    echo "Installing AWS CLI v2..."
    cd /tmp
    curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
    apt-get install -y unzip
    unzip -q awscliv2.zip
    ./aws/install
    rm -rf aws awscliv2.zip
fi

# Install git
apt-get install -y git

# =============================================================================
# Get EC2 Metadata
# =============================================================================

echo "[2/8] Getting EC2 metadata..."

# Get instance metadata
TOKEN=$(curl -X PUT "http://169.254.169.254/latest/api/token" -H "X-aws-ec2-metadata-token-ttl-seconds: 21600")
PUBLIC_IP=$(curl -H "X-aws-ec2-metadata-token: $TOKEN" http://169.254.169.254/latest/meta-data/public-ipv4)
INSTANCE_ID=$(curl -H "X-aws-ec2-metadata-token: $TOKEN" http://169.254.169.254/latest/meta-data/instance-id)
AVAILABILITY_ZONE=$(curl -H "X-aws-ec2-metadata-token: $TOKEN" http://169.254.169.254/latest/meta-data/placement/availability-zone)
REGION=$(echo $AVAILABILITY_ZONE | sed 's/[a-z]$//')

echo "Instance ID: $INSTANCE_ID"
echo "Public IP: $PUBLIC_IP"
echo "Region: $REGION"

# Set dashboard domain using nip.io
DASHBOARD_DOMAIN="${PUBLIC_IP}.nip.io"
echo "Dashboard Domain: $DASHBOARD_DOMAIN"

# =============================================================================
# Create Application Directory
# =============================================================================

echo "[3/8] Creating application directory..."

mkdir -p $APP_DIR
mkdir -p $LOG_DIR
chown -R $APP_USER:$APP_USER $APP_DIR $LOG_DIR

# =============================================================================
# Download Application Code
# =============================================================================

echo "[4/8] Downloading application code..."

# Download from S3 deployment bucket
cd $APP_DIR
sudo -u $APP_USER aws s3 cp "s3://${DEPLOYMENT_BUCKET}/dashboard-latest.zip" dashboard.zip --region $REGION

# Extract
sudo -u $APP_USER unzip -q -o dashboard.zip
rm dashboard.zip

# =============================================================================
# Install Python Dependencies
# =============================================================================

echo "[5/8] Installing Python dependencies..."

cd $APP_DIR

# Create virtual environment
sudo -u $APP_USER python3.12 -m venv venv

# Install dependencies
sudo -u $APP_USER ./venv/bin/pip install --upgrade pip
sudo -u $APP_USER ./venv/bin/pip install -r requirements.txt

# =============================================================================
# Configure Environment Variables
# =============================================================================

echo "[6/8] Configuring environment variables..."

# Create environment file for the dashboard service
cat > /etc/manga-dashboard.env <<EOF
# AWS Configuration
AWS_REGION=$REGION
AWS_DEFAULT_REGION=$REGION

# DynamoDB
DYNAMODB_TABLE=$DYNAMODB_TABLE

# S3
S3_BUCKET=$S3_BUCKET

# Secrets Manager
ADMIN_SECRET_NAME=$ADMIN_SECRET_NAME
JWT_SECRET_NAME=$JWT_SECRET_NAME

# State Machine
STATE_MACHINE_ARN=$STATE_MACHINE_ARN

# Application
PYTHONPATH=$APP_DIR
LOG_LEVEL=INFO
EOF

chmod 600 /etc/manga-dashboard.env

# =============================================================================
# Create Systemd Service for Uvicorn
# =============================================================================

echo "[7/8] Creating systemd services..."

# Uvicorn service
cat > /etc/systemd/system/manga-dashboard.service <<EOF
[Unit]
Description=Manga Video Pipeline Admin Dashboard
After=network.target

[Service]
Type=simple
User=$APP_USER
Group=$APP_USER
WorkingDirectory=$APP_DIR
EnvironmentFile=/etc/manga-dashboard.env

# Use virtual environment Python
ExecStart=$APP_DIR/venv/bin/uvicorn src.dashboard.app:app \\
    --host 127.0.0.1 \\
    --port 8000 \\
    --log-level info \\
    --access-log

# Restart on failure
Restart=always
RestartSec=5s

# Logging
StandardOutput=append:$LOG_DIR/dashboard.log
StandardError=append:$LOG_DIR/dashboard-error.log

# Security
NoNewPrivileges=true
PrivateTmp=true

[Install]
WantedBy=multi-user.target
EOF

# =============================================================================
# Configure Caddy
# =============================================================================

# Copy Caddyfile to Caddy config directory
mkdir -p /etc/caddy
cp $APP_DIR/scripts/Caddyfile /etc/caddy/Caddyfile

# Create Caddy environment file with domain
cat > /etc/caddy/env <<EOF
DASHBOARD_DOMAIN=$DASHBOARD_DOMAIN
EOF

# Update Caddy systemd service to use environment file
mkdir -p /etc/systemd/system/caddy.service.d
cat > /etc/systemd/system/caddy.service.d/override.conf <<EOF
[Service]
EnvironmentFile=/etc/caddy/env
EOF

# Create Caddy log directory
mkdir -p /var/log/caddy
chown caddy:caddy /var/log/caddy

# =============================================================================
# Start Services
# =============================================================================

echo "[8/8] Starting services..."

# Reload systemd
systemctl daemon-reload

# Enable services to start on boot
systemctl enable manga-dashboard.service
systemctl enable caddy.service

# Start services
systemctl start manga-dashboard.service
systemctl start caddy.service

# Wait a moment for services to start
sleep 5

# Check service status
echo "==================================================="
echo "Service Status:"
echo "==================================================="
systemctl status manga-dashboard.service --no-pager || true
systemctl status caddy.service --no-pager || true

# =============================================================================
# Verification
# =============================================================================

echo "==================================================="
echo "Setup Complete!"
echo "==================================================="
echo "Dashboard URL: https://$DASHBOARD_DOMAIN"
echo "Instance ID: $INSTANCE_ID"
echo "Public IP: $PUBLIC_IP"
echo ""
echo "Logs:"
echo "  - Setup: /var/log/dashboard-setup.log"
echo "  - Application: $LOG_DIR/dashboard.log"
echo "  - Caddy: /var/log/caddy/dashboard.log"
echo ""
echo "Service Management:"
echo "  - Dashboard: systemctl status manga-dashboard"
echo "  - Caddy: systemctl status caddy"
echo "==================================================="

# Test local endpoint
echo "Testing local endpoint..."
curl -f http://localhost:8000/login || echo "Warning: Local endpoint not responding"

echo "Dashboard setup completed at: $(date)"
