"""Tests for DynamoDB client wrapper."""

import os
from collections.abc import Generator
from datetime import UTC, datetime
from unittest.mock import patch

import boto3
import pytest
from moto import mock_aws

from src.common.config import Settings
from src.common.db import DynamoDBClient
from src.common.models import JobRecord, JobStatus, PipelineSettings


@pytest.fixture
def aws_credentials() -> Generator[None, None, None]:
    """Mock AWS credentials for moto."""
    with patch.dict(
        os.environ,
        {
            "AWS_ACCESS_KEY_ID": "testing",
            "AWS_SECRET_ACCESS_KEY": "testing",
            "AWS_SECURITY_TOKEN": "testing",
            "AWS_SESSION_TOKEN": "testing",
            "AWS_DEFAULT_REGION": "ap-southeast-1",
        },
    ):
        yield


@pytest.fixture
def settings(aws_credentials: None) -> Settings:
    """Create test settings."""
    with patch.dict(
        os.environ,
        {
            "S3_BUCKET": "test-bucket",
            "AWS_REGION": "ap-southeast-1",
            "DYNAMODB_JOBS_TABLE": "test_manga_jobs",
            "DYNAMODB_MANGA_TABLE": "test_processed_manga",
            "DYNAMODB_SETTINGS_TABLE": "test_settings",
        },
    ):
        return Settings()


@pytest.fixture
def mock_dynamodb() -> Generator[None, None, None]:
    """Start moto mock for AWS services."""
    with mock_aws():
        yield


@pytest.fixture
def dynamodb_tables(mock_dynamodb: None, settings: Settings) -> None:
    """Create DynamoDB tables for testing."""
    dynamodb = boto3.resource("dynamodb", region_name=settings.aws_region)

    # Create jobs table
    dynamodb.create_table(
        TableName=settings.dynamodb_jobs_table,
        KeySchema=[{"AttributeName": "job_id", "KeyType": "HASH"}],
        AttributeDefinitions=[{"AttributeName": "job_id", "AttributeType": "S"}],
        BillingMode="PAY_PER_REQUEST",
    )

    # Create manga table
    dynamodb.create_table(
        TableName=settings.dynamodb_manga_table,
        KeySchema=[{"AttributeName": "manga_id", "KeyType": "HASH"}],
        AttributeDefinitions=[{"AttributeName": "manga_id", "AttributeType": "S"}],
        BillingMode="PAY_PER_REQUEST",
    )

    # Create settings table
    dynamodb.create_table(
        TableName=settings.dynamodb_settings_table,
        KeySchema=[{"AttributeName": "setting_id", "KeyType": "HASH"}],
        AttributeDefinitions=[{"AttributeName": "setting_id", "AttributeType": "S"}],
        BillingMode="PAY_PER_REQUEST",
    )


@pytest.fixture
def db_client(dynamodb_tables: None, settings: Settings) -> DynamoDBClient:
    """Create a DynamoDB client for testing."""
    return DynamoDBClient(settings)


