"""Unit tests for dashboard API routes."""

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from src.common.models import JobRecord, JobStatus, PipelineSettings
from src.dashboard.app import create_app
from src.dashboard.auth import hash_password


@pytest.fixture
def admin_password():
    """Admin password for testing."""
    return "test-admin-password-123"


@pytest.fixture
def admin_credentials(admin_password):
    """Mock admin credentials."""
    return {
        "username": "admin",
        "password_hash": hash_password(admin_password),
    }


@pytest.fixture
def mock_secrets_client(admin_credentials):
    """Mock SecretsClient."""
    mock = MagicMock()
    mock.get_secret.return_value = admin_credentials
    return mock


@pytest.fixture
def mock_db_client():
    """Mock DynamoDBClient."""
    mock = MagicMock()

    # Default empty jobs list
    mock.list_jobs.return_value = []

    # Default settings
    mock.get_settings.return_value = PipelineSettings(
        daily_quota=10,
        voice_id="vi-VN-HoaiMyNeural",
        tone="engaging",
        script_style="chapter_walkthrough",
    )

    return mock


@pytest.fixture
def test_app(mock_secrets_client, mock_db_client):
    """Create test FastAPI app with mocked dependencies."""
    # Mock settings to avoid requiring environment variables
    mock_settings = MagicMock()
    mock_settings.aws_region = "us-east-1"
    mock_settings.dynamodb_table = "test-table"
    mock_settings.s3_bucket = "test-bucket"

    with patch("src.dashboard.app.get_settings", return_value=mock_settings):
        with patch("src.dashboard.app.DynamoDBClient", return_value=mock_db_client):
            with patch("src.dashboard.app.SecretsClient", return_value=mock_secrets_client):
                app = create_app(
                    jwt_secret_key="test-secret-key-for-testing-only",
                    admin_secret_name="test/admin",
                    state_machine_arn="arn:aws:states:us-east-1:123456789012:stateMachine:test",
                    secure_cookies=False,  # Allow HTTP for testing
                )
                yield app


@pytest.fixture
def client(test_app):
    """Test client for making requests."""
    return TestClient(test_app)


@pytest.fixture
def auth_client(client, admin_password):
    """Authenticated test client with cookie."""
    # Login to get auth cookie
    csrf_token = client.app.state.csrf_manager.generate_token()

    response = client.post(
        "/api/auth/login",
        data={
            "username": "admin",
            "password": admin_password,
            "csrf_token": csrf_token,
        },
    )

    assert response.status_code == 200

    # Return client (cookies are automatically preserved)
    return client


# =====================================================================
# Authentication Routes Tests
# =====================================================================


def test_login_page_accessible(client):
    """Test that login page is accessible without authentication."""
    response = client.get("/login")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]


def test_unauthenticated_access_redirects_to_login(client):
    """Test that unauthenticated requests redirect to /login."""
    response = client.get("/", follow_redirects=False)

    assert response.status_code == 302
    assert response.headers["location"] == "/login"


def test_login_with_valid_credentials(client, admin_password):
    """Test login with valid credentials sets cookie."""
    csrf_token = client.app.state.csrf_manager.generate_token()

    response = client.post(
        "/api/auth/login",
        data={
            "username": "admin",
            "password": admin_password,
            "csrf_token": csrf_token,
        },
    )

    assert response.status_code == 200
    assert "access_token" in response.cookies
    assert response.json()["message"] == "Login successful"
    assert response.json()["redirect"] == "/"


def test_login_with_invalid_credentials(client):
    """Test login with invalid credentials returns 401."""
    csrf_token = client.app.state.csrf_manager.generate_token()

    response = client.post(
        "/api/auth/login",
        data={
            "username": "admin",
            "password": "wrong-password",
            "csrf_token": csrf_token,
        },
    )

    assert response.status_code == 401
    assert "access_token" not in response.cookies


def test_login_with_invalid_csrf(client, admin_password):
    """Test login with invalid CSRF token returns 403."""
    response = client.post(
        "/api/auth/login",
        data={
            "username": "admin",
            "password": admin_password,
            "csrf_token": "invalid-token",
        },
    )

    assert response.status_code == 403


def test_logout_clears_cookie(auth_client):
    """Test logout clears auth cookie."""
    response = auth_client.post("/api/auth/logout")

    assert response.status_code == 200
    assert response.json()["message"] == "Logged out successfully"
    assert response.json()["redirect"] == "/login"


