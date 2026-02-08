"""Unit tests for dashboard authentication module."""

import time
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException, Request
from starlette.applications import Starlette
from starlette.responses import Response
from starlette.testclient import TestClient

from src.dashboard.auth import (
    COOKIE_NAME,
    AuthMiddleware,
    clear_auth_cookie,
    create_access_token,
    get_current_user,
    hash_password,
    set_auth_cookie,
    verify_password,
    verify_token,
)


@pytest.fixture
def secret_key():
    """Secret key for testing."""
    return "test-secret-key-do-not-use-in-production-please-use-random-32-bytes"


@pytest.fixture
def test_username():
    """Test username."""
    return "admin"


@pytest.fixture
def test_password():
    """Test plain password."""
    return "secure-password-123"


@pytest.fixture
def hashed_password():
    """Pre-hashed test password."""
    # Hash of "secure-password-123"
    return hash_password("secure-password-123")


# =====================================================================
# Password Verification Tests
# =====================================================================


def test_verify_password_correct(test_password, hashed_password):
    """Test password verification with correct password."""
    result = verify_password(test_password, hashed_password)
    assert result is True


def test_verify_password_incorrect(hashed_password):
    """Test password verification with incorrect password."""
    result = verify_password("wrong-password", hashed_password)
    assert result is False


def test_verify_password_empty_password(hashed_password):
    """Test password verification with empty password."""
    result = verify_password("", hashed_password)
    assert result is False


def test_verify_password_invalid_hash(test_password):
    """Test password verification with invalid hash format."""
    result = verify_password(test_password, "not-a-valid-bcrypt-hash")
    assert result is False


def test_hash_password_creates_valid_hash(test_password):
    """Test that hash_password creates a valid bcrypt hash."""
    hashed = hash_password(test_password)

    # Verify it's a valid hash by checking it against the original
    assert verify_password(test_password, hashed)
    assert len(hashed) > 50  # bcrypt hashes are typically 60 chars


def test_hash_password_different_each_time(test_password):
    """Test that hash_password produces different hashes (salt is random)."""
    hash1 = hash_password(test_password)
    hash2 = hash_password(test_password)

    # Hashes should be different due to random salt
    assert hash1 != hash2

    # But both should verify correctly
    assert verify_password(test_password, hash1)
    assert verify_password(test_password, hash2)


# =====================================================================
# JWT Token Tests
# =====================================================================


def test_create_access_token(test_username, secret_key):
    """Test creating a JWT access token."""
    token = create_access_token(test_username, secret_key, expires_hours=1)

    assert token is not None
    assert isinstance(token, str)
    assert len(token) > 0


def test_verify_token_valid(test_username, secret_key):
    """Test verifying a valid JWT token."""
    token = create_access_token(test_username, secret_key, expires_hours=1)
    username = verify_token(token, secret_key)

    assert username == test_username


def test_verify_token_round_trip(test_username, secret_key):
    """Test create and verify token round-trip."""
    # Create token
    token = create_access_token(test_username, secret_key, expires_hours=24)

    # Verify token
    username = verify_token(token, secret_key)

    # Should get back original username
    assert username == test_username


def test_verify_token_expired(test_username, secret_key):
    """Test that expired token returns None."""
    # Create token that expires in 0 hours (already expired)
    # We need to manually create an expired token
    from jose import jwt

    expire = datetime.now(timezone.utc) - timedelta(hours=1)  # 1 hour ago
    payload = {
        "sub": test_username,
        "exp": expire,
        "iat": datetime.now(timezone.utc),
    }

    expired_token = jwt.encode(payload, secret_key, algorithm="HS256")

    # Verify should return None
    username = verify_token(expired_token, secret_key)
    assert username is None


def test_verify_token_invalid_signature(test_username, secret_key):
    """Test that token with invalid signature returns None."""
    token = create_access_token(test_username, secret_key, expires_hours=1)

    # Try to verify with wrong secret key
    username = verify_token(token, "wrong-secret-key")
    assert username is None


def test_verify_token_malformed(secret_key):
    """Test that malformed token returns None."""
    username = verify_token("not.a.valid.jwt.token", secret_key)
    assert username is None


def test_verify_token_missing_sub(secret_key):
    """Test that token missing 'sub' claim returns None."""
    from jose import jwt

    # Create token without 'sub' claim
    payload = {
        "exp": datetime.now(timezone.utc) + timedelta(hours=1),
        "iat": datetime.now(timezone.utc),
    }
    token = jwt.encode(payload, secret_key, algorithm="HS256")

    username = verify_token(token, secret_key)
    assert username is None


# =====================================================================
# get_current_user Tests
# =====================================================================


