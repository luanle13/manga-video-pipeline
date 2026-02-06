# Manga Video Pipeline

A pipeline for processing manga into video content.

## Setup

```bash
# Install dependencies
pip install -r requirements.txt

# Install dev dependencies
pip install -r requirements-dev.txt
```

## Configuration

The application uses environment variables for configuration. Required variables:

- `S3_BUCKET`: S3 bucket name for storage

Optional variables with defaults:

- `AWS_REGION`: AWS region (default: `ap-southeast-1`)
- `DYNAMODB_JOBS_TABLE`: DynamoDB jobs table name (default: `manga_jobs`)
- `DYNAMODB_MANGA_TABLE`: DynamoDB manga table name (default: `processed_manga`)
- `DYNAMODB_SETTINGS_TABLE`: DynamoDB settings table name (default: `settings`)
- `DEEPINFRA_SECRET_NAME`: AWS Secrets Manager name for DeepInfra API key
- `YOUTUBE_SECRET_NAME`: AWS Secrets Manager name for YouTube OAuth
- `ADMIN_SECRET_NAME`: AWS Secrets Manager name for admin credentials
- `MANGADEX_BASE_URL`: MangaDex API base URL
- `DEEPINFRA_BASE_URL`: DeepInfra API base URL
- `DEFAULT_VOICE_ID`: Default voice ID for TTS
- `DEFAULT_TONE`: Default tone for content generation
- `DEFAULT_DAILY_QUOTA`: Default daily quota

## Running Tests

```bash
pytest tests/
```

## Linting

```bash
ruff check .
```
