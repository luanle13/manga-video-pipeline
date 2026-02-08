"""Processed manga routes for admin dashboard."""

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from src.dashboard.auth import get_current_user

router = APIRouter(tags=["Manga"], dependencies=[Depends(get_current_user)])

# Templates will be configured by main app
templates: Jinja2Templates | None = None


def set_templates(jinja_templates: Jinja2Templates):
    """Set Jinja2 templates instance."""
    global templates
    templates = jinja_templates


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
