"""Review video generation routes."""

import asyncio
import uuid
from datetime import datetime

import boto3
from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from src.common.config import get_settings
from src.common.db import DynamoDBClient
from src.common.logging_config import setup_logger
from src.common.models import JobRecord, JobStatus, JobType, MangaSource
from src.dashboard.auth import get_current_user
from src.review_fetcher.scraper_factory import (
    detect_source_from_url,
    get_all_scrapers,
    get_scraper_for_url,
    is_supported_url,
)

logger = setup_logger(__name__)

router = APIRouter(tags=["Review"], dependencies=[Depends(get_current_user)])

# Templates will be configured by main app
templates: Jinja2Templates | None = None


def set_templates(jinja_templates: Jinja2Templates):
    """Set Jinja2 templates instance."""
    global templates
    templates = jinja_templates


def get_db_client(request: Request) -> DynamoDBClient:
    """Get DynamoDB client from app state."""
    return request.app.state.db_client


class SearchRequest(BaseModel):
    """Search request model."""

    query: str
    source: str | None = None


class SearchResultItem(BaseModel):
    """Search result item model."""

    title: str
    url: str
    cover_url: str | None = None
    source: str
    chapter_count: int | None = None


class CreateReviewRequest(BaseModel):
    """Create review job request model."""

    manga_url: str | None = None
    manga_name: str | None = None
    source: str | None = None


@router.get("/review", response_class=HTMLResponse)
async def review_page(
    request: Request,
    username: str = Depends(get_current_user),
):
    """
    Render review video creation page.

    Args:
        request: FastAPI request.
        username: Authenticated username.

    Returns:
        HTML review creation page.
    """
    if templates is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Templates not configured",
        )

    # Generate CSRF token
    csrf_token = request.app.state.csrf_manager.generate_token()

    # Get available sources
    sources = [
        {"value": "truyenqq", "label": "TruyenQQ"},
        {"value": "nettruyen", "label": "NetTruyen"},
        {"value": "truyentranhlh", "label": "TruyenTranhLH"},
    ]

    return templates.TemplateResponse(
        "review.html",
        {
            "request": request,
            "username": username,
            "csrf_token": csrf_token,
            "sources": sources,
        },
    )


@router.post("/api/review/search")
async def search_manga(
    request: Request,
    data: SearchRequest,
    username: str = Depends(get_current_user),
) -> list[SearchResultItem]:
    """
    Search for manga across supported sites.

    Args:
        request: FastAPI request.
        data: Search request with query and optional source.
        username: Authenticated username.

    Returns:
        List of search results.
    """
    query = data.query.strip()
    if not query:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Search query is required",
        )

    logger.info(
        "Searching for manga",
        extra={"query": query, "source": data.source, "username": username},
    )

    try:
        results: list[SearchResultItem] = []

        # Get scrapers to use
        if data.source:
            try:
                source_enum = MangaSource(data.source)
                from src.review_fetcher.scraper_factory import get_scraper_for_source

                scrapers = [get_scraper_for_source(source_enum)]
            except ValueError:
                scrapers = get_all_scrapers()
        else:
            scrapers = get_all_scrapers()

        # Search across scrapers
        async def search_scraper(scraper):
            """Search a single scraper."""
            try:
                async with scraper:
                    return await scraper.search(query)
            except Exception as e:
                logger.warning(
                    "Search failed for scraper",
                    extra={"source": scraper.SOURCE, "error": str(e)},
                )
                return []

        # Run searches in parallel
        all_results = await asyncio.gather(*[search_scraper(s) for s in scrapers])

        # Flatten and convert results
        for scraper_results in all_results:
            for result in scraper_results:
                results.append(
                    SearchResultItem(
                        title=result.title,
                        url=result.url,
                        cover_url=result.cover_url,
                        source=result.source.value,
                        chapter_count=result.chapter_count,
                    )
                )

        # Limit results
        return results[:20]

    except Exception as e:
        logger.error(
            "Search failed",
            extra={"query": query, "error": str(e)},
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Search failed: {str(e)}",
        )


