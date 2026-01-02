# Architecture Overview

This document provides a comprehensive overview of the Manga Video Pipeline architecture, including system design, components, and data flow.

## System Design

The Manga Video Pipeline is built as a distributed system using microservices principles. The architecture is designed to be scalable, maintainable, and resilient to failures.

### High-Level Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Discovery     │    │   Processing    │    │   Upload        │
│   Services      │    │   Services      │    │   Services      │
├─────────────────┤    ├─────────────────┤    ├─────────────────┤
│ • MangaDex API  │    │ • Scraper       │    │ • YouTube Uploader│
│ • Trend Analysis│    │ • Summarization │    │ • TikTok Uploader │
│ • Scheduling    │    │ • Text-to-Speech│    │ • Facebook Uploader│
└─────────────────┘    │ • Video Gen     │    │ • Notification  │
                       └─────────────────┘    └─────────────────┘
                                │                       │
                                ▼                       ▼
                    ┌───────────────────────────────────────┐
                    │        Message Queue (Redis)        │
                    └───────────────────────────────────────┘
                                │
                                ▼
                    ┌───────────────────────────────────────┐
                    │         Data Storage Layer          │
                    ├─────────────────┬─────────────────────┤
                    │   Database      │    File Storage     │
                    │ (SQLite/PostgreSQL) │ (Temp, Data)    │
                    └─────────────────┴─────────────────────┘
                                │
                                ▼
                    ┌───────────────────────────────────────┐
                    │          Dashboard/UI               │
                    │        (FastAPI + HTMX)             │
                    └───────────────────────────────────────┘
```

## Components Description

### 1. Discovery Layer
**Purpose**: Identifies trending manga and chapters to process.

- **MangaDex Integration**:
  - Handles API communication with MangaDex
  - Retrieves trending manga data
  - Implements rate limiting and caching
  - Stores metadata in database

- **Trend Analysis Engine**:
  - Analyzes manga popularity trends
  - Filters content based on configurable criteria
  - Schedules processing of selected content

- **Scheduler**:
  - Uses Celery Beat for periodic tasks
  - Configurable intervals (default: every 2 hours)
  - Handles discovery and processing schedules

### 2. Processing Layer
**Purpose**: Converts manga chapters into video content.

- **Web Scraper**:
  - Downloads manga chapter images
  - Handles rate limiting and proxy rotation
  - Implements retry logic for failed downloads
  - Stores images temporarily

- **AI Summarizer**:
  - Uses GPT-4o-mini for chapter summarization
  - Generates narration scripts
  - Supports multiple languages (English, Vietnamese)
  - Manages API rate limits and costs

- **Text-to-Speech Service**:
  - Converts text to audio using OpenAI TTS
  - Multiple voice options (alloy, echo, fable, onyx, nova, shimmer)
  - Configurable speed settings
  - Audio quality optimization

- **Video Generator**:
  - Combines images and audio into video
  - Creates vertical videos (1080x1920) for social media
  - Applies transitions and effects
  - Optimizes for YouTube Shorts, TikTok, and Facebook Reels

### 3. Upload Layer
**Purpose**: Distributes processed content across platforms.

- **Platform Managers**:
  - YouTube Manager: Handles YouTube Data API
  - TikTok Manager: Interfaces with TikTok Content API
  - Facebook Manager: Uses Meta Graph API
  - Consistent interface across platforms

- **Upload Orchestration**:
  - Parallel upload to multiple platforms
  - Retry logic for failed uploads
  - Progress tracking and status updates

- **Notification System**:
  - Telegram bot integration
  - Success/error notifications
  - Daily summary reports
  - Platform health alerts

### 4. Infrastructure Components
**Purpose**: Support services for the pipeline.

- **Message Queue (Redis)**:
  - Task distribution with Celery
  - Caching for frequently accessed data
  - Session management
  - Real-time dashboard updates

- **Database Layer**:
  - PostgreSQL for production (SQLite for development)
  - Stores pipeline run metadata
  - Tracks upload statuses
  - Maintains configuration data

- **Dashboard (FastAPI + HTMX)**:
  - Real-time monitoring interface
  - Configuration management
  - Manual trigger controls
  - Historical data visualization

## Data Flow

### Core Pipeline Flow

```
1. Discovery Service
   ↓
   Queries MangaDex API → Identifies trending content → Schedules processing

