# Configuration Guide

This guide explains all configuration options for the Manga Video Pipeline, including environment variables and configuration files.

## Environment Variables

The application relies on environment variables for configuration. Set these in your `.env` file or system environment.

### General Configuration

```bash
# Database configuration
DATABASE_URL=sqlite:///./data/manga_pipeline.db
# For PostgreSQL: postgresql://username:password@localhost/dbname

# Redis configuration
REDIS_URL=redis://localhost:6379/0

# Logging level
LOG_LEVEL=INFO

# Timezone for scheduling
TZ=UTC

# Maximum concurrent Celery workers
CELERY_WORKER_CONCURRENCY=2
```

### API Keys and Credentials

```bash
# OpenAI API for AI features
OPENAI_API_KEY=your_openai_api_key_here

# Telegram bot for notifications
TELEGRAM_BOT_TOKEN=your_telegram_bot_token_here
TELEGRAM_CHAT_ID=your_chat_id_here

# YouTube API credentials
YOUTUBE_CLIENT_ID=your_youtube_client_id
YOUTUBE_CLIENT_SECRET=your_youtube_client_secret
YOUTUBE_REFRESH_TOKEN=your_youtube_refresh_token
YOUTUBE_CHANNEL_ID=your_youtube_channel_id

# TikTok API credentials
TIKTOK_CLIENT_KEY=your_tiktok_client_key
TIKTOK_CLIENT_SECRET=your_tiktok_client_secret
TIKTOK_ACCESS_TOKEN=your_tiktok_access_token

# Facebook/Meta API credentials
FACEBOOK_APP_ID=your_facebook_app_id
FACEBOOK_APP_SECRET=your_facebook_app_secret
FACEBOOK_PAGE_ID=your_facebook_page_id
FACEBOOK_ACCESS_TOKEN=your_facebook_access_token
```

### Pipeline Configuration

```bash
# Discovery settings
DISCOVERY_INTERVAL_HOURS=2
DISCOVERY_LIMIT=50
DISCOVERY_MAX_TRENDING_DAYS=7

# Processing settings
PROCESSING_MAX_CHAPTERS_PER_BATCH=10
PROCESSING_TARGET_DURATION_SEC=60
PROCESSING_DEFAULT_VOICE=alloy
PROCESSING_DEFAULT_SPEED=1.0

# Upload settings
UPLOAD_RETRY_ATTEMPTS=3
UPLOAD_RETRY_DELAY_MIN=60
UPLOAD_DEFAULT_LANGUAGE=en

# Temporary file settings
TEMP_CLEANUP_DAYS=7
TEMP_DIR=./temp/
DATA_DIR=./data/
```

### Notification Settings

```bash
# Notification timing
NOTIFICATION_DAILY_SUMMARY_TIME=23:00  # 11 PM UTC
NOTIFICATION_FAILED_UPLOAD_ALERT=true

# Notification content
NOTIFICATION_ENABLE_SUCCESS=true
NOTIFICATION_ENABLE_ERROR=true
NOTIFICATION_ENABLE_SUMMARY=true
```

### Performance Settings

```bash
# Async settings
ASYNC_MAX_WORKERS=5
ASYNC_TIMEOUT_SECONDS=300

# Memory limits for processing
VIDEO_MEMORY_LIMIT_MB=2048
AUDIO_MEMORY_LIMIT_MB=512
IMAGE_MEMORY_LIMIT_MB=256

# Rate limits
API_RATE_LIMIT_REQUESTS=100
API_RATE_LIMIT_WINDOW=60

# Concurrency limits
CONCURRENT_IMAGE_DOWNLOADS=5
CONCURRENT_VIDEO_PROCESSES=2
CONCURRENT_UPLOADS=3
```

## Example Development Configuration

```bash
# .env.development

# General settings
DATABASE_URL=sqlite:///./data/dev_manga_pipeline.db
REDIS_URL=redis://localhost:6379/1
LOG_LEVEL=DEBUG
TZ=America/Los_Angeles

# API keys (fill with your actual keys)
OPENAI_API_KEY=
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=

# Platform credentials
YOUTUBE_CLIENT_ID=
YOUTUBE_CLIENT_SECRET=
YOUTUBE_REFRESH_TOKEN=

TIKTOK_CLIENT_KEY=
TIKTOK_CLIENT_SECRET=
TIKTOK_ACCESS_TOKEN=

FACEBOOK_APP_ID=
FACEBOOK_APP_SECRET=
FACEBOOK_PAGE_ID=
FACEBOOK_ACCESS_TOKEN=

# Pipeline settings
PROCESSING_TARGET_DURATION_SEC=30
PROCESSING_DEFAULT_VOICE=alloy
PROCESSING_DEFAULT_SPEED=1.0

# Temporary settings
TEMP_CLEANUP_DAYS=1
TEMP_DIR=./temp_dev/
DATA_DIR=./data_dev/

# Development-specific
CELERY_WORKER_CONCURRENCY=1
ASYNC_MAX_WORKERS=2
CONCURRENT_VIDEO_PROCESSES=1
```

## Example Production Configuration