@router.post("/api/review/create")
async def create_review(
    request: Request,
    csrf_token: str = Form(...),
    manga_url: str = Form(None),
    manga_name: str = Form(None),
    source: str = Form(None),
    username: str = Depends(get_current_user),
):
    """
    Create a new review video job.

    Args:
        request: FastAPI request.
        csrf_token: CSRF token from form.
        manga_url: Direct URL to manga page.
        manga_name: Manga name to search.
        source: Optional source hint.
        username: Authenticated username.

    Returns:
        JSON with job_id and status.
    """
    # Verify CSRF token
    if not request.app.state.csrf_manager.verify_token(csrf_token):
        logger.warning(
            "Review create failed: invalid CSRF token",
            extra={"username": username},
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid CSRF token",
        )

    # Validate input
    if not manga_url and not manga_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Either manga URL or manga name is required",
        )

    # If URL provided, validate it
    if manga_url and not is_supported_url(manga_url):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported manga URL. Supported sites: TruyenQQ, NetTruyen, TruyenTranhLH",
        )

    try:
        settings = get_settings()
        db_client = get_db_client(request)

        # Create job record
        job_id = str(uuid.uuid4())

        # Detect source from URL if provided
        detected_source = None
        if manga_url:
            try:
                detected_source = detect_source_from_url(manga_url)
            except ValueError:
                pass

        job_record = JobRecord(
            job_id=job_id,
            manga_id="",  # Will be updated by fetcher
            manga_title=manga_name or manga_url or "",
            job_type=JobType.review_video,
            source=detected_source or MangaSource.truyenqq,
            source_url=manga_url,
            status=JobStatus.pending,
        )
        db_client.create_job(job_record)

        logger.info(
            "Review job created",
            extra={
                "job_id": job_id,
                "manga_url": manga_url,
                "manga_name": manga_name,
                "username": username,
            },
        )

        # Get review state machine ARN
        review_state_machine_arn = request.app.state.state_machine_arn.replace(
            "-pipeline", "-review-pipeline"
        )

        # Create Step Functions client
        sfn_client = boto3.client("stepfunctions", region_name=settings.aws_region)

        # Generate unique execution name
        execution_name = f"review-{uuid.uuid4().hex[:8]}-{datetime.now().strftime('%Y%m%d-%H%M%S')}"

        # Start execution
        try:
            import json

            input_data = {
                "job_id": job_id,
                "manga_url": manga_url,
                "manga_name": manga_name,
                "source": source,
                "single_video_mode": True,
            }

            response = sfn_client.start_execution(
                stateMachineArn=review_state_machine_arn,
                name=execution_name,
                input=json.dumps(input_data),
            )

            execution_arn = response["executionArn"]

            logger.info(
                "Review pipeline triggered",
                extra={
                    "job_id": job_id,
                    "execution_arn": execution_arn,
                },
            )

        except sfn_client.exceptions.StateMachineDoesNotExist:
            # Review state machine not deployed yet - just log and continue
            logger.warning(
                "Review state machine not found - job created but not started",
                extra={"job_id": job_id},
            )
            execution_arn = None

        return {
            "message": "Review job created successfully",
            "job_id": job_id,
            "execution_arn": execution_arn if "execution_arn" in dir() else None,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Failed to create review job",
            extra={"username": username, "error": str(e)},
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create review job: {str(e)}",
        )


@router.post("/api/review/validate-url")
async def validate_url(
    request: Request,
    url: str = Form(...),
    username: str = Depends(get_current_user),
):
    """
    Validate if a URL is from a supported manga site.

    Args:
        request: FastAPI request.
        url: URL to validate.
        username: Authenticated username.

    Returns:
        JSON with validation result.
    """
    try:
        is_valid = is_supported_url(url)
        source = None

        if is_valid:
            try:
                source = detect_source_from_url(url).value
            except ValueError:
                pass

        return {
            "valid": is_valid,
            "source": source,
        }
    except Exception as e:
        return {
            "valid": False,
            "error": str(e),
        }