def test_authenticated_access_to_dashboard(auth_client):
    """Test authenticated user can access dashboard."""
    response = auth_client.get("/")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]


# =====================================================================
# Settings Routes Tests
# =====================================================================


def test_settings_page_requires_auth(client):
    """Test settings page requires authentication."""
    response = client.get("/settings", follow_redirects=False)

    assert response.status_code == 302
    assert response.headers["location"] == "/login"


def test_settings_page_accessible_when_authenticated(auth_client):
    """Test authenticated user can access settings page."""
    response = auth_client.get("/settings")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]


def test_get_voices_endpoint(auth_client):
    """Test get voices endpoint returns Vietnamese voices."""
    response = auth_client.get("/api/voices")

    assert response.status_code == 200
    data = response.json()
    assert "voices" in data
    assert len(data["voices"]) >= 2
    assert any(v["id"] == "vi-VN-HoaiMyNeural" for v in data["voices"])


def test_update_settings_with_valid_data(auth_client, mock_db_client):
    """Test updating settings with valid data."""
    csrf_token = auth_client.app.state.csrf_manager.generate_token()

    response = auth_client.put(
        "/api/settings",
        json={
            "daily_quota": 5,
            "voice_id": "vi-VN-HoaiMyNeural",
            "tone": "professional",
            "script_style": "detailed_review",
            "csrf_token": csrf_token,
        },
    )

    assert response.status_code == 200
    assert response.json()["message"] == "Settings updated successfully"

    # Verify DB client was called
    mock_db_client.update_settings.assert_called_once()


def test_update_settings_with_invalid_voice_id(auth_client):
    """Test updating settings with invalid voice ID returns 400."""
    csrf_token = auth_client.app.state.csrf_manager.generate_token()

    response = auth_client.put(
        "/api/settings",
        json={
            "daily_quota": 5,
            "voice_id": "invalid-voice-id",
            "tone": "professional",
            "script_style": "detailed_review",
            "csrf_token": csrf_token,
        },
    )

    assert response.status_code == 400


def test_update_settings_with_invalid_csrf(auth_client):
    """Test updating settings with invalid CSRF token returns 403."""
    response = auth_client.put(
        "/api/settings",
        json={
            "daily_quota": 5,
            "voice_id": "vi-VN-HoaiMyNeural",
            "tone": "professional",
            "script_style": "detailed_review",
            "csrf_token": "invalid-token",
        },
    )

    assert response.status_code == 403


# =====================================================================
# Queue Routes Tests
# =====================================================================


def test_queue_page_requires_auth(client):
    """Test queue page requires authentication."""
    response = client.get("/queue", follow_redirects=False)

    assert response.status_code == 302


def test_queue_page_accessible_when_authenticated(auth_client):
    """Test authenticated user can access queue page."""
    response = auth_client.get("/queue")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]


def test_get_queue_empty(auth_client, mock_db_client):
    """Test get queue returns empty list when no jobs."""
    mock_db_client.list_jobs.return_value = []

    response = auth_client.get("/api/queue")

    assert response.status_code == 200
    data = response.json()
    assert data["jobs"] == []
    assert data["total"] == 0
    assert data["page"] == 1


def test_get_queue_with_jobs(auth_client, mock_db_client):
    """Test get queue returns jobs list."""
    # Create test jobs with explicit timestamps (job-1 is newer, so it appears first)
    now = datetime.now(UTC)
    jobs = [
        JobRecord(
            job_id="job-1",
            manga_id="manga-1",
            manga_title="Test Manga 1",
            status=JobStatus.completed,
            youtube_url="https://youtube.com/watch?v=1",
            created_at=now,  # Newer job
        ),
        JobRecord(
            job_id="job-2",
            manga_id="manga-2",
            manga_title="Test Manga 2",
            status=JobStatus.failed,
            error_message="Test error",
            created_at=now - timedelta(hours=1),  # Older job
        ),
    ]
    mock_db_client.list_jobs.return_value = jobs

    response = auth_client.get("/api/queue")

    assert response.status_code == 200
    data = response.json()
    assert len(data["jobs"]) == 2
    assert data["total"] == 2
    assert data["jobs"][0]["manga_title"] == "Test Manga 1"


