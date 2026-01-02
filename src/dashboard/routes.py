from __future__ import annotations
from fastapi import APIRouter, Request, HTTPException, Depends
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from typing import Annotated
from pathlib import Path
from datetime import datetime
import random
import asyncio


# Create router instance
router = APIRouter()

# Set up templates
templates_dir = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=str(templates_dir))


# Mock data classes for our dashboard
class PipelineRun:
    def __init__(self, id: int, manga_title: str, chapter_number: float, status: str, 
                 started_at: str, duration: int):
        self.id = id
        self.manga_title = manga_title
        self.chapter_number = chapter_number
        self.status = status
        self.started_at = started_at
        self.duration = duration  # in seconds


class UploadStatus:
    def __init__(self, id: int, platform: str, title: str, status: str, 
                 upload_date: str, error_message: str = None):
        self.id = id
        self.platform = platform
        self.title = title
        self.status = status
        self.upload_date = upload_date
        self.error_message = error_message


class PlatformHealth:
    def __init__(self, platform: str, status: str, last_check: str, response_time: float):
        self.platform = platform
        self.status = status  # 'healthy' or 'unhealthy'
        self.last_check = last_check
        self.response_time = response_time


# Mock data generators
def get_mock_stats():
    return {
        "total_chapters_processed": random.randint(50, 200),
        "successful_uploads": random.randint(100, 300),
        "failed_uploads": random.randint(0, 10),
        "active_pipelines": random.randint(0, 5),
        "today_completed": random.randint(5, 15),
        "success_rate": random.uniform(90, 100)
    }


def get_mock_pipeline_runs():
    statuses = ["completed", "in_progress", "failed", "pending"]
    manga_titles = [
        "One Piece", "Naruto", "Bleach", "Attack on Titan", 
        "My Hero Academia", "Demon Slayer", "Jujutsu Kaisen"
    ]
    
    runs = []
    for i in range(10):
        runs.append(PipelineRun(
            id=i+1,
            manga_title=random.choice(manga_titles),
            chapter_number=round(random.uniform(1, 1000), 1),
            status=random.choice(statuses),
            started_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            duration=random.randint(30, 600)  # 30 seconds to 10 minutes
        ))
    return runs


def get_mock_uploads():
    statuses = ["completed", "in_progress", "failed"]
    platforms = ["YouTube", "TikTok", "Facebook"]
    titles = [
        "One Piece Chapter 1001",
        "Naruto Episode 500",
        "Attack on Titan Final",
        "Demon Slayer Kimetsu no Yaiba",
        "Jujutsu Kaisen Season 2"
    ]
    
    uploads = []
    for i in range(15):
        status = random.choice(statuses)
        error_msg = "Upload rate limit exceeded" if status == "failed" else None
        uploads.append(UploadStatus(
            id=i+1,
            platform=random.choice(platforms),
            title=random.choice(titles),
            status=status,
            upload_date=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            error_message=error_msg
        ))
    return uploads


def get_platform_health():
    platforms = ["YouTube", "TikTok", "Facebook"]
    health_status = []
    
    for platform in platforms:
        is_healthy = random.choice([True, True, True, False])  # 75% healthy
        health_status.append(PlatformHealth(
            platform=platform,
            status="healthy" if is_healthy else "unhealthy",
            last_check=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            response_time=round(random.uniform(50, 500), 2)  # ms
        ))
    
    return health_status


# Routes
@router.get("/", response_class=HTMLResponse)
async def dashboard_home(request: Request):
    """Main dashboard page."""
    return templates.TemplateResponse(
        request=request, 
        name="dashboard.html",
        context={
            "request": request,
            "title": "Manga Video Pipeline Dashboard"
        }
    )


@router.get("/api/stats")
async def get_stats():
    """Get statistics JSON."""
    stats = get_mock_stats()
    return JSONResponse(content=stats)


@router.get("/api/pipelines")
async def get_pipelines():
    """Get recent pipeline runs."""
    pipelines = get_mock_pipeline_runs()
    return JSONResponse(content={"runs": [vars(run) for run in pipelines]})


@router.get("/api/uploads")
async def get_uploads():
    """Get recent uploads."""
    uploads = get_mock_uploads()
    return JSONResponse(content={"uploads": [vars(upload) for upload in uploads]})


@router.get("/api/platform-health")
async def get_platform_health_status():
    """Check platform APIs health."""
    health = get_platform_health()
    return JSONResponse(content={"platforms": [vars(h) for h in health]})


@router.post("/api/trigger/discovery")
async def trigger_discovery():
    """Manually trigger manga discovery."""
    # In a real implementation, this would trigger the discovery process
    return JSONResponse(
        content={"message": "Discovery triggered successfully", "status": "success"}
    )


@router.post("/api/retry/upload/{upload_id}")
async def retry_upload(upload_id: int):
    """Retry a failed upload."""
    # In a real implementation, this would retry the specific upload
    return JSONResponse(
        content={
            "message": f"Upload {upload_id} retry initiated", 
            "status": "success",
            "upload_id": upload_id
        }
    )


# HTMX Component Routes
@router.get("/components/stats")
async def get_stats_component(request: Request):
    """HTMX partial for stats."""
    stats = get_mock_stats()
    return templates.TemplateResponse(
        request=request,
        name="components/stats.html",
        context={"request": request, "stats": stats}
    )


@router.get("/components/pipeline-list")
async def get_pipeline_list(request: Request):
    """HTMX partial for pipeline list."""
    pipelines = get_mock_pipeline_runs()
    return templates.TemplateResponse(
        request=request,
        name="components/pipeline_list.html",
        context={"request": request, "pipelines": pipelines}
    )


@router.get("/components/upload-status")
async def get_upload_status(request: Request):
    """HTMX partial for upload status."""
    uploads = get_mock_uploads()
    return templates.TemplateResponse(
        request=request,
        name="components/upload_status.html",
        context={"request": request, "uploads": uploads}
    )


@router.get("/components/platform-health")
async def get_platform_health_component(request: Request):
    """HTMX partial for platform health."""
    health = get_platform_health()
    return templates.TemplateResponse(
        request=request,
        name="components/platform_health.html",
        context={"request": request, "health": health}
    )