2. Scraper Service (Celery Task)
   ↓
   Downloads chapter images → Validates content → Stores temp files

3. Summarizer Service (Celery Task)
   ↓
   Processes images → Generates summary → Creates narration script

4. TTS Service (Celery Task)
   ↓
   Converts script to audio → Applies voice settings → Saves audio file

5. Video Generator (Celery Task)
   ↓
   Combines images & audio → Applies effects → Creates final video

6. Metadata Generator (Celery Task)
   ↓
   Creates titles, descriptions, tags → Optimizes for platforms

7. Upload Services (Celery Tasks - Parallel)
   ↓
   Upload to YouTube/TikTok/Facebook → Monitors progress → Reports status

8. Notification Service
   ↓
   Sends Telegram updates → Daily summaries → Error reports
```

### Async/Sync Boundary Management

Python 3.13's enhanced async capabilities are used throughout:

- **Async Web Requests**: All API calls are async using httpx
- **Task Parallelization**: Celery tasks run async where possible
- **Database Operations**: Async SQLAlchemy for database operations
- **File Operations**: Async file I/O for large file processing
- **System Integration**: asyncio.subprocess for FFmpeg calls

## Technology Stack

### Backend Technologies
- **Python 3.13.3**: Core language with new async features
- **FastAPI**: Web framework with automatic API documentation
- **Celery 5.4+**: Distributed task queue with Redis broker
- **SQLAlchemy**: ORM with async support
- **Redis**: Message queuing and caching
- **PostgreSQL**: Production-grade relational database

### AI and Processing
- **OpenAI API**: GPT-4o-mini for summarization and TTS-1 for audio
- **FFmpeg**: Video/audio processing engine
- **Pillow**: Image manipulation
- **Playwright**: Advanced web scraping

### Frontend Technologies
- **Jinja2**: Server-side templating
- **HTMX**: Dynamic UI updates without heavy JavaScript
- **Tailwind CSS**: Utility-first styling framework
- **Vanilla JavaScript**: Enhanced interactivity

### Deployment Technologies
- **Docker**: Containerization and orchestration
- **Docker Compose**: Multi-container orchestration
- **Supervisor**: Process management in containers
- **Nginx**: Reverse proxy and static file serving

## Scalability Considerations

### Horizontal Scaling
- **Worker Scaling**: Multiple Celery worker instances
- **Load Balancing**: NGINX distributes API requests
- **Database Read Replicas**: Separate read/write pools
- **CDN Integration**: Image and video caching

### Performance Optimization
- **Caching Strategy**: Redis for frequently accessed data
- **Batch Processing**: Efficient bulk operations
- **Asynchronous I/O**: Non-blocking operations throughout
- **Resource Pooling**: Connection and worker reuse

### Resilience Patterns
- **Circuit Breaker**: Prevents cascading failures
- **Retry Logic**: Automatic recovery from transient errors
- **Fallback Mechanisms**: Alternative processing paths
- **Monitoring**: Comprehensive health checks

## Deployment Architecture

### Production Environment
```
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
│   Load Balancer │  │   API Gateway   │  │ Monitoring &    │
│     (NGINX)     │  │   (Auth/Rate    │  │   Analytics     │
└─────────┬───────┘  │    Limiting)    │  └─────────────────┘
          │          └─────────┬───────┘
          │                    │
          └────────────────────┼───────────────────────────┐
                               │                           │
                   ┌───────────▼───────────┐   ┌───────────▼───────────┐
                   │     Web Servers       │   │     Task Queue        │
                   │   (Multiple Instances)│   │   (Redis Cluster)     │
                   │     (Gunicorn)        │   │                       │
                   └───────────┬───────────┘   └───────────┬───────────┘
                               │                           │
                   ┌───────────▼───────────┐   ┌───────────▼───────────┐
                   │      Database         │   │   Task Workers        │
                   │   (PostgreSQL Replicas) │ │ (Multiple Instances)  │
                   └───────────────────────┘   └───────────────────────┘
```

This architecture ensures high availability, scalability, and fault tolerance for the manga video pipeline system.