```bash
# .env.production

# General settings
DATABASE_URL=postgresql://user:password@db-host:5432/manga_pipeline
REDIS_URL=redis://redis-host:6379/0
LOG_LEVEL=INFO
TZ=UTC

# API keys (stored securely)
OPENAI_API_KEY=${OPENAI_API_KEY}
TELEGRAM_BOT_TOKEN=${TELEGRAM_BOT_TOKEN}
TELEGRAM_CHAT_ID=${TELEGRAM_CHAT_ID}

# Platform credentials (stored securely)
YOUTUBE_CLIENT_ID=${YOUTUBE_CLIENT_ID}
YOUTUBE_CLIENT_SECRET=${YOUTUBE_CLIENT_SECRET}
YOUTUBE_REFRESH_TOKEN=${YOUTUBE_REFRESH_TOKEN}

TIKTOK_CLIENT_KEY=${TIKTOK_CLIENT_KEY}
TIKTOK_CLIENT_SECRET=${TIKTOK_CLIENT_SECRET}
TIKTOK_ACCESS_TOKEN=${TIKTOK_ACCESS_TOKEN}

FACEBOOK_APP_ID=${FACEBOOK_APP_ID}
FACEBOOK_APP_SECRET=${FACEBOOK_APP_SECRET}
FACEBOOK_PAGE_ID=${FACEBOOK_PAGE_ID}
FACEBOOK_ACCESS_TOKEN=${FACEBOOK_ACCESS_TOKEN}

# Pipeline settings
PROCESSING_TARGET_DURATION_SEC=60
PROCESSING_DEFAULT_VOICE=alloy
PROCESSING_DEFAULT_SPEED=1.0

# Temporary settings
TEMP_CLEANUP_DAYS=7
TEMP_DIR=/app/temp/
DATA_DIR=/app/data/

# Performance settings
CELERY_WORKER_CONCURRENCY=4
ASYNC_MAX_WORKERS=10
CONCURRENT_VIDEO_PROCESSES=2
CONCURRENT_UPLOADS=4

# Rate limiting
API_RATE_LIMIT_REQUESTS=1000
API_RATE_LIMIT_WINDOW=3600

# Security
ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com
CSRF_TRUSTED_ORIGINS=yourdomain.com
SECURE_SSL_REDIRECT=true
</pre>

## Docker Compose Configuration

For Docker deployments, you can also configure services through `docker-compose.yml`:

```yaml
version: '3.8'

services:
  app:
    build: .
    environment:
      - DATABASE_URL=postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@postgres:5432/${POSTGRES_DB}
      - REDIS_URL=redis://redis:6379/0
      - LOG_LEVEL=INFO
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - TELEGRAM_BOT_TOKEN=${TELEGRAM_BOT_TOKEN}
      - YOUTUBE_CLIENT_ID=${YOUTUBE_CLIENT_ID}
      - YOUTUBE_CLIENT_SECRET=${YOUTUBE_CLIENT_SECRET}
    volumes:
      - ./data:/app/data
      - ./temp:/app/temp
    depends_on:
      - postgres
      - redis
    restart: unless-stopped
    deploy:
      resources:
        limits:
          memory: 2G
          cpus: '1.0'
        reservations:
          memory: 1G
          cpus: '0.5'

  celery-worker:
    build: .
    command: celery -A src.celery_app worker --loglevel=info
    environment:
      - DATABASE_URL=postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@postgres:5432/${POSTGRES_DB}
      - REDIS_URL=redis://redis:6379/0
      - LOG_LEVEL=INFO
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      # ... other environment variables
    volumes:
      - ./data:/app/data
      - ./temp:/app/temp
    depends_on:
      - postgres
      - redis
    restart: unless-stopped
    deploy:
      resources:
        limits:
          memory: 4G
          cpus: '2.0'
        reservations:
          memory: 2G
          cpus: '1.0'

  postgres:
    image: postgres:15-alpine
    environment:
      - POSTGRES_DB=${POSTGRES_DB}
      - POSTGRES_USER=${POSTGRES_USER}
      - POSTGRES_PASSWORD=${POSTGRES_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    restart: unless-stopped

  redis:
    image: redis:7-alpine
    volumes:
      - redis_data:/data
    restart: unless-stopped
    command: redis-server --appendonly yes

volumes:
  postgres_data:
  redis_data:
```

## Configuration Validation

To validate your configuration:

1. **Check all required environment variables are set:**
   ```bash
   python -c "import os; from src.config import validate_config; validate_config()"
   ```

2. **Test API connectivity:**
   ```bash
   python -c "from src.auth import test_api_connections; test_api_connections()"
   ```

3. **Run the configuration checker:**
   ```bash
   python scripts/config_check.py
   ```

## Security Best Practices

1. **Never commit credentials to version control**
2. **Use environment variables or secure vaults for secrets**
3. **Set appropriate file permissions on your .env file (chmod 600)**
4. **Regularly rotate API keys and credentials**
5. **Use different credentials for development and production**

## Troubleshooting Configuration Issues

- **Missing environment variable errors**: Check that all required environment variables are set
- **API authentication failures**: Verify your credentials are correct and have the required scopes
- **Database connection errors**: Check your DATABASE_URL format and credentials
- **Redis connection timeouts**: Verify Redis is running and accessible
- **Permission denied errors**: Check file permissions for temp and data directories

For more help with configuration issues, see [TROUBLESHOOTING.md](./TROUBLESHOOTING.md).