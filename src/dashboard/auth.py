"""Authentication module for admin dashboard.

Provides JWT-based authentication with httpOnly cookies for secure session management.
"""

from datetime import datetime, timedelta, timezone
from typing import Callable

import bcrypt
from fastapi import HTTPException, Request, status
from jose import JWTError, jwt
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import RedirectResponse

from src.common.logging_config import setup_logger

logger = setup_logger(__name__)

# JWT algorithm
ALGORITHM = "HS256"

# Cookie name for access token
COOKIE_NAME = "access_token"

# Paths that don't require authentication
EXCLUDED_PATHS = {"/login", "/api/auth/login", "/static"}


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a plain password against a bcrypt hash.

    Args:
        plain_password: The plain text password to verify.
        hashed_password: The bcrypt hashed password to compare against.

    Returns:
        True if password matches, False otherwise.
    """
    try:
        # Convert strings to bytes for bcrypt
        plain_bytes = plain_password.encode("utf-8")
        hashed_bytes = hashed_password.encode("utf-8")

        # Verify password using bcrypt
        result = bcrypt.checkpw(plain_bytes, hashed_bytes)

        logger.debug(
            "Password verification completed",
            extra={"result": result},
        )

        return result

    except Exception as e:
        logger.warning(
            "Password verification failed",
            extra={"error": str(e)},
        )
        return False


def hash_password(plain_password: str) -> str:
    """
    Hash a password using bcrypt.

    Args:
        plain_password: The plain text password to hash.

    Returns:
        The bcrypt hashed password as a string.
    """
    # Generate salt and hash password
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(plain_password.encode("utf-8"), salt)

    # Convert bytes to string for storage
    return hashed.decode("utf-8")


def create_access_token(username: str, secret_key: str, expires_hours: int = 24) -> str:
    """
    Create a JWT access token.

    Args:
        username: The username to encode in the token.
        secret_key: Secret key for signing the token.
        expires_hours: Number of hours until token expires (default: 24).

    Returns:
        Encoded JWT token as string.
    """
    # Calculate expiration time
    expire = datetime.now(timezone.utc) + timedelta(hours=expires_hours)

    # Create JWT payload
    payload = {
        "sub": username,  # Subject (username)
        "exp": expire,  # Expiration time
        "iat": datetime.now(timezone.utc),  # Issued at
    }

    # Encode and sign JWT
    token = jwt.encode(payload, secret_key, algorithm=ALGORITHM)

    logger.info(
        "Access token created",
        extra={
            "username": username,
            "expires_hours": expires_hours,
        },
    )

    return token


def verify_token(token: str, secret_key: str) -> str | None:
    """
    Verify and decode a JWT token.

    Args:
        token: The JWT token to verify.
        secret_key: Secret key used to sign the token.

    Returns:
        Username from token if valid, None if expired or invalid.
    """
    try:
        # Decode and verify JWT
        payload = jwt.decode(token, secret_key, algorithms=[ALGORITHM])

        # Extract username from subject claim
        username: str | None = payload.get("sub")

        if username is None:
            logger.warning("Token missing 'sub' claim")
            return None

        logger.debug(
            "Token verified successfully",
            extra={"username": username},
        )

        return username

    except JWTError as e:
        logger.warning(
            "Token verification failed",
            extra={"error": str(e), "error_type": type(e).__name__},
        )
        return None


def get_current_user(request: Request) -> str:
    """
    FastAPI dependency to get current authenticated user.

    Extracts and verifies JWT token from httpOnly cookie.

    Args:
        request: FastAPI/Starlette request object.

    Returns:
        Username of authenticated user.

    Raises:
        HTTPException: 401 if token is missing or invalid.
    """
    # Get token from cookie
    token = request.cookies.get(COOKIE_NAME)

    if not token:
        logger.warning(
            "Authentication failed: missing token cookie",
            extra={"path": request.url.path},
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Get secret key from request state (should be set by app)
    secret_key = getattr(request.app.state, "jwt_secret_key", None)

    if not secret_key:
        logger.error("JWT secret key not configured in app state")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Authentication configuration error",
        )

    # Verify token
    username = verify_token(token, secret_key)

    if username is None:
        logger.warning(
            "Authentication failed: invalid token",
            extra={"path": request.url.path},
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    logger.debug(
        "User authenticated via token",
        extra={"username": username, "path": request.url.path},
    )

    return username


class AuthMiddleware(BaseHTTPMiddleware):
    """
    Middleware for checking authentication on all requests.

    Verifies JWT token from httpOnly cookie and redirects to /login
    if missing or invalid. Excludes certain public paths.
    """

    def __init__(self, app, secret_key: str, excluded_paths: set[str] | None = None):
        """
        Initialize authentication middleware.

        Args:
            app: ASGI application.
            secret_key: Secret key for JWT verification.
            excluded_paths: Set of paths that don't require authentication.
                          Defaults to {"/login", "/api/auth/login", "/static"}.
        """
        super().__init__(app)
        self.secret_key = secret_key
        self.excluded_paths = excluded_paths or EXCLUDED_PATHS

        logger.info(
            "AuthMiddleware initialized",
            extra={"excluded_paths": list(self.excluded_paths)},
        )

    async def dispatch(self, request: Request, call_next: Callable):
        """
        Process request and verify authentication.

        Args:
            request: Incoming request.
            call_next: Next middleware/handler in chain.

        Returns:
            Response from next handler or redirect to /login.
        """
        path = request.url.path

        # Check if path should be excluded from authentication
        if self._is_excluded(path):
            logger.debug(
                "Path excluded from authentication",
                extra={"path": path},
            )
            return await call_next(request)

        # Get token from cookie
        token = request.cookies.get(COOKIE_NAME)

        if not token:
            logger.warning(
                "Unauthenticated request: missing token",
                extra={"path": path, "method": request.method},
            )
            return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)

        # Verify token
        username = verify_token(token, self.secret_key)

        if username is None:
            logger.warning(
                "Unauthenticated request: invalid token",
                extra={"path": path, "method": request.method},
            )
            return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)

        # Add username to request state for access in handlers
        request.state.username = username

        logger.debug(
            "Request authenticated",
            extra={"username": username, "path": path, "method": request.method},
        )

        # Continue to next handler
        return await call_next(request)

    def _is_excluded(self, path: str) -> bool:
        """
        Check if a path should be excluded from authentication.

        Args:
            path: Request path to check.

        Returns:
            True if path is excluded, False otherwise.
        """
        # Check exact match
        if path in self.excluded_paths:
            return True

        # Check if path starts with any excluded path (for static files, etc.)
        for excluded_path in self.excluded_paths:
            if path.startswith(excluded_path + "/") or path.startswith(excluded_path):
                return True

        return False


def set_auth_cookie(
    response,
    token: str,
    max_age: int = 86400,  # 24 hours in seconds
    secure: bool = True,
) -> None:
    """
    Set authentication cookie on response.

    Args:
        response: FastAPI/Starlette response object.
        token: JWT token to set in cookie.
        max_age: Cookie max age in seconds (default: 24 hours).
        secure: Whether to set secure flag (default: True).
                Set to False for local development over HTTP.
    """
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        max_age=max_age,
        httponly=True,  # Prevent JavaScript access (XSS protection)
        secure=secure,  # Only send over HTTPS (set False for local dev)
        samesite="strict",  # CSRF protection
        path="/",  # Cookie valid for entire site
    )

    logger.info(
        "Auth cookie set",
        extra={
            "max_age": max_age,
            "secure": secure,
        },
    )


def clear_auth_cookie(response) -> None:
    """
    Clear authentication cookie from response.

    Args:
        response: FastAPI/Starlette response object.
    """
    response.delete_cookie(
        key=COOKIE_NAME,
        path="/",
        httponly=True,
        secure=True,
        samesite="strict",
    )

    logger.info("Auth cookie cleared")