def test_get_queue_with_status_filter(auth_client, mock_db_client):
    """Test get queue with status filter."""
    jobs = [
        JobRecord(
            job_id="job-1",
            manga_id="manga-1",
            manga_title="Test Manga 1",
            status=JobStatus.completed,
        ),
        JobRecord(
            job_id="job-2",
            manga_id="manga-2",
            manga_title="Test Manga 2",
            status=JobStatus.failed,
        ),
    ]
    mock_db_client.list_jobs.return_value = jobs

    response = auth_client.get("/api/queue?status_filter=failed")

    assert response.status_code == 200
    data = response.json()
    assert len(data["jobs"]) == 1
    assert data["jobs"][0]["status"] == "failed"


def test_get_queue_with_pagination(auth_client, mock_db_client):
    """Test get queue with pagination."""
    # Create 25 test jobs
    jobs = [
        JobRecord(
            job_id=f"job-{i}",
            manga_id=f"manga-{i}",
            manga_title=f"Test Manga {i}",
            status=JobStatus.completed,
        )
        for i in range(25)
    ]
    mock_db_client.list_jobs.return_value = jobs

    # Get page 1 (20 items)
    response = auth_client.get("/api/queue?page=1&page_size=20")
    assert response.status_code == 200
    data = response.json()
    assert len(data["jobs"]) == 20
    assert data["total"] == 25

    # Get page 2 (5 items)
    response = auth_client.get("/api/queue?page=2&page_size=20")
    assert response.status_code == 200
    data = response.json()
    assert len(data["jobs"]) == 5


def test_get_job_by_id(auth_client, mock_db_client):
    """Test get specific job by ID."""
    job = JobRecord(
        job_id="job-123",
        manga_id="manga-1",
        manga_title="Test Manga",
        status=JobStatus.completed,
    )
    mock_db_client.get_job.return_value = job

    response = auth_client.get("/api/queue/job-123")

    assert response.status_code == 200
    data = response.json()
    assert data["job_id"] == "job-123"
    assert data["manga_title"] == "Test Manga"


def test_get_job_not_found(auth_client, mock_db_client):
    """Test get job returns 404 when not found."""
    mock_db_client.get_job.return_value = None

    response = auth_client.get("/api/queue/nonexistent-job")

    assert response.status_code == 404


def test_retry_job_success(auth_client, mock_db_client):
    """Test retrying a failed job."""
    # Mock failed job
    job = JobRecord(
        job_id="job-failed",
        manga_id="manga-1",
        manga_title="Test Manga",
        status=JobStatus.failed,
        error_message="Test error",
    )
    mock_db_client.get_job.return_value = job

    # Mock Step Functions client
    with patch("src.dashboard.routes.queue_routes.boto3.client") as mock_boto3:
        mock_sfn = MagicMock()
        mock_sfn.start_execution.return_value = {
            "executionArn": "arn:aws:states:us-east-1:123:execution:test:exec-1"
        }
        mock_boto3.return_value = mock_sfn

        csrf_token = auth_client.app.state.csrf_manager.generate_token()

        response = auth_client.post(
            "/api/queue/job-failed/retry",
            data={"csrf_token": csrf_token},
        )

        assert response.status_code == 200
        assert "retry initiated" in response.json()["message"]

        # Verify Step Functions was called
        mock_sfn.start_execution.assert_called_once()

        # Verify job status was updated
        mock_db_client.update_job_status.assert_called_once()


def test_retry_job_not_failed(auth_client, mock_db_client):
    """Test retrying a non-failed job returns 400."""
    # Mock completed job (not failed)
    job = JobRecord(
        job_id="job-completed",
        manga_id="manga-1",
        manga_title="Test Manga",
        status=JobStatus.completed,
    )
    mock_db_client.get_job.return_value = job

    csrf_token = auth_client.app.state.csrf_manager.generate_token()

    response = auth_client.post(
        "/api/queue/job-completed/retry",
        data={"csrf_token": csrf_token},
    )

    assert response.status_code == 400


def test_retry_job_not_found(auth_client, mock_db_client):
    """Test retrying non-existent job returns 404."""
    mock_db_client.get_job.return_value = None

    csrf_token = auth_client.app.state.csrf_manager.generate_token()

    response = auth_client.post(
        "/api/queue/nonexistent-job/retry",
        data={"csrf_token": csrf_token},
    )

    assert response.status_code == 404


# =====================================================================
# Stats Routes Tests
# =====================================================================


