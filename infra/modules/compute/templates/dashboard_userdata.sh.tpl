#!/bin/bash
# =============================================================================
# Admin Dashboard EC2 Instance User Data Script
# =============================================================================
# This script runs on first boot to:
# 1. Install Python 3.12 and nginx
# 2. Set up the dashboard application
# 3. Configure nginx as reverse proxy with SSL (self-signed for nip.io)
# 4. Start the dashboard service
# =============================================================================

set -e

# Configuration from Terraform
REGION="${region}"
PROJECT_NAME="${project_name}"
S3_BUCKET="${s3_bucket}"
DYNAMODB_JOBS_TABLE="${dynamodb_jobs_table}"
DYNAMODB_PROCESSED_TABLE="${dynamodb_processed_table}"
DYNAMODB_SETTINGS_TABLE="${dynamodb_settings_table}"
ADMIN_CREDENTIALS_SECRET="${admin_credentials_secret}"
JWT_SECRET_NAME="${jwt_secret_name}"
STATE_MACHINE_ARN="${state_machine_arn}"
LOG_LEVEL="${log_level}"
DASHBOARD_DOMAIN="${dashboard_domain}"

# Logging setup
LOG_GROUP="/aws/ec2/$PROJECT_NAME-dashboard"
INSTANCE_ID=$(curl -s http://169.254.169.254/latest/meta-data/instance-id)
LOG_STREAM="$INSTANCE_ID/setup"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

log "Starting dashboard setup on instance: $INSTANCE_ID"

# =============================================================================
# 1. Install System Dependencies
# =============================================================================

log "Installing system dependencies..."

# Update system packages
dnf update -y

# Install Python 3.12 and development tools
dnf install -y python3.12 python3.12-pip python3.12-devel

# Install nginx and SSL tools
dnf install -y nginx openssl

# Install additional dependencies
dnf install -y \
    gcc \
    gcc-c++ \
    make \
    git \
    jq

# Set Python 3.12 as default
alternatives --set python3 /usr/bin/python3.12

# Upgrade pip
python3 -m pip install --upgrade pip

log "System dependencies installed"

# =============================================================================
# 2. Setup Application
# =============================================================================

log "Setting up dashboard application..."

# Create application directory
APP_DIR="/opt/manga-dashboard"
mkdir -p "$APP_DIR"
cd "$APP_DIR"

# Download application code from S3
aws s3 cp "s3://$S3_BUCKET/deployments/dashboard-latest.tar.gz" ./dashboard.tar.gz --region "$REGION"
tar -xzf dashboard.tar.gz
rm dashboard.tar.gz

# Install Python dependencies
python3 -m pip install -r requirements.txt

# Create application user
useradd -r -s /bin/false dashboard || true
chown -R dashboard:dashboard "$APP_DIR"

log "Application setup complete"

# =============================================================================
# 3. Configure Environment
# =============================================================================

log "Configuring environment..."

# Create environment file
cat > /etc/manga-dashboard.env << EOF
AWS_DEFAULT_REGION=$REGION
S3_BUCKET=$S3_BUCKET
DYNAMODB_JOBS_TABLE=$DYNAMODB_JOBS_TABLE
DYNAMODB_PROCESSED_TABLE=$DYNAMODB_PROCESSED_TABLE
DYNAMODB_SETTINGS_TABLE=$DYNAMODB_SETTINGS_TABLE
ADMIN_CREDENTIALS_SECRET=$ADMIN_CREDENTIALS_SECRET
JWT_SECRET_NAME=$JWT_SECRET_NAME
STATE_MACHINE_ARN=$STATE_MACHINE_ARN
LOG_LEVEL=$LOG_LEVEL
EOF

chmod 600 /etc/manga-dashboard.env

# =============================================================================
# 4. Generate Self-Signed SSL Certificate
# =============================================================================

log "Generating SSL certificate..."

SSL_DIR="/etc/nginx/ssl"
mkdir -p "$SSL_DIR"

# Get public IP for certificate
PUBLIC_IP=$(curl -s http://169.254.169.254/latest/meta-data/public-ipv4)

# Generate self-signed certificate
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
    -keyout "$SSL_DIR/dashboard.key" \
    -out "$SSL_DIR/dashboard.crt" \
    -subj "/CN=$PUBLIC_IP/O=$PROJECT_NAME/C=VN" \
    -addext "subjectAltName=IP:$PUBLIC_IP"

chmod 600 "$SSL_DIR/dashboard.key"
chmod 644 "$SSL_DIR/dashboard.crt"

log "SSL certificate generated for IP: $PUBLIC_IP"

# =============================================================================
# 5. Configure Nginx
# =============================================================================

log "Configuring nginx..."

cat > /etc/nginx/conf.d/dashboard.conf << 'NGINX_CONF'
# Redirect HTTP to HTTPS
server {
    listen 80;
    server_name _;
    return 301 https://$host$request_uri;
}

# HTTPS server
server {
    listen 443 ssl http2;
    server_name _;

    # SSL configuration
    ssl_certificate /etc/nginx/ssl/dashboard.crt;
    ssl_certificate_key /etc/nginx/ssl/dashboard.key;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256;
    ssl_prefer_server_ciphers off;

    # Security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;

    # Proxy to Flask application
    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 300;
        proxy_connect_timeout 300;
    }

    # Static files
    location /static {
        alias /opt/manga-dashboard/static;
        expires 1d;
        add_header Cache-Control "public, immutable";
    }

    # Health check endpoint
    location /health {
        proxy_pass http://127.0.0.1:5000/health;
        access_log off;
    }
}
NGINX_CONF

# Remove default nginx config
rm -f /etc/nginx/conf.d/default.conf

# Test nginx configuration
nginx -t

log "Nginx configured"

# =============================================================================
# 6. Create Systemd Service
# =============================================================================

log "Creating systemd service..."

cat > /etc/systemd/system/manga-dashboard.service << 'SERVICE_CONF'
[Unit]
Description=Manga Pipeline Admin Dashboard
After=network.target

[Service]
Type=simple
User=dashboard
Group=dashboard
WorkingDirectory=/opt/manga-dashboard
EnvironmentFile=/etc/manga-dashboard.env
ExecStart=/usr/bin/python3 -m gunicorn --workers 2 --bind 127.0.0.1:5000 --timeout 120 app:app
Restart=always
RestartSec=5

# Security hardening
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/opt/manga-dashboard/logs

[Install]
WantedBy=multi-user.target
SERVICE_CONF

# Create logs directory
mkdir -p "$APP_DIR/logs"
chown dashboard:dashboard "$APP_DIR/logs"

# Reload systemd
systemctl daemon-reload

log "Systemd service created"

# =============================================================================
# 7. Start Services
# =============================================================================

log "Starting services..."

# Enable and start nginx
systemctl enable nginx
systemctl start nginx

# Enable and start dashboard
systemctl enable manga-dashboard
systemctl start manga-dashboard

log "Services started"

# =============================================================================
# 8. Setup CloudWatch Agent (Optional)
# =============================================================================

log "Setting up CloudWatch agent..."

# Install CloudWatch agent
dnf install -y amazon-cloudwatch-agent

# Configure CloudWatch agent
cat > /opt/aws/amazon-cloudwatch-agent/etc/amazon-cloudwatch-agent.json << EOF
{
    "logs": {
        "logs_collected": {
            "files": {
                "collect_list": [
                    {
                        "file_path": "/opt/manga-dashboard/logs/*.log",
                        "log_group_name": "$LOG_GROUP",
                        "log_stream_name": "{instance_id}/application"
                    },
                    {
                        "file_path": "/var/log/nginx/access.log",
                        "log_group_name": "$LOG_GROUP",
                        "log_stream_name": "{instance_id}/nginx-access"
                    },
                    {
                        "file_path": "/var/log/nginx/error.log",
                        "log_group_name": "$LOG_GROUP",
                        "log_stream_name": "{instance_id}/nginx-error"
                    }
                ]
            }
        }
    }
}
EOF

# Start CloudWatch agent
systemctl enable amazon-cloudwatch-agent
systemctl start amazon-cloudwatch-agent

log "CloudWatch agent configured"

# =============================================================================
# 9. Final Status
# =============================================================================

log "Dashboard setup complete!"
log "Access the dashboard at: https://$PUBLIC_IP"
log "Or use nip.io: https://$PUBLIC_IP.nip.io"

# Create setup completion marker
touch /opt/manga-dashboard/.setup-complete
