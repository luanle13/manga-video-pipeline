"""Tests for S3 client wrapper."""

import os
import tempfile
from collections.abc import Generator
from pathlib import Path
from unittest.mock import patch

import boto3
import pytest
from moto import mock_aws

from src.common.config import Settings
from src.common.storage import S3Client


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
            "S3_BUCKET": "test-manga-bucket",
            "AWS_REGION": "ap-southeast-1",
        },
    ):
        return Settings()


@pytest.fixture
def mock_s3() -> Generator[None, None, None]:
    """Start moto mock for S3."""
    with mock_aws():
        yield


@pytest.fixture
def s3_bucket(mock_s3: None, settings: Settings) -> None:
    """Create S3 bucket for testing."""
    s3 = boto3.client("s3", region_name=settings.aws_region)
    s3.create_bucket(
        Bucket=settings.s3_bucket,
        CreateBucketConfiguration={"LocationConstraint": settings.aws_region},
    )


@pytest.fixture
def s3_client(s3_bucket: None, settings: Settings) -> S3Client:
    """Create an S3 client for testing."""
    return S3Client(settings)


@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """Create a temporary directory for file tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


class TestFileOperations:
    """Tests for file upload/download operations."""

    def test_upload_and_download_file_roundtrip(
        self, s3_client: S3Client, temp_dir: Path
    ) -> None:
        """Test uploading and downloading a file."""
        # Create a test file
        original_content = b"Hello, this is test content for S3!"
        upload_path = temp_dir / "upload_test.txt"
        upload_path.write_bytes(original_content)

        # Upload the file
        s3_key = "test/upload_test.txt"
        s3_uri = s3_client.upload_file(str(upload_path), s3_key)

        assert s3_uri == "s3://test-manga-bucket/test/upload_test.txt"

        # Download the file
        download_path = temp_dir / "download_test.txt"
        result_path = s3_client.download_file(s3_key, str(download_path))

        assert result_path == str(download_path)
        assert download_path.read_bytes() == original_content

    def test_upload_file_returns_s3_uri(
        self, s3_client: S3Client, temp_dir: Path
    ) -> None:
        """Test that upload_file returns correct S3 URI."""
        test_file = temp_dir / "test.txt"
        test_file.write_text("test content")

        s3_uri = s3_client.upload_file(str(test_file), "folder/test.txt")

        assert s3_uri == "s3://test-manga-bucket/folder/test.txt"

    def test_download_file_creates_parent_dirs(
        self, s3_client: S3Client, temp_dir: Path
    ) -> None:
        """Test that download_file creates parent directories."""
        # Upload a file first
        test_file = temp_dir / "source.txt"
        test_file.write_text("test")
        s3_client.upload_file(str(test_file), "test.txt")

        # Download to nested path that doesn't exist
        nested_path = temp_dir / "nested" / "deep" / "downloaded.txt"
        s3_client.download_file("test.txt", str(nested_path))

        assert nested_path.exists()
        assert nested_path.read_text() == "test"


class TestBytesOperations:
    """Tests for bytes upload/download operations."""

    def test_upload_and_download_bytes_roundtrip(self, s3_client: S3Client) -> None:
        """Test uploading and downloading bytes."""
        original_data = b"\x00\x01\x02\x03\x04\x05 binary data \xff\xfe\xfd"
        s3_key = "test/binary_data.bin"

        # Upload bytes
        s3_uri = s3_client.upload_bytes(original_data, s3_key)
        assert s3_uri == "s3://test-manga-bucket/test/binary_data.bin"

        # Download bytes
        downloaded_data = s3_client.download_bytes(s3_key)
        assert downloaded_data == original_data

    def test_upload_bytes_with_content_type(self, s3_client: S3Client) -> None:
        """Test uploading bytes with custom content type."""
        data = b"<html><body>Hello</body></html>"
        s3_key = "test/page.html"

        s3_uri = s3_client.upload_bytes(data, s3_key, content_type="text/html")

        assert s3_uri == "s3://test-manga-bucket/test/page.html"
        # Verify content is retrievable
        assert s3_client.download_bytes(s3_key) == data

    def test_upload_bytes_empty(self, s3_client: S3Client) -> None:
        """Test uploading empty bytes."""
        s3_key = "test/empty.bin"
        s3_uri = s3_client.upload_bytes(b"", s3_key)

        assert s3_uri == "s3://test-manga-bucket/test/empty.bin"
        assert s3_client.download_bytes(s3_key) == b""


class TestJsonOperations:
    """Tests for JSON upload/download operations."""

    def test_upload_and_download_json_dict_roundtrip(self, s3_client: S3Client) -> None:
        """Test uploading and downloading JSON dict."""
        original_data = {
            "name": "Test Manga",
            "chapters": [1, 2, 3],
            "metadata": {"author": "Test Author", "year": 2024},
        }
        s3_key = "test/data.json"

        # Upload JSON
        s3_uri = s3_client.upload_json(original_data, s3_key)
        assert s3_uri == "s3://test-manga-bucket/test/data.json"

        # Download JSON
        downloaded_data = s3_client.download_json(s3_key)
        assert downloaded_data == original_data

    def test_upload_and_download_json_list_roundtrip(self, s3_client: S3Client) -> None:
        """Test uploading and downloading JSON list."""
        original_data = [
            {"id": 1, "name": "Item 1"},
            {"id": 2, "name": "Item 2"},
            {"id": 3, "name": "Item 3"},
        ]
        s3_key = "test/items.json"

        s3_uri = s3_client.upload_json(original_data, s3_key)
        downloaded_data = s3_client.download_json(s3_key)

        assert s3_uri == "s3://test-manga-bucket/test/items.json"
        assert downloaded_data == original_data

    def test_upload_json_with_unicode(self, s3_client: S3Client) -> None:
        """Test uploading JSON with unicode characters."""
        original_data = {
            "title": "日本語タイトル",
            "description": "한국어 설명",
            "emoji": "🎉🎊",
        }
        s3_key = "test/unicode.json"

        s3_client.upload_json(original_data, s3_key)
        downloaded_data = s3_client.download_json(s3_key)

        assert downloaded_data == original_data


class TestDeletePrefix:
    """Tests for delete_prefix operation."""

    def test_delete_prefix_removes_all_objects(self, s3_client: S3Client) -> None:
        """Test that delete_prefix removes all objects under prefix."""
        # Create multiple objects under a prefix
        prefix = "to_delete/"
        for i in range(5):
            s3_client.upload_bytes(f"content {i}".encode(), f"{prefix}file_{i}.txt")

        # Verify objects exist
        assert len(s3_client.list_objects(prefix)) == 5

        # Delete the prefix
        deleted_count = s3_client.delete_prefix(prefix)

        assert deleted_count == 5
        assert len(s3_client.list_objects(prefix)) == 0

    def test_delete_prefix_handles_nested_objects(self, s3_client: S3Client) -> None:
        """Test delete_prefix with nested directory structure."""
        prefix = "nested/"
        keys = [
            "nested/level1/file1.txt",
            "nested/level1/level2/file2.txt",
            "nested/level1/level2/level3/file3.txt",
            "nested/another/file4.txt",
        ]
        for key in keys:
            s3_client.upload_bytes(b"content", key)

        deleted_count = s3_client.delete_prefix(prefix)

        assert deleted_count == 4
        assert len(s3_client.list_objects(prefix)) == 0

    def test_empty_prefix_delete_returns_zero(self, s3_client: S3Client) -> None:
        """Test that deleting non-existent prefix returns 0."""
        deleted_count = s3_client.delete_prefix("nonexistent/prefix/")
        assert deleted_count == 0

    def test_delete_prefix_only_deletes_matching_prefix(
        self, s3_client: S3Client,
    ) -> None:
        """Test that delete_prefix only deletes matching objects."""
        # Create objects with different prefixes
        s3_client.upload_bytes(b"keep", "keep/file1.txt")
        s3_client.upload_bytes(b"keep", "keep/file2.txt")
        s3_client.upload_bytes(b"delete", "delete/file1.txt")
        s3_client.upload_bytes(b"delete", "delete/file2.txt")

        # Delete only "delete/" prefix
        deleted_count = s3_client.delete_prefix("delete/")

        assert deleted_count == 2
        assert len(s3_client.list_objects("keep/")) == 2
        assert len(s3_client.list_objects("delete/")) == 0


class TestListObjects:
    """Tests for list_objects operation."""

    def test_list_objects_returns_correct_keys(self, s3_client: S3Client) -> None:
        """Test that list_objects returns correct keys."""
        prefix = "list_test/"
        expected_keys = [
            f"{prefix}file_a.txt",
            f"{prefix}file_b.txt",
            f"{prefix}file_c.txt",
        ]
        for key in expected_keys:
            s3_client.upload_bytes(b"content", key)

        keys = s3_client.list_objects(prefix)

        assert sorted(keys) == sorted(expected_keys)

    def test_list_objects_empty_prefix_returns_empty_list(
        self, s3_client: S3Client
    ) -> None:
        """Test that listing non-existent prefix returns empty list."""
        keys = s3_client.list_objects("nonexistent/prefix/")
        assert keys == []

    def test_list_objects_with_nested_structure(self, s3_client: S3Client) -> None:
        """Test list_objects with nested directory structure."""
        keys_to_create = [
            "parent/child1/file1.txt",
            "parent/child1/file2.txt",
            "parent/child2/file3.txt",
            "parent/file4.txt",
        ]
        for key in keys_to_create:
            s3_client.upload_bytes(b"content", key)

        # List all under parent/
        all_keys = s3_client.list_objects("parent/")
        assert len(all_keys) == 4

        # List only under parent/child1/
        child1_keys = s3_client.list_objects("parent/child1/")
        assert len(child1_keys) == 2

    def test_list_objects_prefix_matching(self, s3_client: S3Client) -> None:
        """Test that list_objects matches prefix correctly."""
        s3_client.upload_bytes(b"content", "prefix_test/file.txt")
        s3_client.upload_bytes(b"content", "prefix_testing/file.txt")
        s3_client.upload_bytes(b"content", "other/file.txt")

        # Should match both prefix_test/ and prefix_testing/
        keys = s3_client.list_objects("prefix_test")
        assert len(keys) == 2

        # Should only match prefix_test/
        keys = s3_client.list_objects("prefix_test/")
        assert len(keys) == 1


class TestPresignedUrl:
    """Tests for presigned URL generation."""

    def test_get_presigned_url_returns_url(self, s3_client: S3Client) -> None:
        """Test that get_presigned_url returns a URL."""
        # Upload a file first
        s3_client.upload_bytes(b"test content", "test/presigned.txt")

        url = s3_client.get_presigned_url("test/presigned.txt")

        assert url.startswith("https://")
        assert "test-manga-bucket" in url
        assert "test/presigned.txt" in url

    def test_get_presigned_url_with_custom_expiry(self, s3_client: S3Client) -> None:
        """Test presigned URL with custom expiration."""
        s3_client.upload_bytes(b"test", "test/expiry.txt")

        url = s3_client.get_presigned_url("test/expiry.txt", expires_in=7200)

        assert url.startswith("https://")
        # URL should contain expiration parameter
        assert "Expires" in url or "X-Amz-Expires" in url


class TestClientInitialization:
    """Tests for client initialization."""

    def test_client_uses_config_bucket(
        self, s3_bucket: None, settings: Settings
    ) -> None:
        """Test that client uses bucket from config."""
        client = S3Client(settings)
        assert client._bucket == settings.s3_bucket

    def test_client_uses_config_region(
        self, s3_bucket: None, settings: Settings
    ) -> None:
        """Test that client uses region from config."""
        client = S3Client(settings)
        assert client._settings.aws_region == "ap-southeast-1"
