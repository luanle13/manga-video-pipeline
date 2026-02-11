"""Authentication routes for admin dashboard."""

import os

from fastapi import APIRouter, Depends, Form, HTTPException, Request, Response, status
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates

from src.common.logging_config import setup_logger
from src.common.secrets import SecretsClient, SecretNotFoundError
from src.dashboard.auth import (
    clear_auth_cookie,
    create_access_token,
    set_auth_cookie,
    verify_password,
)

logger = setup_logger(__name__)

router = APIRouter(tags=["Authentication"])

# Templates will be configured by main app
templates: Jinja2Templates | None = None

# Default admin credentials for local development
# In production, these should be stored in AWS Secrets Manager
DEFAULT_ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "admin")
DEFAULT_ADMIN_PASSWORD_HASH = os.environ.get(
    "ADMIN_PASSWORD_HASH",
    # bcrypt hash for "Luan@130201"
    "$2b$12$8LjdzKzMSOkU0S/BWYL9uOaASFgTV3hZcNnGSHw9Ec68WUYLA29Ja",
)


def set_templates(jinja_templates: Jinja2Templates):
    """Set Jinja2 templates instance."""
    global templates
    templates = jinja_templates


def get_admin_credentials(request: Request) -> dict:
    """
    Get admin credentials from Secrets Manager or environment fallback.

    Returns:
        Dict with 'username' and 'password_hash' keys.
    """
    # Get secrets client from app state (set during startup)
    secrets_client: SecretsClient = request.app.state.secrets_client

    # Get admin credentials from Secrets Manager
    secret_name = request.app.state.admin_secret_name

    try:
        credentials = secrets_client.get_secret_json(secret_name)
        return {
            "username": credentials.get("username", "admin"),
            "password_hash": credentials.get("password_hash", ""),
        }
    except (SecretNotFoundError, Exception) as e:
        # Fallback to environment variables for local development
        logger.warning(
            "Could not retrieve admin credentials from Secrets Manager, using fallback",
            extra={"error": str(e)},
        )
        return {
            "username": DEFAULT_ADMIN_USERNAME,
            "password_hash": DEFAULT_ADMIN_PASSWORD_HASH,
        }


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    """
    Render login page.

    Returns:
        HTML login page with CSRF token.
    """
    if templates is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Templates not configured",
        )

    # Generate CSRF token
    csrf_token = request.app.state.csrf_manager.generate_token()

    return templates.TemplateResponse(
        "login.html",
        {
            "request": request,
            "csrf_token": csrf_token,
        },
    )


@router.post("/api/auth/login")
async def login(
    request: Request,
    response: Response,
    username: str = Form(...),
    password: str = Form(...),
    csrf_token: str = Form(...),
    credentials: dict = Depends(get_admin_credentials),
):
    """
    Authenticate user and set auth cookie.

    Args:
        request: FastAPI request.
        response: FastAPI response.
        username: Username from form.
        password: Password from form.
        csrf_token: CSRF token from form.
        credentials: Admin credentials from Secrets Manager.

    Returns:
        JSON with success message and redirect URL.

    Raises:
        HTTPException: 401 if credentials invalid, 403 if CSRF invalid.
    """
    # Verify CSRF token
    if not request.app.state.csrf_manager.verify_token(csrf_token):
        logger.warning(
            "Login failed: invalid CSRF token",
            extra={"username": username},
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid CSRF token",
        )

    # Verify credentials
    expected_username = credentials.get("username", "admin")
    password_hash = credentials.get("password_hash")

    if not password_hash:
        logger.error("Admin password hash not configured")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Authentication configuration error",
        )

    if username != expected_username or not verify_password(password, password_hash):
        logger.warning(
            "Login failed: invalid credentials",
            extra={"username": username},
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )

    # Create JWT token
    jwt_secret = request.app.state.jwt_secret_key
    token = create_access_token(
        username=username,
        secret_key=jwt_secret,
        expires_hours=24,
    )

    # Set httpOnly cookie
    set_auth_cookie(
        response,
        token,
        max_age=86400,  # 24 hours
        secure=request.app.state.secure_cookies,
    )

    logger.info(
        "User logged in successfully",
        extra={"username": username},
    )

    return {
        "message": "Login successful",
        "redirect": "/",
    }


@router.post("/api/auth/logout")
async def logout(response: Response):
    """
    Clear auth cookie and log out user.

    Args:
        response: FastAPI response.

    Returns:
        JSON with success message and redirect URL.
    """
    clear_auth_cookie(response)

    logger.info("User logged out")

    return {
        "message": "Logged out successfully",
        "redirect": "/login",
    }