def test_dashboard_home_requires_auth(client):
    """Test dashboard home requires authentication."""
    response = client.get("/", follow_redirects=False)

    assert response.status_code == 302


def test_dashboard_home_accessible_when_authenticated(auth_client):
    """Test authenticated user can access dashboard home."""
    response = auth_client.get("/")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]


def test_get_stats_empty_database(auth_client, mock_db_client):
    """Test get stats with no jobs."""
    mock_db_client.list_jobs.return_value = []

    response = auth_client.get("/api/stats")

    assert response.status_code == 200
    data = response.json()
    assert data["videos_today"] == 0
    assert data["videos_total"] == 0
    assert data["videos_failed"] == 0
    assert data["videos_pending"] == 0
    assert data["daily_quota"] == 10


def test_get_stats_with_jobs(auth_client, mock_db_client):
    """Test get stats calculates correctly."""
    # Create test jobs
    now = datetime.now(UTC)

    jobs = [
        JobRecord(
            job_id="job-1",
            manga_id="manga-1",
            manga_title="Test 1",
            status=JobStatus.completed,
            created_at=now,
            updated_at=now,
        ),
        JobRecord(
            job_id="job-2",
            manga_id="manga-2",
            manga_title="Test 2",
            status=JobStatus.failed,
            created_at=now,
            updated_at=now,
        ),
        JobRecord(
            job_id="job-3",
            manga_id="manga-3",
            manga_title="Test 3",
            status=JobStatus.rendering,
            created_at=now,
            updated_at=now,
        ),
    ]
    mock_db_client.list_jobs.return_value = jobs

    response = auth_client.get("/api/stats")

    assert response.status_code == 200
    data = response.json()
    assert data["videos_total"] == 3
    assert data["videos_failed"] == 1
    assert data["videos_pending"] == 1  # rendering is pending


def test_stats_structure(auth_client, mock_db_client):
    """Test stats endpoint returns correct structure."""
    mock_db_client.list_jobs.return_value = []

    response = auth_client.get("/api/stats")

    assert response.status_code == 200
    data = response.json()

    # Verify all required fields present
    assert "videos_today" in data
    assert "videos_total" in data
    assert "videos_failed" in data
    assert "videos_pending" in data
    assert "avg_render_time_minutes" in data
    assert "daily_quota" in data
    assert "quota_remaining" in data


# =====================================================================
# Integration Tests
# =====================================================================


def test_full_auth_flow_integration(client, admin_password):
    """Test complete authentication flow."""
    # 1. Try to access protected route → redirect to login
    response = client.get("/queue", follow_redirects=False)
    assert response.status_code == 302
    assert response.headers["location"] == "/login"

    # 2. Access login page
    response = client.get("/login")
    assert response.status_code == 200

    # 3. Login with credentials
    csrf_token = client.app.state.csrf_manager.generate_token()
    response = client.post(
        "/api/auth/login",
        data={
            "username": "admin",
            "password": admin_password,
            "csrf_token": csrf_token,
        },
    )
    assert response.status_code == 200

    # 4. Access protected route → should succeed
    response = client.get("/queue")
    assert response.status_code == 200

    # 5. Logout
    response = client.post("/api/auth/logout")
    assert response.status_code == 200

    # 6. Try to access protected route again → redirect to login
    response = client.get("/queue", follow_redirects=False)
    assert response.status_code == 302


def test_settings_update_round_trip(auth_client, mock_db_client):
    """Test settings GET → update → GET flow."""
    # Mock get_pipeline_settings to return updated settings after update
    original_settings = PipelineSettings(
        daily_quota=10,
        voice_id="vi-VN-HoaiMyNeural",
        tone="engaging",
        script_style="chapter_walkthrough",
    )

    mock_db_client.get_pipeline_settings.return_value = original_settings

    # 1. Get current settings
    response = auth_client.get("/settings")
    assert response.status_code == 200

    # 2. Update settings
    csrf_token = auth_client.app.state.csrf_manager.generate_token()
    response = auth_client.put(
        "/api/settings",
        json={
            "daily_quota": 5,
            "voice_id": "vi-VN-NamMinhNeural",
            "tone": "professional",
            "script_style": "detailed_review",
            "csrf_token": csrf_token,
        },
    )
    assert response.status_code == 200

    # 3. Verify update was called
    mock_db_client.update_settings.assert_called_once()
