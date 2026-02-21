"""Processed manga routes for admin dashboard."""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from src.common.db import DynamoDBClient
from src.common.logging_config import setup_logger
from src.dashboard.auth import get_current_user

logger = setup_logger(__name__)

router = APIRouter(tags=["Manga"], dependencies=[Depends(get_current_user)])

# Templates will be configured by main app
templates: Jinja2Templates | None = None


def set_templates(jinja_templates: Jinja2Templates):
    """Set Jinja2 templates instance."""
    global templates
    templates = jinja_templates


def get_db_client(request: Request) -> DynamoDBClient:
    """Get DynamoDB client from app state."""
    return request.app.state.db_client


class ProcessedMangaItem(BaseModel):
    """Processed manga item for API response."""

    manga_id: str
    title: str
    processed_at: str


class ProcessedMangaResponse(BaseModel):
    """Response for processed manga list endpoint."""

    items: list[ProcessedMangaItem]
    total: int


@router.get("/manga", response_class=HTMLResponse)
async def manga_page(
    request: Request,
    username: str = Depends(get_current_user),
):
    """
    Render processed manga page.

    Args:
        request: FastAPI request.
        username: Authenticated username.

    Returns:
        HTML manga page.
    """
    if templates is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Templates not configured",
        )

    return templates.TemplateResponse(
        "manga.html",
        {
            "request": request,
            "username": username,
        },
    )


@router.get("/api/processed-manga")
async def get_processed_manga(
    limit: int = Query(100, ge=1, le=500, description="Maximum items to return"),
    db_client: DynamoDBClient = Depends(get_db_client),
) -> ProcessedMangaResponse:
    """
    Get list of processed manga.

    Args:
        limit: Maximum number of items to return.
        db_client: DynamoDB client.

    Returns:
        List of processed manga with total count.
    """
    try:
        items = db_client.list_processed_manga(limit=limit)

        # Convert to response format
        processed_items = []
        for item in items:
            processed_items.append(
                ProcessedMangaItem(
                    manga_id=item.get("manga_id", ""),
                    title=item.get("title", "Unknown"),
                    processed_at=item.get("processed_at", ""),
                )
            )

        # Sort by processed_at descending
        processed_items.sort(key=lambda x: x.processed_at, reverse=True)

        logger.debug(
            "Processed manga retrieved",
            extra={"count": len(processed_items)},
        )

        return ProcessedMangaResponse(
            items=processed_items,
            total=len(processed_items),
        )

    except Exception as e:
        logger.error(
            "Failed to retrieve processed manga",
            extra={"error": str(e)},
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve processed manga: {str(e)}",
        )
