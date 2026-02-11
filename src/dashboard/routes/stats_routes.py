"""Statistics and dashboard home routes."""

from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from src.common.db import DynamoDBClient
from src.common.logging_config import setup_logger
from src.common.models import JobStatus
from src.dashboard.auth import get_current_user

# Vietnam timezone
VIETNAM_TZ = ZoneInfo("Asia/Ho_Chi_Minh")


def get_vietnam_today() -> str:
    """
    Get today's date in Vietnam timezone (UTC+7).

    Returns:
        Date string in YYYY-MM-DD format.
    """
    now_vietnam = datetime.now(VIETNAM_TZ)
    return now_vietnam.date().isoformat()

logger = setup_logger(__name__)

router = APIRouter(tags=["Stats"], dependencies=[Depends(get_current_user)])

# Templates will be configured by main app
templates: Jinja2Templates | None = None


def set_templates(jinja_templates: Jinja2Templates):
    """Set Jinja2 templates instance."""
    global templates
    templates = jinja_templates


def get_db_client(request: Request) -> DynamoDBClient:
    """Get DynamoDB client from app state."""
    return request.app.state.db_client


class DashboardStats(BaseModel):
    """Statistics for dashboard home page."""

    videos_today: int
    videos_total: int
    videos_failed: int
    videos_pending: int
    avg_render_time_minutes: float | None
    daily_quota: int
    quota_remaining: int


@router.get("/", response_class=HTMLResponse)
async def dashboard_home(
    request: Request,
    username: str = Depends(get_current_user),
):
    """
    Render dashboard home page with statistics.

    Args:
        request: FastAPI request.
        username: Authenticated username.

    Returns:
        HTML dashboard home page.
    """
    if templates is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Templates not configured",
        )

    # Get stats for template
    db_client = get_db_client(request)

    try:
        stats = calculate_stats(db_client)
    except Exception as e:
        logger.error(
            "Failed to calculate stats",
            extra={"error": str(e)},
        )
        # Use empty stats
        stats = DashboardStats(
            videos_today=0,
            videos_total=0,
            videos_failed=0,
            videos_pending=0,
            avg_render_time_minutes=None,
            daily_quota=10,
            quota_remaining=10,
        )

    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "username": username,
            "stats": stats,
        },
    )


@router.get("/api/stats")
async def get_stats(
    db_client: DynamoDBClient = Depends(get_db_client),
) -> DashboardStats:
    """
    Get dashboard statistics.

    Args:
        db_client: DynamoDB client.

    Returns:
        Statistics object with video counts and metrics.
    """
    try:
        stats = calculate_stats(db_client)

        logger.debug(
            "Stats calculated",
            extra={
                "videos_today": stats.videos_today,
                "videos_total": stats.videos_total,
            },
        )

        return stats

    except Exception as e:
        logger.error(
            "Failed to calculate stats",
            extra={"error": str(e)},
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to calculate stats: {str(e)}",
        )


def calculate_stats(db_client: DynamoDBClient) -> DashboardStats:
    """
    Calculate dashboard statistics from database.

    Args:
        db_client: DynamoDB client.

    Returns:
        DashboardStats object with calculated metrics.
    """
    # Get all jobs
    all_jobs = db_client.list_jobs()

    # Get today's date in Vietnam timezone
    today = get_vietnam_today()

    # Calculate basic counts
    videos_total = len(all_jobs)
    videos_failed = len([j for j in all_jobs if j.status == JobStatus.failed])
    videos_pending = len(
        [
            j
            for j in all_jobs
            if j.status
            in [
                JobStatus.pending,
                JobStatus.fetching,
                JobStatus.scripting,
                JobStatus.tts,
                JobStatus.rendering,
                JobStatus.uploading,
            ]
        ]
    )

    # Count videos created today (Vietnam timezone)
    videos_today = 0
    for job in all_jobs:
        # Import here to avoid circular dependency
        from zoneinfo import ZoneInfo

        VIETNAM_TZ = ZoneInfo("Asia/Ho_Chi_Minh")

        job_date = job.created_at.astimezone(VIETNAM_TZ).date().isoformat()
        if job_date == today:
            videos_today += 1

    # Calculate average render time for completed jobs
    completed_jobs = [j for j in all_jobs if j.status == JobStatus.completed]
    avg_render_time_minutes = None

    if completed_jobs:
        total_render_time = 0
        count = 0

        for job in completed_jobs:
            # Estimate render time from created_at to updated_at
            # This is approximate; actual render time would need tracking
            render_duration = (job.updated_at - job.created_at).total_seconds()

            # Only count jobs that completed in reasonable time (< 24 hours)
            if render_duration < 86400:
                total_render_time += render_duration
                count += 1

        if count > 0:
            avg_render_time_minutes = (total_render_time / count) / 60

    # Get daily quota from settings
    try:
        settings = db_client.get_settings()
        daily_quota = settings.daily_quota
    except Exception:
        daily_quota = 10  # Default

    quota_remaining = max(0, daily_quota - videos_today)

    return DashboardStats(
        videos_today=videos_today,
        videos_total=videos_total,
        videos_failed=videos_failed,
        videos_pending=videos_pending,
        avg_render_time_minutes=avg_render_time_minutes,
        daily_quota=daily_quota,
        quota_remaining=quota_remaining,
    )