def test_get_current_user_valid_token(test_username, secret_key):
    """Test get_current_user with valid token in cookie."""
    # Create token
    token = create_access_token(test_username, secret_key, expires_hours=1)

    # Create mock request with token in cookie
    request = MagicMock(spec=Request)
    request.cookies = {COOKIE_NAME: token}
    request.url.path = "/dashboard"

    # Mock app state with secret key
    request.app.state.jwt_secret_key = secret_key

    # Get current user
    username = get_current_user(request)
    assert username == test_username


def test_get_current_user_missing_token(secret_key):
    """Test get_current_user raises 401 when token is missing."""
    # Create mock request without token
    request = MagicMock(spec=Request)
    request.cookies = {}
    request.url.path = "/dashboard"
    request.app.state.jwt_secret_key = secret_key

    # Should raise HTTPException with 401
    with pytest.raises(HTTPException) as exc_info:
        get_current_user(request)

    assert exc_info.value.status_code == 401
    assert "Not authenticated" in str(exc_info.value.detail)


def test_get_current_user_invalid_token(secret_key):
    """Test get_current_user raises 401 when token is invalid."""
    # Create mock request with invalid token
    request = MagicMock(spec=Request)
    request.cookies = {COOKIE_NAME: "invalid.token.here"}
    request.url.path = "/dashboard"
    request.app.state.jwt_secret_key = secret_key

    # Should raise HTTPException with 401
    with pytest.raises(HTTPException) as exc_info:
        get_current_user(request)

    assert exc_info.value.status_code == 401
    assert "Invalid or expired token" in str(exc_info.value.detail)


def test_get_current_user_missing_secret_key(test_username, secret_key):
    """Test get_current_user raises 500 when secret key not configured."""
    token = create_access_token(test_username, secret_key, expires_hours=1)

    # Create mock request without secret key in app state
    request = MagicMock(spec=Request)
    request.cookies = {COOKIE_NAME: token}
    request.url.path = "/dashboard"
    request.app.state.jwt_secret_key = None

    # Should raise HTTPException with 500
    with pytest.raises(HTTPException) as exc_info:
        get_current_user(request)

    assert exc_info.value.status_code == 500
    assert "configuration error" in str(exc_info.value.detail).lower()


# =====================================================================
# AuthMiddleware Tests
# =====================================================================


@pytest.fixture
def test_app(secret_key):
    """Create test Starlette app with AuthMiddleware."""
    app = Starlette()

    # Add middleware
    app.add_middleware(AuthMiddleware, secret_key=secret_key)

    # Add test routes
    @app.route("/")
    async def index(request):
        return Response("Home page", media_type="text/plain")

    @app.route("/dashboard")
    async def dashboard(request):
        username = getattr(request.state, "username", "unknown")
        return Response(f"Dashboard for {username}", media_type="text/plain")

    @app.route("/login")
    async def login(request):
        return Response("Login page", media_type="text/plain")

    @app.route("/api/auth/login")
    async def api_login(request):
        return Response("API login", media_type="text/plain")

    return app


def test_middleware_redirects_unauthenticated_requests(test_app):
    """Test that middleware redirects requests without token to /login."""
    client = TestClient(test_app)

    # Request without token should redirect
    response = client.get("/dashboard", follow_redirects=False)

    assert response.status_code == 302
    assert response.headers["location"] == "/login"


def test_middleware_allows_authenticated_requests(test_app, test_username, secret_key):
    """Test that middleware allows requests with valid token."""
    client = TestClient(test_app)

    # Create valid token
    token = create_access_token(test_username, secret_key, expires_hours=1)

    # Request with valid token should succeed
    response = client.get("/dashboard", cookies={COOKIE_NAME: token})

    assert response.status_code == 200
    assert test_username in response.text


def test_middleware_excludes_login_path(test_app):
    """Test that middleware excludes /login path."""
    client = TestClient(test_app)

    # Request to /login without token should succeed
    response = client.get("/login")

    assert response.status_code == 200
    assert "Login page" in response.text


def test_middleware_excludes_api_auth_login_path(test_app):
    """Test that middleware excludes /api/auth/login path."""
    client = TestClient(test_app)

    # Request to /api/auth/login without token should succeed
    response = client.get("/api/auth/login")

    assert response.status_code == 200
    assert "API login" in response.text


def test_middleware_redirects_on_invalid_token(test_app):
    """Test that middleware redirects requests with invalid token."""
    client = TestClient(test_app)

    # Request with invalid token should redirect
    response = client.get("/dashboard", cookies={COOKIE_NAME: "invalid.token"}, follow_redirects=False)

    assert response.status_code == 302
    assert response.headers["location"] == "/login"


def test_middleware_sets_username_in_request_state(test_app, test_username, secret_key):
    """Test that middleware sets username in request.state."""
    client = TestClient(test_app)

    # Create valid token
    token = create_access_token(test_username, secret_key, expires_hours=1)

    # Request should have username in response
    response = client.get("/dashboard", cookies={COOKIE_NAME: token})

    assert response.status_code == 200
    assert test_username in response.text


