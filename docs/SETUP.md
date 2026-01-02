# Setup Guide

This guide will walk you through setting up the Manga Video Pipeline on your development machine or production server.

## Prerequisites

Before setting up the pipeline, ensure you have the following:

- **Python 3.13.3** or higher (required for all new async features)
- **Docker** (version 20.10+) and **Docker Compose** (version 2.0+)
- **FFmpeg** installed and available in your system PATH
- **Git** for version control
- **Virtual environment tool** (recommended: `uv` or `venv`)

### Python 3.13.3+

This project leverages Python 3.13.3's new features, especially enhanced async capabilities. Install Python 3.13.3+ from [python.org](https://www.python.org/downloads/) or use your system's package manager:

```bash
# For macOS with Homebrew
brew install python@3.13

# For Ubuntu/Debian
sudo apt update
sudo apt install python3.13 python3.13-venv python3.13-dev
```

### Docker Installation

1. Install Docker Desktop (Windows/macOS) or Docker Engine (Linux)
2. Install Docker Compose plugin or standalone docker-compose
3. Verify installation:
   ```bash
   docker --version
   docker compose version
   ```

### FFmpeg Installation

Install FFmpeg for video/audio processing:

```bash
# For macOS
brew install ffmpeg

# For Ubuntu/Debian
sudo apt update
sudo apt install ffmpeg

# For Windows
# Download from https://ffmpeg.org/download.html
```

## Installation Steps

### Option 1: Using uv (Recommended)

1. **Install uv (Universal Virtual Environment tool):**
   ```bash
   pip install uv
   ```

2. **Clone the repository:**
   ```bash
   git clone https://github.com/your-username/manga-video-pipeline.git
   cd manga-video-pipeline
   ```

3. **Create virtual environment and install dependencies:**
   ```bash
   uv venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   uv pip install -r requirements.txt
   ```

### Option 2: Using pip

1. **Clone the repository:**
   ```bash
   git clone https://github.com/your-username/manga-video-pipeline.git
   cd manga-video-pipeline
   ```

2. **Create virtual environment and install dependencies:**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install --upgrade pip
   pip install -r requirements.txt
   ```

## Platform API Setup

The pipeline uploads content to multiple platforms. You'll need to obtain API credentials for each platform you want to use.

### YouTube API Setup

1. **Go to [Google Cloud Console](https://console.cloud.google.com/)**
2. **Create a new project or select an existing one**
3. **Enable the YouTube Data API v3**
4. **Create OAuth 2.0 credentials:**
   - Go to "Credentials" section
   - Click "Create Credentials" > "OAuth 2.0 Client IDs"
   - Select "Desktop application" as application type
   - Download the credentials JSON file
5. **Place the JSON file in `credentials/client_secret.json`**
6. **Set environment variables:**
   - `YOUTUBE_CLIENT_ID` - Your client ID
   - `YOUTUBE_CLIENT_SECRET` - Your client secret

### TikTok API Setup

1. **Go to [TikTok for Developers](https://developers.tiktok.com/)**
2. **Apply for a developer account**
3. **Create a new app in the Developer Portal**
4. **Obtain the Client Key and Client Secret**
5. **Set environment variables:**
   - `TIKTOK_CLIENT_KEY` - Your TikTok client key
   - `TIKTOK_CLIENT_SECRET` - Your TikTok client secret

### Facebook/Meta API Setup

1. **Go to [Meta for Developers](https://developers.facebook.com/)**
2. **Create a new app**
3. **Add the "Pages" product to your app**
4. **Get your App ID and App Secret**
5. **Create a Facebook Page for your content**
6. **Set environment variables:**
   - `FACEBOOK_APP_ID` - Your Facebook app ID
   - `FACEBOOK_APP_SECRET` - Your Facebook app secret
   - `FACEBOOK_PAGE_ID` - Your Facebook page ID

## Environment Configuration

1. **Copy the example environment file:**
   ```bash
   cp .env.example .env
   ```

2. **Edit `.env` and fill in your specific values:**
   ```bash
   # Open the file in your editor
   nano .env
   # or
   code .env
   ```

3. **At minimum, configure the following:**
   - `TELEGRAM_BOT_TOKEN` - For notifications
   - `TELEGRAM_CHAT_ID` - For sending notifications to
   - `OPENAI_API_KEY` - For AI features
   - Platform-specific credentials listed above

## Running the Pipeline

### Development Mode

For development, you can run different components individually:

1. **Start the dashboard:**
   ```bash
   uvicorn src.dashboard.app:app --reload
   ```

2. **Start Celery workers:**
   ```bash
   celery -A src.celery_app worker --loglevel=info
   ```

3. **Start Celery beat scheduler:**
   ```bash
   celery -A src.celery_app beat --loglevel=info
   ```

### Production Mode

For production deployment, use Docker Compose:

1. **Build and start services:**
   ```bash
   docker-compose -f docker-compose.prod.yml up --build
   ```

2. **Or run in detached mode:**
   ```bash
   docker-compose -f docker-compose.prod.yml up --build -d
   ```

## First Run Instructions

1. **Ensure all services are running (Redis, Celery, etc.)**

2. **Run the initial discovery:**
   ```bash
   python -c "from src.discovery.manager import DiscoveryManager; import asyncio; asyncio.run(DiscoveryManager().discover_trending_manga())"
   ```

3. **Trigger a manual pipeline run:**
   - Access the dashboard at `http://localhost:8000`
   - Use the "Trigger Discovery" button
   - Monitor the pipeline status

4. **Check the logs:**
   - Dashboard logs: Check your terminal where the server runs
   - Celery logs: Available via the dashboard
   - Database: Check `data/manga_pipeline.db` for records

## Verification

To verify that everything is working:

1. **Check if the dashboard is accessible** at `http://localhost:8000`
2. **Run the test suite:**
   ```bash
   pytest tests/
   ```
3. **Verify API connections by checking the dashboard status page**
4. **Check Redis and database connectivity through the dashboard**

## Troubleshooting

- **If FFmpeg is not found**: Make sure it's installed and in your PATH
- **If Docker containers fail**: Check logs with `docker logs <container_name>`
- **If API credentials don't work**: Verify they are correctly copied to the environment
- **If uploads fail**: Check rate limits and permissions for each platform

For common issues, see [TROUBLESHOOTING.md](./TROUBLESHOOTING.md).