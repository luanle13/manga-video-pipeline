# Troubleshooting Guide

This document provides solutions for common issues you may encounter when running the Manga Video Pipeline.

## Common Errors and Solutions

### General Setup Issues

#### Python Version Not Compatible
**Error**: `RuntimeError: You need Python version 3.13 or higher`

**Solution**:
- Install Python 3.13.3 or higher
- For macOS with Homebrew:
  ```bash
  brew install python@3.13
  # Or use pyenv to manage Python versions
  pyenv install 3.13.3
  pyenv global 3.13.3
  ```

#### Module Import Errors
**Error**: `ModuleNotFoundError: No module named 'celery'`

**Solution**:
- Activate your virtual environment
- Install dependencies:
  ```bash
  pip install -r requirements.txt
  # Or if using uv:
  uv pip install -r requirements.txt
  ```

#### FFmpeg Not Found
**Error**: `[Errno 2] No such file or directory: 'ffmpeg'`

**Solution**:
```bash
# macOS
brew install ffmpeg

# Ubuntu/Debian
sudo apt update
sudo apt install ffmpeg

# CentOS/RHEL
sudo yum install ffmpeg

# Windows: Download from https://ffmpeg.org/download.html
```

### API and Authentication Issues

#### OpenAI API Key Issues
**Error**: `AuthenticationError` or `Invalid API key`

**Solutions**:
1. Verify your OpenAI API key in your `.env` file
2. Check for extra spaces or quotes around the key
3. Ensure your account has sufficient credits
4. Generate a new API key from OpenAI dashboard if needed

#### YouTube OAuth Errors
**Error**: `google.auth.exceptions.RefreshError`

**Solutions**:
1. Check that your `client_secret.json` file is correctly placed
2. Regenerate credentials in Google Cloud Console
3. Ensure required APIs are enabled (YouTube Data API v3)
4. Check OAuth consent screen is properly configured

#### Platform API Rate Limits
**Error**: `Rate limit exceeded` or similar API errors

**Solutions**:
1. Implement exponential backoff in your API calls
2. Reduce parallel processing to stay within limits
3. Check your rate limits in the respective platform consoles
4. Consider spreading processing across longer time windows

### Docker-Related Issues

#### Docker Build Failures
**Error**: `ERROR [internal] load metadata for docker.io/library/python:3.13-slim`

**Solutions**:
1. Update Docker to the latest version
2. Clear Docker build cache:
   ```bash
   docker system prune -a
   ```
3. Check internet connectivity

#### Container Won't Start
**Error**: `docker-compose up` fails with various container errors

**Solutions**:
1. Check Docker daemon is running
2. View container logs:
   ```bash
   docker-compose logs <service-name>
   ```
3. Ensure sufficient system resources (RAM, disk space)
4. Check port conflicts (default port 8000)

### Database Issues

#### Database Connection Errors
**Error**: `psycopg2.OperationalError: FATAL: database "<db>" does not exist`

**Solutions**:
1. Ensure PostgreSQL container is running:
   ```bash
   docker-compose up postgres
   ```
2. Initialize database with migrations (if implemented)
3. Check `DATABASE_URL` in your environment

#### SQLite Locking Issues
**Error**: `database is locked` or `database table is locked`

**Solutions**:
1. Increase connection timeout in settings
2. Reduce concurrent database writes
3. Implement proper connection pooling
4. Check for unclosed connections in code

### Processing Pipeline Issues

#### Image Download Failures
**Error**: `HTTP ERROR 403: Forbidden` when downloading images

**Solutions**:
1. Add more user-agent rotation to scraper
2. Implement proxy rotation if needed
3. Check if the source website has implemented anti-bot measures
4. Adjust download rate limits

#### FFmpeg Processing Failures
**Error**: `FFmpeg exited with code 1` or similar encoding errors

**Solutions**:
1. Verify FFmpeg installation:
   ```bash
   ffmpeg -version
   ```
2. Check input file format compatibility
3. Verify sufficient disk space for temporary files
4. Try different video codecs or settings

#### Video Generation Issues
**Error**: Generated videos have incorrect duration or are corrupt

**Solutions**:
1. Check audio and image file formats
2. Verify duration calculations match expected values
3. Check for audio/video synchronization issues
4. Ensure image dimensions are consistent

## Debug Mode Instructions

### Enabling Debug Mode
Set the following environment variables:

