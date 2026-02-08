"""Unit tests for the cleanup Lambda handler."""

import json
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import boto3
import pytest
from moto import mock_aws

from src.cleanup.handler import handler


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
    with patch("src.cleanup.handler.get_settings") as mock:
        settings = MagicMock()
        settings.s3_bucket = "test-bucket"
        settings.aws_region = "us-east-1"
        settings.dynamodb_jobs_table = "test-jobs-table"
        mock.return_value = settings
        yield settings


@pytest.fixture
def s3_client(aws_credentials, mock_settings):
    """Create a mock S3 client with bucket."""
    with mock_aws():
        s3 = boto3.client("s3", region_name="us-east-1")
        s3.create_bucket(Bucket="test-bucket")
        yield s3


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
def mock_db_client(dynamodb_client):
    """Mock DynamoDB client for handler."""
    with patch("src.cleanup.handler.DynamoDBClient") as mock_class:
        mock_instance = MagicMock()
        mock_instance._client = dynamodb_client
        mock_instance._table_name = "test-jobs-table"

        # Mock get_job to return a job record
        mock_job = MagicMock()
        mock_job.job_id = "test-job-123"
        mock_job.status = "completed"
        mock_instance.get_job.return_value = mock_job

        mock_class.return_value = mock_instance
        yield mock_instance


@pytest.fixture
def mock_s3_client(s3_client):
    """Mock S3Client for handler."""
    with patch("src.cleanup.handler.S3Client") as mock_class:
        from src.common.storage import S3Client

        # Create real S3Client instance with mocked boto3
        settings = MagicMock()
        settings.s3_bucket = "test-bucket"
        settings.aws_region = "us-east-1"

        with patch("src.common.storage.boto3.client", return_value=s3_client):
            real_client = S3Client(settings)
            mock_class.return_value = real_client
            yield real_client


def test_handler_deletes_objects_correctly(
    mock_settings, mock_db_client, mock_s3_client, s3_client
):
    """Test that handler deletes S3 objects correctly and returns metrics."""
    # Create test objects in S3
    job_id = "test-job-123"
    s3_client.put_object(
        Bucket="test-bucket",
        Key=f"jobs/{job_id}/panel_manifest.json",
        Body=b'{"test": "data"}',
    )
    s3_client.put_object(
        Bucket="test-bucket",
        Key=f"jobs/{job_id}/audio/segment_0.mp3",
        Body=b"audio data here",
    )
    s3_client.put_object(
        Bucket="test-bucket",
        Key=f"jobs/{job_id}/video.mp4",
        Body=b"video data here",
    )

    # Call handler
    event = {"job_id": job_id}
    result = handler(event, None)

    # Verify response
    assert result["job_id"] == job_id
    assert result["objects_deleted"] == 3
    assert result["bytes_freed"] > 0

    # Verify objects are deleted
    response = s3_client.list_objects_v2(Bucket="test-bucket", Prefix=f"jobs/{job_id}/")
    assert "Contents" not in response or len(response.get("Contents", [])) == 0


def test_handler_already_clean_prefix_returns_success(
    mock_settings, mock_db_client, mock_s3_client
):
    """Test that handler returns success when prefix is already clean."""
    # No objects in S3
    job_id = "test-job-456"

    # Call handler
    event = {"job_id": job_id}
    result = handler(event, None)

    # Verify response
    assert result["job_id"] == job_id
    assert result["objects_deleted"] == 0
    assert result["bytes_freed"] == 0


def test_handler_updates_job_record(mock_settings, mock_db_client, mock_s3_client, s3_client):
    """Test that handler updates job record with cleanup_at timestamp."""
    job_id = "test-job-789"

    # Create a job record in DynamoDB
    dynamodb = mock_db_client._client
    dynamodb.put_item(
        TableName="test-jobs-table",
        Item={
            "job_id": {"S": job_id},
            "status": {"S": "completed"},
            "created_at": {"S": datetime.now(UTC).isoformat()},
        },
    )

    # Call handler
    event = {"job_id": job_id}
    result = handler(event, None)

    # Verify job record was updated
    response = dynamodb.get_item(
        TableName="test-jobs-table",
        Key={"job_id": {"S": job_id}},
    )

    assert "Item" in response
    item = response["Item"]
    assert "cleanup_at" in item
    assert "updated_at" in item

    # Verify cleanup_at is a valid ISO timestamp
    cleanup_at = datetime.fromisoformat(item["cleanup_at"]["S"])
    assert cleanup_at.tzinfo is not None


def test_handler_counts_bytes_correctly(
    mock_settings, mock_db_client, mock_s3_client, s3_client
):
    """Test that handler correctly counts bytes freed."""
    job_id = "test-job-bytes"

    # Create objects with known sizes
    data_1 = b"a" * 1000  # 1000 bytes
    data_2 = b"b" * 2000  # 2000 bytes
    data_3 = b"c" * 3000  # 3000 bytes

    s3_client.put_object(Bucket="test-bucket", Key=f"jobs/{job_id}/file1.txt", Body=data_1)
    s3_client.put_object(Bucket="test-bucket", Key=f"jobs/{job_id}/file2.txt", Body=data_2)
    s3_client.put_object(Bucket="test-bucket", Key=f"jobs/{job_id}/file3.txt", Body=data_3)

    # Call handler
    event = {"job_id": job_id}
    result = handler(event, None)

    # Verify byte count
    assert result["objects_deleted"] == 3
    assert result["bytes_freed"] == 6000  # 1000 + 2000 + 3000


def test_handler_missing_job_id_raises_error(mock_settings, mock_db_client, mock_s3_client):
    """Test that handler raises error when job_id is missing."""
    event = {}

    with pytest.raises(ValueError, match="job_id is required"):
        handler(event, None)


def test_handler_handles_job_not_found(
    mock_settings, mock_db_client, mock_s3_client, s3_client
):
    """Test that handler handles case when job is not found in database."""
    job_id = "nonexistent-job"

    # Mock get_job to return None
    mock_db_client.get_job.return_value = None

    # Create test object
    s3_client.put_object(
        Bucket="test-bucket",
        Key=f"jobs/{job_id}/test.txt",
        Body=b"test data",
    )

    # Call handler - should still delete objects
    event = {"job_id": job_id}
    result = handler(event, None)

    # Verify deletion happened
    assert result["objects_deleted"] == 1
    assert result["bytes_freed"] > 0


def test_handler_handles_db_update_failure(
    mock_settings, mock_db_client, mock_s3_client, s3_client
):
    """Test that handler handles DynamoDB update failure gracefully."""
    job_id = "test-job-db-error"

    # Create test object
    s3_client.put_object(
        Bucket="test-bucket",
        Key=f"jobs/{job_id}/test.txt",
        Body=b"test data",
    )

    # Mock DynamoDB update to raise error using patch
    with patch.object(
        mock_db_client._client, "update_item", side_effect=Exception("DynamoDB error")
    ):
        # Call handler - should still succeed
        event = {"job_id": job_id}
        result = handler(event, None)

    # Verify deletion still happened despite DB error
    assert result["objects_deleted"] == 1
    assert result["bytes_freed"] > 0

    # Verify the handler completed successfully
    assert result["job_id"] == job_id
