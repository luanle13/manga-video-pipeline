"""FastAPI application for manga video pipeline admin dashboard."""

import os
import secrets
from pathlib import Path

import boto3
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from src.common.config import get_settings
from src.common.db import DynamoDBClient
from src.common.logging_config import setup_logger
from src.common.secrets import SecretsClient
from src.dashboard.auth import AuthMiddleware
from src.dashboard.csrf import CSRFManager
from src.dashboard.routes import (
    auth_routes,
    manga_routes,
    queue_routes,
    review_routes,
    settings_routes,
    stats_routes,
)

logger = setup_logger(__name__)


def create_app(
    jwt_secret_key: str | None = None,
    admin_secret_name: str = "manga-pipeline/admin-credentials",
    state_machine_arn: str | None = None,
    secure_cookies: bool = True,
) -> FastAPI:
    """
    Create and configure FastAPI application.

    Args:
        jwt_secret_key: Secret key for JWT signing. If None, generates random key.
        admin_secret_name: Name of secret in Secrets Manager with admin credentials.
        state_machine_arn: ARN of Step Functions state machine for job retries.
        secure_cookies: Whether to use secure (HTTPS-only) cookies.

    Returns:
        Configured FastAPI application.
    """
    # Create FastAPI app
    app = FastAPI(
        title="Manga Video Pipeline Admin",
        description="Admin dashboard for managing manga-to-video pipeline",
        version="1.0.0",
        docs_url="/api/docs",
        redoc_url="/api/redoc",
    )

    # Load settings
    settings = get_settings()

    # Initialize services
    db_client = DynamoDBClient(settings)
    secrets_client = SecretsClient(region=settings.aws_region)

    # Generate or use provided JWT secret
    if jwt_secret_key is None:
        jwt_secret_key = secrets.token_hex(32)
        logger.warning(
            "Using generated JWT secret key. "
            "For production, provide a persistent secret key from Secrets Manager."
        )

    # Initialize CSRF manager
    csrf_manager = CSRFManager(token_lifetime_minutes=60)

    # Store dependencies in app state
    app.state.db_client = db_client
    app.state.secrets_client = secrets_client
    app.state.jwt_secret_key = jwt_secret_key
    app.state.admin_secret_name = admin_secret_name
    app.state.csrf_manager = csrf_manager
    app.state.secure_cookies = secure_cookies
    # Get state machine ARN - either from parameter, env var, or construct dynamically
    if state_machine_arn:
        app.state.state_machine_arn = state_machine_arn
    elif os.environ.get("STATE_MACHINE_ARN"):
        app.state.state_machine_arn = os.environ["STATE_MACHINE_ARN"]
    else:
        # Get account ID dynamically
        try:
            sts_client = boto3.client("sts", region_name=settings.aws_region)
            account_id = sts_client.get_caller_identity()["Account"]
            app.state.state_machine_arn = f"arn:aws:states:{settings.aws_region}:{account_id}:stateMachine:manga-video-pipeline-pipeline"
        except Exception as e:
            logger.warning(f"Could not get account ID: {e}. Using placeholder.")
            app.state.state_machine_arn = f"arn:aws:states:{settings.aws_region}:000000000000:stateMachine:manga-video-pipeline-pipeline"

    # Set up Jinja2 templates
    templates_dir = Path(__file__).parent / "templates"
    templates_dir.mkdir(exist_ok=True)
    templates = Jinja2Templates(directory=str(templates_dir))

    # Configure templates for route modules
    auth_routes.set_templates(templates)
    settings_routes.set_templates(templates)
    queue_routes.set_templates(templates)
    stats_routes.set_templates(templates)
    manga_routes.set_templates(templates)
    review_routes.set_templates(templates)

    # Mount static files
    static_dir = Path(__file__).parent / "static"
    static_dir.mkdir(exist_ok=True)
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    # Add authentication middleware (must be after routes are defined)
    # Note: Middleware is applied in reverse order, so this should be last
    app.add_middleware(
        AuthMiddleware,
        secret_key=jwt_secret_key,
        excluded_paths={"/login", "/api/auth/login", "/static"},
    )

    # Include routers
    app.include_router(auth_routes.router)
    app.include_router(stats_routes.router)
    app.include_router(settings_routes.router)
    app.include_router(queue_routes.router)
    app.include_router(manga_routes.router)
    app.include_router(review_routes.router)

    logger.info(
        "FastAPI application created",
        extra={
            "secure_cookies": secure_cookies,
            "admin_secret_name": admin_secret_name,
        },
    )

    return app


# Create app instance for running with uvicorn
# In production, load secrets from Secrets Manager
# Skip app creation during test collection (when env vars not available)
try:
    app = create_app()
except Exception:
    # During test imports, settings may not be available
    # Tests will create their own app instances
    app = None  # type: ignore


if __name__ == "__main__":
    import uvicorn

    # Run development server
    uvicorn.run(
        "src.dashboard.app:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info",
    )
