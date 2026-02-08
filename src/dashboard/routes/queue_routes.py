"""Queue management routes for admin dashboard."""

from typing import Literal

import boto3
from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request, status
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from src.common.config import get_settings
from src.common.db import DynamoDBClient
from src.common.logging_config import setup_logger
from src.common.models import JobStatus
from src.dashboard.auth import get_current_user

logger = setup_logger(__name__)

router = APIRouter(tags=["Queue"], dependencies=[Depends(get_current_user)])

# Templates will be configured by main app
templates: Jinja2Templates | None = None


def set_templates(jinja_templates: Jinja2Templates):
    """Set Jinja2 templates instance."""
    global templates
    templates = jinja_templates


def get_db_client(request: Request) -> DynamoDBClient:
    """Get DynamoDB client from app state."""
    return request.app.state.db_client


class JobSummary(BaseModel):
    """Summary of a job for list view."""

    job_id: str
    manga_title: str
    status: str
    created_at: str
    updated_at: str
    youtube_url: str | None = None
    error_message: str | None = None
    progress_pct: int = 0


class QueueResponse(BaseModel):
    """Response for queue list endpoint."""

    jobs: list[JobSummary]
    total: int
    page: int
    page_size: int
    status_filter: str | None = None


@router.get("/queue", response_class=HTMLResponse)
async def queue_page(
    request: Request,
    username: str = Depends(get_current_user),
):
    """
    Render queue page.

    Args:
        request: FastAPI request.
        username: Authenticated username.

    Returns:
        HTML queue page.
    """
    if templates is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Templates not configured",
        )

    # Generate CSRF token for retry buttons
    csrf_token = request.app.state.csrf_manager.generate_token()

    return templates.TemplateResponse(
        "queue.html",
        {
            "request": request,
            "username": username,
            "csrf_token": csrf_token,
            "statuses": [status.value for status in JobStatus],
        },
    )


@router.get("/api/queue")
async def get_queue(
    status_filter: str | None = Query(None, description="Filter by job status"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    db_client: DynamoDBClient = Depends(get_db_client),
) -> QueueResponse:
    """
    Get list of jobs with optional filtering and pagination.

    Args:
        status_filter: Filter by job status (optional).
        page: Page number (1-indexed).
        page_size: Number of items per page.
        db_client: DynamoDB client.

    Returns:
        Paginated list of jobs.
    """
    try:
        # Validate status filter
        if status_filter:
            try:
                JobStatus(status_filter)
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid status: {status_filter}",
                )

        # Get jobs from DynamoDB
        all_jobs = db_client.list_jobs()

        # Filter by status if specified
        if status_filter:
            all_jobs = [job for job in all_jobs if job.status == status_filter]

        # Sort by created_at descending (newest first)
        all_jobs.sort(key=lambda j: j.created_at, reverse=True)

        # Calculate pagination
        total = len(all_jobs)
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        page_jobs = all_jobs[start_idx:end_idx]

        # Convert to summary format
        job_summaries = [
            JobSummary(
                job_id=job.job_id,
                manga_title=job.manga_title,
                status=job.status,
                created_at=job.created_at.isoformat(),
                updated_at=job.updated_at.isoformat(),
                youtube_url=job.youtube_url,
                error_message=job.error_message,
                progress_pct=job.progress_pct,
            )
            for job in page_jobs
        ]

        logger.debug(
            "Queue retrieved",
            extra={
                "total": total,
                "page": page,
                "page_size": page_size,
                "status_filter": status_filter,
            },
        )

        return QueueResponse(
            jobs=job_summaries,
            total=total,
            page=page,
            page_size=page_size,
            status_filter=status_filter,
        )

    except Exception as e:
        logger.error(
            "Failed to retrieve queue",
            extra={"error": str(e)},
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve queue: {str(e)}",
        )


@router.get("/api/queue/{job_id}")
async def get_job(
    job_id: str,
    db_client: DynamoDBClient = Depends(get_db_client),
):
    """
    Get detailed information about a specific job.

    Args:
        job_id: Job ID to retrieve.
        db_client: DynamoDB client.

    Returns:
        Job details including all fields.

    Raises:
        HTTPException: 404 if job not found.
    """
    try:
        job = db_client.get_job(job_id)

        if not job:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Job {job_id} not found",
            )

        logger.debug(
            "Job retrieved",
            extra={"job_id": job_id, "status": job.status},
        )

        return job.model_dump()

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Failed to retrieve job",
            extra={"job_id": job_id, "error": str(e)},
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve job: {str(e)}",
        )


@router.post("/api/queue/{job_id}/retry")
async def retry_job(
    request: Request,
    job_id: str,
    csrf_token: str = Form(...),
    username: str = Depends(get_current_user),
    db_client: DynamoDBClient = Depends(get_db_client),
):
    """
    Retry a failed job by triggering Step Functions execution.

    Args:
        request: FastAPI request.
        job_id: Job ID to retry.
        csrf_token: CSRF token from form.
        username: Authenticated username.
        db_client: DynamoDB client.

    Returns:
        JSON with success message and execution ARN.

    Raises:
        HTTPException: 403 if CSRF invalid, 404 if job not found,
                      400 if job not failed, 500 if retry fails.
    """
    # Verify CSRF token
    if not request.app.state.csrf_manager.verify_token(csrf_token):
        logger.warning(
            "Job retry failed: invalid CSRF token",
            extra={"username": username, "job_id": job_id},
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid CSRF token",
        )

    # Get job from database
    job = db_client.get_job(job_id)

    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job {job_id} not found",
        )

    # Check if job is in failed state
    if job.status != JobStatus.failed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Job {job_id} is not in failed state (current: {job.status})",
        )

    # Trigger Step Functions execution
    try:
        # Get state machine ARN from app state (includes region info)
        state_machine_arn = request.app.state.state_machine_arn

        # Extract region from state machine ARN
        # ARN format: arn:aws:states:REGION:ACCOUNT:stateMachine:NAME
        arn_parts = state_machine_arn.split(":")
        region = arn_parts[3] if len(arn_parts) > 3 else "us-east-1"

        sfn_client = boto3.client("stepfunctions", region_name=region)

        # Start execution
        response = sfn_client.start_execution(
            stateMachineArn=state_machine_arn,
            name=f"retry-{job_id}",
            input=f'{{"job_id": "{job_id}"}}',
        )

        execution_arn = response["executionArn"]

        # Update job status to pending
        db_client.update_job_status(
            job_id=job_id,
            status=JobStatus.pending,
            error_message=None,
        )

        logger.info(
            "Job retry triggered",
            extra={
                "username": username,
                "job_id": job_id,
                "execution_arn": execution_arn,
            },
        )

        return {
            "message": f"Job {job_id} retry initiated",
            "execution_arn": execution_arn,
        }

    except Exception as e:
        logger.error(
            "Failed to retry job",
            extra={"username": username, "job_id": job_id, "error": str(e)},
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retry job: {str(e)}",
        )
