"""Unit tests for the quota checker Lambda handler."""

from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch
from zoneinfo import ZoneInfo

import boto3
import pytest
from moto import mock_aws

from src.scheduler.quota_checker import (
    QUOTA_STATUSES,
    VIETNAM_TZ,
    count_todays_jobs,
    get_vietnam_today,
    handler,
)


@pytest.fixture
def aws_credentials(monkeypatch):
    """Mock AWS credentials for moto."""
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("AWS_SECURITY_TOKEN", "testing")
    monkeypatch.setenv("AWS_SESSION_TOKEN", "testing")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")


@pytest.fixture
def mock_settings():
    """Mock settings."""
    with patch("src.scheduler.quota_checker.get_settings") as mock:
        settings = MagicMock()
        settings.daily_quota = 10
        settings.s3_bucket = "test-bucket"
        settings.aws_region = "us-east-1"
        settings.dynamodb_jobs_table = "test-jobs-table"
        mock.return_value = settings
        yield settings


@pytest.fixture
def dynamodb_client(aws_credentials, mock_settings):
    """Create a mock DynamoDB client with table."""
    with mock_aws():
        dynamodb = boto3.client("dynamodb", region_name="us-east-1")
        dynamodb.create_table(
            TableName="test-jobs-table",
            KeySchema=[{"AttributeName": "job_id", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "job_id", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )
        yield dynamodb


@pytest.fixture
def mock_db_client(dynamodb_client, mock_settings):
    """Mock DynamoDB client for handler."""
    with patch("src.scheduler.quota_checker.DynamoDBClient") as mock_class:
        mock_instance = MagicMock()
        # Mock the dynamodb resource and its meta.client
        mock_dynamodb = MagicMock()
        mock_dynamodb.meta.client = dynamodb_client
        mock_instance._dynamodb = mock_dynamodb
        mock_instance._settings = mock_settings
        mock_class.return_value = mock_instance
        yield mock_instance


def create_job_item(
    job_id: str,
    status: str,
    created_at: datetime,
) -> dict:
    """
    Create a DynamoDB job item.

    Args:
        job_id: Job ID
        status: Job status
        created_at: Created timestamp (timezone-aware)

    Returns:
        DynamoDB item dict
    """
    return {
        "job_id": {"S": job_id},
        "status": {"S": status},
        "created_at": {"S": created_at.isoformat()},
        "manga_title": {"S": "Test Manga"},
        "updated_at": {"S": created_at.isoformat()},
    }


def test_get_vietnam_today():
    """Test getting today's date in Vietnam timezone."""
    # Mock current time to a known value
    # 2026-02-07 16:00 UTC = 2026-02-07 23:00 Vietnam (UTC+7)
    test_time = datetime(2026, 2, 7, 16, 0, 0, tzinfo=ZoneInfo("UTC"))

    with patch("src.scheduler.quota_checker.datetime") as mock_datetime:
        mock_datetime.now.return_value = test_time.astimezone(VIETNAM_TZ)
        result = get_vietnam_today()

    assert result == "2026-02-07"


def test_get_vietnam_today_crosses_midnight():
    """Test date calculation when UTC and Vietnam dates differ."""
    # 2026-02-07 23:00 UTC = 2026-02-08 06:00 Vietnam (next day)
    test_time = datetime(2026, 2, 7, 23, 0, 0, tzinfo=ZoneInfo("UTC"))

    with patch("src.scheduler.quota_checker.datetime") as mock_datetime:
        mock_datetime.now.return_value = test_time.astimezone(VIETNAM_TZ)
        result = get_vietnam_today()

    assert result == "2026-02-08"


def test_handler_no_jobs_today(mock_settings, mock_db_client):
    """Test quota check when no jobs exist today."""
    # Empty table
    result = handler({}, None)

    assert result["quota"] == 10
    assert result["used"] == 0
    assert result["remaining"] == 10
    assert result["quota_reached"] is False
    assert result["daily_quota"] == 10
    assert result["daily_count"] == 0


def test_handler_jobs_equal_to_quota(mock_settings, mock_db_client, dynamodb_client):
    """Test quota check when jobs equal quota limit."""
    today = get_vietnam_today()
    today_dt = datetime.fromisoformat(f"{today}T12:00:00+07:00")

    # Create exactly 10 jobs (quota limit)
    for i in range(10):
        item = create_job_item(
            job_id=f"job-{i}",
            status="completed",
            created_at=today_dt,
        )
        dynamodb_client.put_item(TableName="test-jobs-table", Item=item)

    result = handler({}, None)

    assert result["quota"] == 10
    assert result["used"] == 10
    assert result["remaining"] == 0
    assert result["quota_reached"] is True


def test_handler_jobs_exceed_quota(mock_settings, mock_db_client, dynamodb_client):
    """Test quota check when jobs exceed quota limit."""
    today = get_vietnam_today()
    today_dt = datetime.fromisoformat(f"{today}T12:00:00+07:00")

    # Create 12 jobs (exceeds quota of 10)
    for i in range(12):
        item = create_job_item(
            job_id=f"job-{i}",
            status="completed",
            created_at=today_dt,
        )
        dynamodb_client.put_item(TableName="test-jobs-table", Item=item)

    result = handler({}, None)

    assert result["quota"] == 10
    assert result["used"] == 12
    assert result["remaining"] == 0  # Should not go negative
    assert result["quota_reached"] is True


def test_handler_failed_jobs_dont_count(mock_settings, mock_db_client, dynamodb_client):
    """Test that failed jobs are excluded from quota count."""
    today = get_vietnam_today()
    today_dt = datetime.fromisoformat(f"{today}T12:00:00+07:00")

    # Create 5 completed jobs
    for i in range(5):
        item = create_job_item(
            job_id=f"job-completed-{i}",
            status="completed",
            created_at=today_dt,
        )
        dynamodb_client.put_item(TableName="test-jobs-table", Item=item)

    # Create 3 failed jobs (should not count)
    for i in range(3):
        item = create_job_item(
            job_id=f"job-failed-{i}",
            status="failed",
            created_at=today_dt,
        )
        dynamodb_client.put_item(TableName="test-jobs-table", Item=item)

    result = handler({}, None)

    assert result["used"] == 5  # Only completed jobs count
    assert result["remaining"] == 5
    assert result["quota_reached"] is False


def test_handler_only_counts_valid_statuses(mock_settings, mock_db_client, dynamodb_client):
    """Test that only jobs with valid statuses count toward quota."""
    today = get_vietnam_today()
    today_dt = datetime.fromisoformat(f"{today}T12:00:00+07:00")

    # Create jobs with various statuses
    valid_statuses = ["pending", "fetching", "scripting", "tts", "rendering", "uploading", "completed"]
    for i, status in enumerate(valid_statuses):
        item = create_job_item(
            job_id=f"job-{status}-{i}",
            status=status,
            created_at=today_dt,
        )
        dynamodb_client.put_item(TableName="test-jobs-table", Item=item)

    # Create jobs with invalid statuses (should not count)
    invalid_statuses = ["failed"]
    for i, status in enumerate(invalid_statuses):
        item = create_job_item(
            job_id=f"job-{status}-{i}",
            status=status,
            created_at=today_dt,
        )
        dynamodb_client.put_item(TableName="test-jobs-table", Item=item)

    result = handler({}, None)

    assert result["used"] == len(valid_statuses)  # Only valid statuses count
    assert result["remaining"] == 10 - len(valid_statuses)


def test_handler_only_counts_todays_jobs(mock_settings, mock_db_client, dynamodb_client):
    """Test that only jobs created today are counted."""
    today = get_vietnam_today()
    today_dt = datetime.fromisoformat(f"{today}T12:00:00+07:00")
    yesterday_dt = today_dt - timedelta(days=1)
    tomorrow_dt = today_dt + timedelta(days=1)

    # Create 3 jobs today
    for i in range(3):
        item = create_job_item(
            job_id=f"job-today-{i}",
            status="completed",
            created_at=today_dt,
        )
        dynamodb_client.put_item(TableName="test-jobs-table", Item=item)

    # Create 2 jobs yesterday (should not count)
    for i in range(2):
        item = create_job_item(
            job_id=f"job-yesterday-{i}",
            status="completed",
            created_at=yesterday_dt,
        )
        dynamodb_client.put_item(TableName="test-jobs-table", Item=item)

    # Create 2 jobs tomorrow (should not count)
    for i in range(2):
        item = create_job_item(
            job_id=f"job-tomorrow-{i}",
            status="completed",
            created_at=tomorrow_dt,
        )
        dynamodb_client.put_item(TableName="test-jobs-table", Item=item)

    result = handler({}, None)

    assert result["used"] == 3  # Only today's jobs
    assert result["remaining"] == 7


def test_handler_timezone_aware_counting(mock_settings, mock_db_client, dynamodb_client):
    """Test that jobs are counted correctly across timezone boundaries."""
    # Mock Vietnam today as 2026-02-08
    vietnam_today = "2026-02-08"

    with patch("src.scheduler.quota_checker.get_vietnam_today", return_value=vietnam_today):
        # Create job at 2026-02-07 23:00 UTC = 2026-02-08 06:00 Vietnam (today)
        job_utc_night = datetime(2026, 2, 7, 23, 0, 0, tzinfo=ZoneInfo("UTC"))
        item1 = create_job_item(
            job_id="job-utc-night",
            status="completed",
            created_at=job_utc_night,
        )
        dynamodb_client.put_item(TableName="test-jobs-table", Item=item1)

        # Create job at 2026-02-08 18:00 UTC = 2026-02-09 01:00 Vietnam (tomorrow)
        job_utc_evening = datetime(2026, 2, 8, 18, 0, 0, tzinfo=ZoneInfo("UTC"))
        item2 = create_job_item(
            job_id="job-utc-evening",
            status="completed",
            created_at=job_utc_evening,
        )
        dynamodb_client.put_item(TableName="test-jobs-table", Item=item2)

        result = handler({}, None)

        # Only the first job (which is today in Vietnam time) should count
        assert result["used"] == 1


def test_count_todays_jobs_handles_invalid_timestamps(
    mock_settings, mock_db_client, dynamodb_client
):
    """Test that invalid timestamps are handled gracefully."""
    today = get_vietnam_today()
    today_dt = datetime.fromisoformat(f"{today}T12:00:00+07:00")

    # Valid job
    item1 = create_job_item(
        job_id="job-valid",
        status="completed",
        created_at=today_dt,
    )
    dynamodb_client.put_item(TableName="test-jobs-table", Item=item1)

    # Job with invalid timestamp
    item2 = {
        "job_id": {"S": "job-invalid-timestamp"},
        "status": {"S": "completed"},
        "created_at": {"S": "not-a-valid-timestamp"},
        "manga_title": {"S": "Test"},
    }
    dynamodb_client.put_item(TableName="test-jobs-table", Item=item2)

    # Job with missing timestamp
    item3 = {
        "job_id": {"S": "job-no-timestamp"},
        "status": {"S": "completed"},
        "manga_title": {"S": "Test"},
    }
    dynamodb_client.put_item(TableName="test-jobs-table", Item=item3)

    result = handler({}, None)

    # Should only count the valid job
    assert result["used"] == 1


def test_count_todays_jobs_handles_invalid_status(
    mock_settings, mock_db_client, dynamodb_client
):
    """Test that invalid job statuses are handled gracefully."""
    today = get_vietnam_today()
    today_dt = datetime.fromisoformat(f"{today}T12:00:00+07:00")

    # Valid job
    item1 = create_job_item(
        job_id="job-valid",
        status="completed",
        created_at=today_dt,
    )
    dynamodb_client.put_item(TableName="test-jobs-table", Item=item1)

    # Job with invalid status
    item2 = {
        "job_id": {"S": "job-invalid-status"},
        "status": {"S": "invalid-status-value"},
        "created_at": {"S": today_dt.isoformat()},
        "manga_title": {"S": "Test"},
    }
    dynamodb_client.put_item(TableName="test-jobs-table", Item=item2)

    # Job with missing status
    item3 = {
        "job_id": {"S": "job-no-status"},
        "created_at": {"S": today_dt.isoformat()},
        "manga_title": {"S": "Test"},
    }
    dynamodb_client.put_item(TableName="test-jobs-table", Item=item3)

    result = handler({}, None)

    # Should only count the valid job
    assert result["used"] == 1


def test_quota_statuses_constant():
    """Test that QUOTA_STATUSES includes expected statuses."""
    from src.common.models import JobStatus

    expected_statuses = {
        JobStatus.pending,
        JobStatus.fetching,
        JobStatus.scripting,
        JobStatus.tts,
        JobStatus.rendering,
        JobStatus.uploading,
        JobStatus.completed,
    }

    assert QUOTA_STATUSES == expected_statuses

    # Ensure failed is NOT in quota statuses
    assert JobStatus.failed not in QUOTA_STATUSES


def test_handler_custom_quota(mock_settings, mock_db_client, dynamodb_client):
    """Test quota check with custom quota value."""
    # Override quota to 5
    mock_settings.daily_quota = 5

    today = get_vietnam_today()
    today_dt = datetime.fromisoformat(f"{today}T12:00:00+07:00")

    # Create 3 jobs
    for i in range(3):
        item = create_job_item(
            job_id=f"job-{i}",
            status="completed",
            created_at=today_dt,
        )
        dynamodb_client.put_item(TableName="test-jobs-table", Item=item)

    result = handler({}, None)

    assert result["quota"] == 5
    assert result["used"] == 3
    assert result["remaining"] == 2
    assert result["quota_reached"] is False