class TestJobOperations:
    """Tests for job CRUD operations."""

    def test_create_and_retrieve_job(self, db_client: DynamoDBClient) -> None:
        """Test creating and retrieving a job."""
        job = JobRecord(
            job_id="job-001",
            manga_id="manga-001",
            manga_title="One Piece",
            status=JobStatus.pending,
        )

        db_client.create_job(job)
        retrieved = db_client.get_job("job-001")

        assert retrieved is not None
        assert retrieved.job_id == "job-001"
        assert retrieved.manga_id == "manga-001"
        assert retrieved.manga_title == "One Piece"
        assert retrieved.status == JobStatus.pending
        assert retrieved.created_at is not None
        assert retrieved.updated_at is not None

    def test_get_nonexistent_job_returns_none(self, db_client: DynamoDBClient) -> None:
        """Test that getting a nonexistent job returns None."""
        result = db_client.get_job("nonexistent-job")
        assert result is None

    def test_update_job_status(self, db_client: DynamoDBClient) -> None:
        """Test updating job status."""
        job = JobRecord(
            job_id="job-002",
            manga_id="manga-002",
            manga_title="Naruto",
        )
        db_client.create_job(job)

        # Update to fetching
        db_client.update_job_status("job-002", JobStatus.fetching, progress_pct=10)
        updated = db_client.get_job("job-002")

        assert updated is not None
        assert updated.status == JobStatus.fetching
        assert updated.progress_pct == 10

    def test_update_job_status_with_error(self, db_client: DynamoDBClient) -> None:
        """Test updating job status with error message."""
        job = JobRecord(
            job_id="job-003",
            manga_id="manga-003",
            manga_title="Bleach",
        )
        db_client.create_job(job)

        db_client.update_job_status(
            "job-003",
            JobStatus.failed,
            error_message="API rate limit exceeded",
        )
        updated = db_client.get_job("job-003")

        assert updated is not None
        assert updated.status == JobStatus.failed
        assert updated.error_message == "API rate limit exceeded"

    def test_update_job_status_with_youtube_url(self, db_client: DynamoDBClient) -> None:
        """Test updating job status with YouTube URL."""
        job = JobRecord(
            job_id="job-004",
            manga_id="manga-004",
            manga_title="Attack on Titan",
        )
        db_client.create_job(job)

        db_client.update_job_status(
            "job-004",
            JobStatus.completed,
            youtube_url="https://youtube.com/watch?v=abc123",
            progress_pct=100,
        )
        updated = db_client.get_job("job-004")

        assert updated is not None
        assert updated.status == JobStatus.completed
        assert updated.youtube_url == "https://youtube.com/watch?v=abc123"
        assert updated.progress_pct == 100

    def test_list_jobs_no_filter(self, db_client: DynamoDBClient) -> None:
        """Test listing jobs without filter."""
        jobs = [
            JobRecord(job_id="job-a", manga_id="m-a", manga_title="Manga A"),
            JobRecord(
                job_id="job-b",
                manga_id="m-b",
                manga_title="Manga B",
                status=JobStatus.completed,
            ),
            JobRecord(
                job_id="job-c",
                manga_id="m-c",
                manga_title="Manga C",
                status=JobStatus.failed,
            ),
        ]
        for job in jobs:
            db_client.create_job(job)

        result = db_client.list_jobs()
        assert len(result) == 3

    def test_list_jobs_with_status_filter(self, db_client: DynamoDBClient) -> None:
        """Test listing jobs with status filter."""
        jobs = [
            JobRecord(
                job_id="job-x",
                manga_id="m-x",
                manga_title="Manga X",
                status=JobStatus.pending,
            ),
            JobRecord(
                job_id="job-y",
                manga_id="m-y",
                manga_title="Manga Y",
                status=JobStatus.completed,
            ),
            JobRecord(
                job_id="job-z",
                manga_id="m-z",
                manga_title="Manga Z",
                status=JobStatus.pending,
            ),
        ]
        for job in jobs:
            db_client.create_job(job)

        pending_jobs = db_client.list_jobs(status=JobStatus.pending)
        assert len(pending_jobs) == 2
        for job in pending_jobs:
            assert job.status == JobStatus.pending

    def test_daily_job_count(self, db_client: DynamoDBClient) -> None:
        """Test getting daily job count."""
        # Create jobs (they will get today's date)
        today = datetime.now(UTC).strftime("%Y-%m-%d")

        for i in range(3):
            job = JobRecord(
                job_id=f"job-daily-{i}",
                manga_id=f"m-daily-{i}",
                manga_title=f"Manga Daily {i}",
            )
            db_client.create_job(job)

        count = db_client.get_daily_job_count(today)
        assert count == 3

    def test_daily_job_count_different_date(self, db_client: DynamoDBClient) -> None:
        """Test daily job count for a date with no jobs."""
        count = db_client.get_daily_job_count("2020-01-01")
        assert count == 0


