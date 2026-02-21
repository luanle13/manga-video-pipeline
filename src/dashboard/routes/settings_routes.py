"""Settings routes for admin dashboard."""

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field

from src.common.config import get_settings
from src.common.db import DynamoDBClient
from src.common.logging_config import setup_logger
from src.common.models import PipelineSettings
from src.dashboard.auth import get_current_user

logger = setup_logger(__name__)

router = APIRouter(tags=["Settings"], dependencies=[Depends(get_current_user)])

# Templates will be configured by main app
templates: Jinja2Templates | None = None


def set_templates(jinja_templates: Jinja2Templates):
    """Set Jinja2 templates instance."""
    global templates
    templates = jinja_templates


def get_db_client(request: Request) -> DynamoDBClient:
    """Get DynamoDB client from app state."""
    return request.app.state.db_client


# Vietnamese TTS voices for Edge TTS
VIETNAMESE_VOICES = [
    {
        "id": "vi-VN-HoaiMyNeural",
        "name": "HoaiMy (Female)",
        "gender": "Female",
        "locale": "vi-VN",
    },
    {
        "id": "vi-VN-NamMinhNeural",
        "name": "NamMinh (Male)",
        "gender": "Male",
        "locale": "vi-VN",
    },
]


class UpdateSettingsRequest(BaseModel):
    """Request model for updating settings."""

    daily_quota: int = Field(ge=1, le=10, description="Daily video quota (1-10)")
    voice_id: str = Field(description="Edge TTS voice ID")
    tone: str = Field(description="Narration tone")
    script_style: str = Field(description="Script generation style")
    manual_review_mode: bool = Field(
        default=False,
        description="Pause after rendering for manual review before upload",
    )
    csrf_token: str = Field(description="CSRF token for request validation")


@router.get("/settings", response_class=HTMLResponse)
async def settings_page(
    request: Request,
    username: str = Depends(get_current_user),
):
    """
    Render settings page with current values.

    Args:
        request: FastAPI request.
        username: Authenticated username.

    Returns:
        HTML settings page.
    """
    if templates is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Templates not configured",
        )

    # Get current settings from DynamoDB
    db_client = get_db_client(request)

    try:
        current_settings = db_client.get_settings()
    except Exception as e:
        logger.error(
            "Failed to load settings",
            extra={"error": str(e)},
        )
        # Use default settings
        current_settings = PipelineSettings()

    # Generate CSRF token
    csrf_token = request.app.state.csrf_manager.generate_token()

    return templates.TemplateResponse(
        "settings.html",
        {
            "request": request,
            "username": username,
            "settings": current_settings,
            "voices": VIETNAMESE_VOICES,
            "csrf_token": csrf_token,
        },
    )


@router.get("/api/voices")
async def get_voices():
    """
    Get list of available Vietnamese TTS voices.

    Returns:
        List of voice objects with id, name, gender, locale.
    """
    return {"voices": VIETNAMESE_VOICES}


@router.put("/api/settings")
async def update_settings(
    request: Request,
    settings_update: UpdateSettingsRequest,
    username: str = Depends(get_current_user),
    db_client: DynamoDBClient = Depends(get_db_client),
):
    """
    Update pipeline settings in DynamoDB.

    Args:
        request: FastAPI request.
        settings_update: New settings values (includes CSRF token).
        username: Authenticated username.
        db_client: DynamoDB client.

    Returns:
        JSON with success message and updated settings.

    Raises:
        HTTPException: 403 if CSRF invalid, 500 if update fails.
    """
    # Verify CSRF token
    if not request.app.state.csrf_manager.verify_token(settings_update.csrf_token):
        logger.warning(
            "Settings update failed: invalid CSRF token",
            extra={"username": username},
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid CSRF token",
        )

    # Validate voice ID
    valid_voice_ids = [v["id"] for v in VIETNAMESE_VOICES]
    if settings_update.voice_id not in valid_voice_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid voice_id. Must be one of: {valid_voice_ids}",
        )

    # Validate script style
    valid_styles = ["detailed_review", "summary", "chapter_walkthrough"]
    if settings_update.script_style not in valid_styles:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid script_style. Must be one of: {valid_styles}",
        )

    # Create PipelineSettings object
    new_settings = PipelineSettings(
        daily_quota=settings_update.daily_quota,
        voice_id=settings_update.voice_id,
        tone=settings_update.tone,
        script_style=settings_update.script_style,
        manual_review_mode=settings_update.manual_review_mode,
    )

    # Update in DynamoDB
    try:
        db_client.update_settings(new_settings)

        logger.info(
            "Settings updated successfully",
            extra={
                "username": username,
                "daily_quota": new_settings.daily_quota,
                "voice_id": new_settings.voice_id,
            },
        )

        return {
            "message": "Settings updated successfully",
            "settings": new_settings.model_dump(),
        }

    except Exception as e:
        logger.error(
            "Failed to update settings",
            extra={"username": username, "error": str(e)},
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update settings: {str(e)}",
        )
