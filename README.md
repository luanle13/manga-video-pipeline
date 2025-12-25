# Manga Video Pipeline

An automated pipeline that discovers trending manga, scrapes chapters, generates AI summaries, creates TTS audio, produces videos, and uploads to YouTube/TikTok/Facebook.

## Features

- **Manga Discovery**: Automatically discovers trending manga from various sources
- **Chapter Scraping**: Scrapes manga chapters and images
- **AI Processing**: Summarizes chapters and generates TTS audio
- **Video Generation**: Creates videos from manga images and TTS
- **Multi-Platform Upload**: Uploads videos to YouTube, TikTok, and Facebook
- **Web Dashboard**: Monitors pipeline status and results
- **Task Scheduling**: Scheduled discovery and processing tasks

## Tech Stack

- Python 3.13 with modern type hints
- Playwright, BeautifulSoup4, HTTPX for scraping
- OpenAI API for AI summarization and TTS
- FFmpeg-python, Pillow for video generation
- FastAPI, Uvicorn for dashboard
- SQLAlchemy, Aiosqlite for database
- Celery, Redis for task queue
- Google APIs for YouTube upload

## Installation

### Prerequisites

- Python 3.13
- Docker and Docker Compose
- FFmpeg

### Setup

1. Clone the repository:
   ```bash
   git clone <repository-url>
   cd manga-video-pipeline
   ```

2. Copy the environment file:
   ```bash
   cp .env.example .env
   ```

3. Edit `.env` and add your API keys:
   - OpenAI API key
   - YouTube credentials
   - Social media tokens
   - Telegram bot token (optional)

4. Install Playwright browsers:
   ```bash
   python -m playwright install chromium
   ```

## Usage

### Running with Docker (Recommended)

```bash
docker-compose up --build
```

The dashboard will be available at `http://localhost:8000`

### Running Locally

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Run the pipeline:
   ```bash
   python -m src.cli run-pipeline
   ```

3. Start the dashboard server:
   ```bash
   python -m src.cli start-server
   ```

### CLI Commands

- `run-pipeline`: Run the complete manga video pipeline
- `start-server`: Start the dashboard web server
- `discover-trending`: Start a trending manga discovery task

### Running Celery Workers

For background task processing:

```bash
# Start Celery worker
celery -A src.scheduler.celery_app worker --loglevel=info

# Start Celery beat (scheduler)
celery -A src.scheduler.celery_app beat --loglevel=info
```

## Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Discovery     │───▶│    Scraper      │───▶│      AI         │
│   (Trending     │    │ (Manga/Chapter │    │ (Summary/TTS)   │
│   Manga)        │    │    Images)      │    │                 │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                                        │
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Video Gen.    │◀───┤      AI         │───▶│   Dashboard     │
│   (Video/Audio  │    │(Script Gen.)    │    │   (Web UI)      │
│    Creation)    │    │                 │    │                 │
└─────────────────┘    └─────────────────┘    └─────────────────┘
        │
┌─────────────────┐
│   Uploader      │───▶ YouTube/TikTok/Facebook
│ (Video Upload)  │
└─────────────────┘
```

## Configuration

All configuration is handled through environment variables in the `.env` file:

- `OPENAI_API_KEY`: Your OpenAI API key
- `YOUTUBE_CREDENTIALS_PATH`: Path to YouTube credentials file
- `TELEGRAM_BOT_TOKEN`: Telegram bot token for notifications
- `DATABASE_URL`: Database connection string
- `REDIS_URL`: Redis connection string for Celery

## Project Structure

```
src/
├── config/          # Configuration and settings
├── discovery/       # Manga discovery logic
├── scraper/         # Manga scraping functionality
├── ai/              # AI processing (summarization, TTS)
├── video/           # Video generation
├── uploader/        # Video upload to platforms
├── notifications/   # Notification service
├── database/        # Database models and operations
├── dashboard/       # Web dashboard
├── scheduler/       # Task scheduling (Celery)
├── pipeline/        # Pipeline orchestration
└── cli.py          # Command-line interface
```

## License

MIT