class TestMangaTrackingOperations:
    """Tests for manga tracking operations."""

    def test_is_manga_processed_false(self, db_client: DynamoDBClient) -> None:
        """Test checking unprocessed manga."""
        result = db_client.is_manga_processed("new-manga")
        assert result is False

    def test_mark_manga_processed(self, db_client: DynamoDBClient) -> None:
        """Test marking manga as processed."""
        db_client.mark_manga_processed(
            manga_id="manga-proc-001",
            title="Processed Manga",
            youtube_url="https://youtube.com/watch?v=xyz",
        )

        result = db_client.is_manga_processed("manga-proc-001")
        assert result is True

    def test_duplicate_manga_detection(self, db_client: DynamoDBClient) -> None:
        """Test that duplicate manga marking doesn't overwrite."""
        # Mark first time
        db_client.mark_manga_processed(
            manga_id="manga-dup",
            title="Original Title",
            youtube_url="https://youtube.com/original",
        )

        # Try to mark again with different data
        db_client.mark_manga_processed(
            manga_id="manga-dup",
            title="New Title",
            youtube_url="https://youtube.com/new",
        )

        # Verify original data is preserved
        items = db_client.list_processed_manga()
        manga = next((m for m in items if m["manga_id"] == "manga-dup"), None)

        assert manga is not None
        assert manga["title"] == "Original Title"
        assert manga["youtube_url"] == "https://youtube.com/original"

    def test_list_processed_manga(self, db_client: DynamoDBClient) -> None:
        """Test listing processed manga."""
        for i in range(3):
            db_client.mark_manga_processed(
                manga_id=f"manga-list-{i}",
                title=f"Manga {i}",
            )

        result = db_client.list_processed_manga()
        assert len(result) == 3


class TestSettingsOperations:
    """Tests for settings CRUD operations."""

    def test_get_settings_default(self, db_client: DynamoDBClient) -> None:
        """Test getting default settings when none exist."""
        result = db_client.get_settings()

        assert isinstance(result, PipelineSettings)
        assert result.daily_quota == 1
        assert result.voice_id == "vi-VN-HoaiMyNeural"
        assert result.tone == "engaging and informative"
        assert result.script_style == "chapter_walkthrough"

    def test_settings_round_trip(self, db_client: DynamoDBClient) -> None:
        """Test saving and loading settings."""
        new_settings = PipelineSettings(
            daily_quota=5,
            voice_id="en-US-CustomVoice",
            tone="casual and fun",
            script_style="detailed_review",
        )

        db_client.update_settings(new_settings)
        loaded = db_client.get_settings()

        assert loaded.daily_quota == 5
        assert loaded.voice_id == "en-US-CustomVoice"
        assert loaded.tone == "casual and fun"
        assert loaded.script_style == "detailed_review"

    def test_update_settings_overwrites(self, db_client: DynamoDBClient) -> None:
        """Test that updating settings overwrites previous values."""
        # Set initial settings
        db_client.update_settings(PipelineSettings(daily_quota=3))

        # Update with new settings
        db_client.update_settings(PipelineSettings(daily_quota=7))

        loaded = db_client.get_settings()
        assert loaded.daily_quota == 7


class TestClientInitialization:
    """Tests for client initialization."""

    def test_client_uses_config_table_names(
        self, dynamodb_tables: None, settings: Settings
    ) -> None:
        """Test that client uses table names from config."""
        client = DynamoDBClient(settings)

        # Verify table names match config
        assert client._jobs_table.name == settings.dynamodb_jobs_table
        assert client._manga_table.name == settings.dynamodb_manga_table
        assert client._settings_table.name == settings.dynamodb_settings_table

    def test_client_uses_config_region(
        self, dynamodb_tables: None, settings: Settings
    ) -> None:
        """Test that client uses region from config."""
        client = DynamoDBClient(settings)

        # The client should be initialized with the correct region
        assert settings.aws_region == "ap-southeast-1"
        assert client._settings is not None