# =====================================================================
# Cookie Helper Tests
# =====================================================================


def test_set_auth_cookie_settings():
    """Test that set_auth_cookie sets correct cookie settings."""
    response = MagicMock()
    token = "test-token"

    set_auth_cookie(response, token, max_age=3600, secure=True)

    # Verify set_cookie was called with correct parameters
    response.set_cookie.assert_called_once()
    call_kwargs = response.set_cookie.call_args[1]

    assert call_kwargs["key"] == COOKIE_NAME
    assert call_kwargs["value"] == token
    assert call_kwargs["max_age"] == 3600
    assert call_kwargs["httponly"] is True
    assert call_kwargs["secure"] is True
    assert call_kwargs["samesite"] == "strict"
    assert call_kwargs["path"] == "/"


def test_set_auth_cookie_insecure_for_local_dev():
    """Test that set_auth_cookie can be set to insecure for local dev."""
    response = MagicMock()
    token = "test-token"

    set_auth_cookie(response, token, secure=False)

    call_kwargs = response.set_cookie.call_args[1]
    assert call_kwargs["secure"] is False


def test_set_auth_cookie_httponly_always_true():
    """Test that httpOnly is always True for security."""
    response = MagicMock()
    token = "test-token"

    set_auth_cookie(response, token)

    call_kwargs = response.set_cookie.call_args[1]
    assert call_kwargs["httponly"] is True


def test_set_auth_cookie_samesite_strict():
    """Test that samesite is always 'strict' for CSRF protection."""
    response = MagicMock()
    token = "test-token"

    set_auth_cookie(response, token)

    call_kwargs = response.set_cookie.call_args[1]
    assert call_kwargs["samesite"] == "strict"


def test_clear_auth_cookie():
    """Test that clear_auth_cookie deletes the cookie correctly."""
    response = MagicMock()

    clear_auth_cookie(response)

    # Verify delete_cookie was called with correct parameters
    response.delete_cookie.assert_called_once()
    call_kwargs = response.delete_cookie.call_args[1]

    assert call_kwargs["key"] == COOKIE_NAME
    assert call_kwargs["path"] == "/"
    assert call_kwargs["httponly"] is True
    assert call_kwargs["secure"] is True
    assert call_kwargs["samesite"] == "strict"


# =====================================================================
# Custom Excluded Paths Tests
# =====================================================================


@pytest.fixture
def test_app_custom_exclusions(secret_key):
    """Create test app with custom excluded paths."""
    app = Starlette()

    # Add middleware with custom exclusions
    custom_exclusions = {"/login", "/public", "/health"}
    app.add_middleware(AuthMiddleware, secret_key=secret_key, excluded_paths=custom_exclusions)

    @app.route("/public")
    async def public(request):
        return Response("Public page", media_type="text/plain")

    @app.route("/health")
    async def health(request):
        return Response("OK", media_type="text/plain")

    @app.route("/private")
    async def private(request):
        return Response("Private page", media_type="text/plain")

    return app


def test_middleware_custom_excluded_paths(test_app_custom_exclusions):
    """Test middleware with custom excluded paths."""
    client = TestClient(test_app_custom_exclusions)

    # /public should be accessible without auth
    response = client.get("/public")
    assert response.status_code == 200

    # /health should be accessible without auth
    response = client.get("/health")
    assert response.status_code == 200

    # /private should require auth
    response = client.get("/private", follow_redirects=False)
    assert response.status_code == 302


# =====================================================================
# Integration Tests
# =====================================================================


def test_full_auth_flow(test_app, test_username, secret_key):
    """Test complete authentication flow."""
    client = TestClient(test_app)

    # 1. Try to access protected page without auth -> redirect to login
    response = client.get("/dashboard", follow_redirects=False)
    assert response.status_code == 302
    assert response.headers["location"] == "/login"

    # 2. Create token (simulating login)
    token = create_access_token(test_username, secret_key, expires_hours=1)

    # 3. Access protected page with token -> should succeed
    response = client.get("/dashboard", cookies={COOKIE_NAME: token})
    assert response.status_code == 200
    assert test_username in response.text

    # 4. Access login page with token -> should still succeed (excluded path)
    response = client.get("/login", cookies={COOKIE_NAME: token})
    assert response.status_code == 200


def test_token_expiration_handling(test_app, test_username, secret_key):
    """Test handling of expired tokens."""
    from jose import jwt

    client = TestClient(test_app)

    # Create expired token
    expire = datetime.now(timezone.utc) - timedelta(hours=1)
    payload = {
        "sub": test_username,
        "exp": expire,
        "iat": datetime.now(timezone.utc),
    }
    expired_token = jwt.encode(payload, secret_key, algorithm="HS256")

    # Request with expired token should redirect
    response = client.get("/dashboard", cookies={COOKIE_NAME: expired_token}, follow_redirects=False)
    assert response.status_code == 302
    assert response.headers["location"] == "/login"
