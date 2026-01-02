# Manga Video Pipeline - Production Deployment

This document provides instructions for deploying the manga video pipeline application to production on AWS EC2.

## AWS EC2 Setup (t3.small Instance)

### Prerequisites
- AWS Account with appropriate IAM permissions
- SSH key pair for EC2 access
- Domain name (optional, for SSL)

### 1. Launch EC2 Instance
1. Go to AWS Console → EC2 → Launch Instance
2. Choose Ubuntu Server 22.04 LTS (HVM) - 64-bit x86
3. Select **t3.small** instance type (2 vCPUs, 2 GiB RAM)
4. Configure security group:
   - SSH: Port 22, Source: Your IP
   - HTTP: Port 80, Source: 0.0.0.0/0
   - HTTPS: Port 443, Source: 0.0.0.0/0 (if using SSL)
   - Custom TCP: Port 8000, Source: Your IP (for the manga pipeline)

### 2. Connect to Your Instance
```bash
ssh -i your-key.pem ubuntu@your-instance-ip
```

### 3. Update System and Install Dependencies
```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y \
    apt-transport-https \
    ca-certificates \
    curl \
    gnupg \
    lsb-release \
    python3-pip \
    python3-dev \
    build-essential \
    git \
    ffmpeg \
    cron \
    nginx \
    certbot \
    python3-certbot-nginx
```

### 4. Install Docker
```bash
# Add Docker's official GPG key
sudo mkdir -p /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg

# Set up the repository
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# Update package index and install Docker
sudo apt update
sudo apt install docker-ce docker-ce-cli containerd.io docker-compose-plugin

# Add user to docker group
sudo usermod -aG docker ubuntu
```

### 5. Clone Repository
```bash
cd /home/ubuntu
git clone https://github.com/your-username/manga-video-pipeline.git
cd manga-video-pipeline
```

### 6. Set Up Application Directories
```bash
mkdir -p data
chmod 755 data

# Create environment file
cat << EOF > .env
DATABASE_URL=sqlite:///./data/manga_pipeline.db
REDIS_URL=redis://localhost:6379/0
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
TELEGRAM_CHAT_ID=your_telegram_chat_id
OPENAI_API_KEY=your_openai_api_key
YOUTUBE_CLIENT_ID=your_youtube_client_id
YOUTUBE_CLIENT_SECRET=your_youtube_client_secret
TIKTOK_CLIENT_KEY=your_tiktok_client_key
TIKTOK_CLIENT_SECRET=your_tiktok_client_secret
FACEBOOK_APP_ID=your_facebook_app_id
FACEBOOK_APP_SECRET=your_facebook_app_secret
EOF
```

### 7. Deploy Using Scripts
```bash
# Make scripts executable
chmod +x scripts/deploy.sh
chmod +x scripts/backup.sh

# Run the deployment script
./scripts/deploy.sh
```

### 8. Set Up Health Checks and Monitoring
```bash
# Add health check to crontab
crontab -l > mycron
echo "*/5 * * * * curl -f http://localhost:8000/health >/dev/null 2>&1 || echo 'Health check failed'" >> mycron
crontab mycron
rm mycron
```

### 9. Configure Nginx (Optional - for reverse proxy)
```bash
sudo tee /etc/nginx/sites-available/manga-pipeline << EOF
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
}
EOF

sudo ln -s /etc/nginx/sites-available/manga-pipeline /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

### 10. Set Up Automatic Backups
```bash
# Add daily backup to crontab
crontab -l > mycron
echo "0 2 * * * /home/ubuntu/manga-video-pipeline/scripts/backup.sh create" >> mycron
crontab mycron
rm mycron
```

### 11. Configure Resource Limits (for t3.small)
The application is already configured to respect the t3.small resource constraints:
- App: 1GB memory, 1 CPU
- Celery Worker: 2GB memory, 1.5 CPU (with burst capability)
- Celery Beat: 512MB memory, 0.5 CPU
- Redis: 512MB memory, 0.5 CPU

### Monitoring and Maintenance Tips

#### Check Service Status
```bash
docker-compose -f docker-compose.prod.yml ps
```

#### View Logs
```bash
docker-compose -f docker-compose.prod.yml logs -f app
docker-compose -f docker-compose.prod.yml logs -f celery-worker
```

#### Run Backup Manually
```bash
./scripts/backup.sh create
./scripts/backup.sh list
```

#### Restore from Backup
```bash
./scripts/backup.sh restore /path/to/backup/file
```

#### Deploy Updates
```bash
git pull origin main
./scripts/deploy.sh
```

#### Rollback in Case of Issues
```bash
./scripts/deploy.sh rollback
```

### Security Best Practices
1. Use environment variables for secrets
2. Keep the system updated with security patches
3. Monitor logs regularly
4. Use SSL certificates for production domains
5. Restrict SSH access to necessary IPs only
6. Regular database backups

### Troubleshooting
- If services fail to start, check logs: `docker-compose -f docker-compose.prod.yml logs`
- If health checks fail, verify database connectivity and service dependencies
- For performance issues, consider upgrading to t3.medium if resource limits are exceeded consistently
- Memory and CPU limits are set conservatively; adjust based on actual usage

### Cost Optimization
The t3.small instance is cost-effective for moderate loads. Consider:
- Reserved instances for long-term commitments
- t3.medium if performance demands require more resources
- Monitor cloudwatch metrics to optimize resource allocation