```bash
LOG_LEVEL=DEBUG
DEBUG=true
CELERY_WORKER_LOG_LEVEL=DEBUG
REDIS_URL=redis://localhost:6379/0
```

### Debugging Pipeline Issues
1. **View Application Logs**:
   ```bash
   docker-compose logs -f app
   ```

2. **View Celery Worker Logs**:
   ```bash
   docker-compose logs -f celery-worker
   ```

3. **Check Database Contents**:
   ```bash
   sqlite3 data/manga_pipeline.db
   # Or connect to your PostgreSQL instance
   ```

4. **Monitor Redis Queues**:
   ```bash
   # Connect to Redis
   redis-cli
   # List queues
   KEYS *
   # Check queue length
   LLEN celery
   ```

### Debug Commands

**Check All Service Health**:
```bash
docker-compose ps
```

**Restart Specific Service**:
```bash
docker-compose restart app
docker-compose restart celery-worker
docker-compose restart redis
```

**Run Individual Components in Isolation**:
```bash
# Run only the web app
docker-compose up app

# Run only Celery worker
docker-compose run --rm celery-worker
```

## Python 3.13 Specific Issues

### Async Context Issues
**Issue**: Problems with async context managers when using new async features

**Solutions**:
- Ensure all async functions are properly awaited
- Use `asyncio.run()` for main async functions
- Check that async fixtures are properly defined in tests

### Type Hinting Issues
**Issue**: Issues with new typing features like `TypedDict`, `TypeVarTuple`, etc.

**Solutions**:
- Use compatible syntax with the installed Python version
- Update mypy configuration for Python 3.13 features
- Install latest version of type checker tools

### Dependency Compatibility
**Issue**: Some packages may not yet support Python 3.13

**Solutions**:
- Use `--pre` flag when installing packages: `pip install --pre package_name`
- Check package compatibility on PyPI
- Consider using older stable versions if needed

## Log Locations

### Application Logs
- **Docker Deployment**: View with `docker-compose logs`
- **Local Development**: Console output from `uvicorn`
- **Production**: Usually stored in `/var/log/` or configured logging service

### Celery Task Logs
- **Local**: Console output when running `celery worker`
- **Docker**: `docker-compose logs celery-worker`
- **Production**: Check logging directory in production setup

### Database Logs
- **PostgreSQL**: In the `postgres` container: `docker logs <postgres_container_id>`
- **SQLite**: No dedicated logs, but application logs contain DB queries

## Diagnostic Commands

### System Health Check
```bash
# Check if all services are running
docker-compose ps

# Check system resources
docker stats

# Check for failed tasks
docker-compose logs --tail=100 | grep "ERROR\|FAILED\|EXCEPTION"
```

### Pipeline Status Check
```bash
# Check database for recent runs
sqlite3 data/manga_pipeline.db "SELECT * FROM pipeline_runs ORDER BY started_at DESC LIMIT 10;"

# Check Redis queues
redis-cli llen celery
redis-cli llen celery__active
```

### Connectivity Tests
```bash
# Test database connection
python -c "from src.db import get_db_session; print('DB connection OK')" 

# Test Redis connection
python -c "import redis; r = redis.Redis(host='localhost', port=6379, db=0); r.ping(); print('Redis OK')"

# Test API connectivity
python -c "import asyncio, openai; asyncio.run(openai.AsyncOpenAI().models.list()); print('OpenAI API OK')"
```

## Platform-Specific Troubleshooting

### YouTube Upload Issues
- **Private Videos**: Check OAuth scopes include `youtube.upload`
- **Copyright Claims**: Ensure content is allowed under YouTube's terms
- **Geographic Restrictions**: Confirm account can upload to desired regions

### TikTok Upload Issues
- **Video Format**: Ensure video meets TikTok's format requirements (vertical, 9:16 ratio)
- **File Size**: Check video is under platform limits
- **Rate Limits**: Verify you're not exceeding TikTok's posting limits

### Facebook Upload Issues
- **Page Permissions**: Ensure token has required permissions for posting
- **Content Policies**: Check content complies with Facebook's policies
- **API Versions**: Verify using supported Graph API version

## Getting Help

If you encounter issues not covered in this guide:

1. **Check the logs** using the diagnostic commands above
2. **Verify your configuration** matches the documentation
3. **Search existing issues** in the repository
4. **Create an issue** with detailed logs and reproduction steps

For more complex debugging, you can also:
- Enable more verbose logging
- Use a debugger like `pdb` or IDE debugging tools
- Review the architecture documentation to understand component interactions