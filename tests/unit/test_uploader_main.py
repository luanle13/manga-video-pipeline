"""Unit tests for uploader main entry point."""

import os
from unittest.mock import MagicMock, patch

import pytest

from src.common.models import ChapterInfo, JobRecord, JobStatus, MangaInfo
from src.uploader.main import main
from src.uploader.upload_client import YouTubeQuotaError, YouTubeUploadError
from src.uploader.youtube_auth import YouTubeAuthError


@pytest.fixture
def mock_env(monkeypatch):
    """Set up environment variables."""
    monkeypatch.setenv("JOB_ID", "test-job-123")


@pytest.fixture
def mock_job_record():
    """Mock job record."""
    return JobRecord(
        job_id="test-job-123",
        manga_id="manga-456",
        manga_title="Test Manga",
        status=JobStatus.rendering,
        progress_pct=85,
    )


@pytest.fixture
def mock_panel_manifest():
    """Mock panel manifest."""
    return {
        "job_id": "test-job-123",
        "manga_id": "manga-456",
        "manga_title": "Test Manga",
        "description": "Test manga description",
        "genres": ["Action", "Adventure"],
        "cover_url": "https://example.com/cover.jpg",
        "total_panels": 10,
        "chapters": [
            {
                "chapter_id": "ch1",
                "title": "Chapter 1",
                "chapter_number": "1",
                "panels": [],
            },
            {
                "chapter_id": "ch2",
                "title": "Chapter 2",
                "chapter_number": "2",
                "panels": [],
            },
        ],
    }


@pytest.fixture
def mock_youtube_metadata():
    """Mock YouTube metadata."""
    return {
        "title": "Review Manga Test Manga | Tóm Tắt Đầy Đủ",
        "description": "📖 Review và tóm tắt manga Test Manga\n\nTest manga description",
        "tags": ["test manga", "action", "adventure"],
        "category_id": "24",
        "default_language": "vi",
        "privacy_status": "public",
    }


class TestUploaderMainFlow:
    """Tests for main uploader flow."""

    @patch("src.uploader.main.get_settings")
    @patch("src.uploader.main.DynamoDBClient")
    @patch("src.uploader.main.S3Client")
    @patch("src.uploader.main.SecretsClient")
    @patch("src.uploader.main.YouTubeAuthManager")
    @patch("src.uploader.main.MetadataGenerator")
    @patch("src.uploader.main.YouTubeUploadClient")
    @patch("src.uploader.main.boto3.client")
    @patch("os.path.exists")
    @patch("os.path.getsize")
    @patch("os.unlink")
    def test_full_upload_flow_with_local_video(
        self,
        mock_unlink,
        mock_getsize,
        mock_exists,
        mock_boto3_client,
        mock_upload_client_class,
        mock_metadata_gen_class,
        mock_youtube_auth_class,
        mock_secrets_client_class,
        mock_s3_client_class,
        mock_db_client_class,
        mock_get_settings,
        mock_env,
        mock_job_record,
        mock_panel_manifest,
        mock_youtube_metadata,
    ):
        """Test full upload flow with local video file."""
        # Setup mocks
        mock_config = MagicMock()
        mock_config.dynamodb_jobs_table = "test-jobs"
        mock_config.s3_bucket = "test-bucket"
        mock_config.aws_region = "us-east-1"
        mock_config.youtube_secret_name = "youtube-secret"
        mock_get_settings.return_value = mock_config

        mock_db_client = MagicMock()
        mock_db_client.get_job.return_value = mock_job_record
        mock_db_client_class.return_value = mock_db_client

        mock_s3_client = MagicMock()
        mock_s3_client.download_json.return_value = mock_panel_manifest
        mock_s3_client_class.return_value = mock_s3_client

        mock_secrets_client = MagicMock()
        mock_secrets_client_class.return_value = mock_secrets_client

        mock_youtube_auth = MagicMock()
        mock_youtube_service = MagicMock()
        mock_youtube_auth.get_authenticated_service.return_value = mock_youtube_service
        mock_youtube_auth_class.return_value = mock_youtube_auth

        mock_metadata_gen = MagicMock()
        mock_metadata_gen.generate_metadata.return_value = mock_youtube_metadata
        mock_metadata_gen_class.return_value = mock_metadata_gen

        mock_upload_client = MagicMock()
        mock_upload_client.upload_video.return_value = "https://youtube.com/watch?v=test123"
        mock_upload_client_class.return_value = mock_upload_client

        mock_lambda_client = MagicMock()
        mock_boto3_client.return_value = mock_lambda_client

        # Mock local video exists
        mock_exists.return_value = True
        mock_getsize.return_value = 100 * 1024 * 1024  # 100MB

        # Execute
        main()

        # Verify flow
        # 1. Config initialized
        mock_get_settings.assert_called()

        # 2. Clients initialized
        mock_db_client_class.assert_called_once()
        mock_s3_client_class.assert_called_once()
        mock_secrets_client_class.assert_called_once()

        # 3. Job loaded
        mock_db_client.get_job.assert_called_once_with("test-job-123")

        # 4. Panel manifest loaded
        mock_s3_client.download_json.assert_called_once_with(
            "jobs/test-job-123/panel_manifest.json"
        )

        # 5. YouTube authenticated
        mock_youtube_auth.get_authenticated_service.assert_called_once()

        # 6. Metadata generated
        mock_metadata_gen.generate_metadata.assert_called_once()

        # 7. Video uploaded
        mock_upload_client.upload_video.assert_called_once()
        upload_call_args = mock_upload_client.upload_video.call_args
        assert "/tmp/render/test-job-123/video.mp4" in upload_call_args[0][0]
        assert upload_call_args[0][1] == mock_youtube_metadata

        # 8. Job status updated to uploading
        status_calls = mock_db_client.update_job_status.call_args_list
        assert any(
            call[1]["status"] == JobStatus.uploading
            for call in status_calls
        )

        # 9. Job status updated to completed
        assert any(
            call[1]["status"] == JobStatus.completed
            for call in status_calls
        )
        completed_call = [c for c in status_calls if c[1]["status"] == JobStatus.completed][0]
        assert completed_call[1]["youtube_url"] == "https://youtube.com/watch?v=test123"
        assert completed_call[1]["progress_pct"] == 100

        # 10. Cleanup Lambda invoked
        mock_lambda_client.invoke.assert_called_once()
        invoke_args = mock_lambda_client.invoke.call_args
        assert "manga-pipeline-cleanup" in invoke_args[1]["FunctionName"]
        assert invoke_args[1]["InvocationType"] == "Event"

        # 11. Local file cleaned up
        mock_unlink.assert_called()

    @patch("src.uploader.main.get_settings")
    @patch("src.uploader.main.DynamoDBClient")
    @patch("src.uploader.main.S3Client")
    @patch("src.uploader.main.SecretsClient")
    @patch("src.uploader.main.YouTubeAuthManager")
    @patch("src.uploader.main.MetadataGenerator")
    @patch("src.uploader.main.YouTubeUploadClient")
    @patch("src.uploader.main.boto3.client")
    @patch("os.path.exists")
    @patch("os.makedirs")
    @patch("os.path.getsize")
    @patch("os.unlink")
    def test_downloads_video_from_s3_when_not_local(
        self,
        mock_unlink,
        mock_getsize,
        mock_makedirs,
        mock_exists,
        mock_boto3_client,
        mock_upload_client_class,
        mock_metadata_gen_class,
        mock_youtube_auth_class,
        mock_secrets_client_class,
        mock_s3_client_class,
        mock_db_client_class,
        mock_get_settings,
        mock_env,
        mock_job_record,
        mock_panel_manifest,
        mock_youtube_metadata,
    ):
        """Test that video is downloaded from S3 when not found locally."""
        # Setup mocks
        mock_config = MagicMock()
        mock_config.dynamodb_jobs_table = "test-jobs"
        mock_config.s3_bucket = "test-bucket"
        mock_config.aws_region = "us-east-1"
        mock_config.youtube_secret_name = "youtube-secret"
        mock_get_settings.return_value = mock_config

        mock_db_client = MagicMock()
        mock_db_client.get_job.return_value = mock_job_record
        mock_db_client_class.return_value = mock_db_client

        mock_s3_client = MagicMock()
        mock_s3_client.download_json.return_value = mock_panel_manifest
        mock_s3_client_class.return_value = mock_s3_client

        mock_secrets_client = MagicMock()
        mock_secrets_client_class.return_value = mock_secrets_client

        mock_youtube_auth = MagicMock()
        mock_youtube_service = MagicMock()
        mock_youtube_auth.get_authenticated_service.return_value = mock_youtube_service
        mock_youtube_auth_class.return_value = mock_youtube_auth

        mock_metadata_gen = MagicMock()
        mock_metadata_gen.generate_metadata.return_value = mock_youtube_metadata
        mock_metadata_gen_class.return_value = mock_metadata_gen

        mock_upload_client = MagicMock()
        mock_upload_client.upload_video.return_value = "https://youtube.com/watch?v=test123"
        mock_upload_client_class.return_value = mock_upload_client

        mock_lambda_client = MagicMock()
        mock_boto3_client.return_value = mock_lambda_client

        # Mock local video does NOT exist
        mock_exists.side_effect = [False, True]  # First check false, then after download true
        mock_getsize.return_value = 100 * 1024 * 1024

        # Execute
        main()

        # Verify video was downloaded from S3
        mock_s3_client.download_file.assert_called_once()
        download_call_args = mock_s3_client.download_file.call_args
        assert download_call_args[0][0] == "jobs/test-job-123/video.mp4"
        assert "/tmp/render/test-job-123/video.mp4" in download_call_args[0][1]

        # Verify directory was created
        mock_makedirs.assert_called()


class TestErrorHandling:
    """Tests for error handling."""

    @patch("src.uploader.main.get_settings")
    @patch("src.uploader.main.DynamoDBClient")
    def test_raises_error_without_job_id(self, mock_db_client_class, mock_get_settings):
        """Test that error is raised when JOB_ID is not set."""
        # Don't set JOB_ID environment variable
        with pytest.raises(ValueError, match="JOB_ID environment variable not set"):
            main()

    @patch("src.uploader.main.get_settings")
    @patch("src.uploader.main.DynamoDBClient")
    @patch("src.uploader.main.S3Client")
    @patch("src.uploader.main.SecretsClient")
    def test_handles_missing_job_record(
        self,
        mock_secrets_client_class,
        mock_s3_client_class,
        mock_db_client_class,
        mock_get_settings,
        mock_env,
    ):
        """Test handling of missing job record."""
        # Setup mocks
        mock_config = MagicMock()
        mock_config.dynamodb_jobs_table = "test-jobs"
        mock_config.s3_bucket = "test-bucket"
        mock_config.aws_region = "us-east-1"
        mock_get_settings.return_value = mock_config

        mock_db_client = MagicMock()
        mock_db_client.get_job.return_value = None  # Job not found
        mock_db_client_class.return_value = mock_db_client

        mock_s3_client = MagicMock()
        mock_s3_client_class.return_value = mock_s3_client

        mock_secrets_client = MagicMock()
        mock_secrets_client_class.return_value = mock_secrets_client

        # Execute & Verify
        with pytest.raises(ValueError, match="Job test-job-123 not found"):
            main()

    @patch("src.uploader.main.get_settings")
    @patch("src.uploader.main.DynamoDBClient")
    @patch("src.uploader.main.S3Client")
    @patch("src.uploader.main.SecretsClient")
    @patch("src.uploader.main.YouTubeAuthManager")
    @patch("os.path.exists")
    def test_handles_youtube_auth_failure(
        self,
        mock_exists,
        mock_youtube_auth_class,
        mock_secrets_client_class,
        mock_s3_client_class,
        mock_db_client_class,
        mock_get_settings,
        mock_env,
        mock_job_record,
        mock_panel_manifest,
    ):
        """Test handling of YouTube authentication failure."""
        # Setup mocks
        mock_config = MagicMock()
        mock_config.dynamodb_jobs_table = "test-jobs"
        mock_config.s3_bucket = "test-bucket"
        mock_config.aws_region = "us-east-1"
        mock_config.youtube_secret_name = "youtube-secret"
        mock_get_settings.return_value = mock_config

        mock_db_client = MagicMock()
        mock_db_client.get_job.return_value = mock_job_record
        mock_db_client_class.return_value = mock_db_client

        mock_s3_client = MagicMock()
        mock_s3_client.download_json.return_value = mock_panel_manifest
        mock_s3_client_class.return_value = mock_s3_client

        mock_secrets_client = MagicMock()
        mock_secrets_client_class.return_value = mock_secrets_client

        mock_youtube_auth = MagicMock()
        mock_youtube_auth.get_authenticated_service.side_effect = YouTubeAuthError(
            "Authentication failed"
        )
        mock_youtube_auth_class.return_value = mock_youtube_auth

        mock_exists.return_value = True

        # Execute & Verify
        with pytest.raises(YouTubeAuthError):
            main()

        # Verify job status was updated to failed
        mock_db_client.update_job_status.assert_called()
        call_args = mock_db_client.update_job_status.call_args
        assert call_args[1]["status"] == JobStatus.failed
        assert "authentication failed" in call_args[1]["error_message"].lower()

    @patch("src.uploader.main.get_settings")
    @patch("src.uploader.main.DynamoDBClient")
    @patch("src.uploader.main.S3Client")
    @patch("src.uploader.main.SecretsClient")
    @patch("src.uploader.main.YouTubeAuthManager")
    @patch("src.uploader.main.MetadataGenerator")
    @patch("src.uploader.main.YouTubeUploadClient")
    @patch("os.path.exists")
    @patch("os.path.getsize")
    @patch("os.unlink")
    def test_handles_quota_exceeded_error(
        self,
        mock_unlink,
        mock_getsize,
        mock_exists,
        mock_upload_client_class,
        mock_metadata_gen_class,
        mock_youtube_auth_class,
        mock_secrets_client_class,
        mock_s3_client_class,
        mock_db_client_class,
        mock_get_settings,
        mock_env,
        mock_job_record,
        mock_panel_manifest,
        mock_youtube_metadata,
    ):
        """Test handling of YouTube quota exceeded error."""
        # Setup mocks
        mock_config = MagicMock()
        mock_config.dynamodb_jobs_table = "test-jobs"
        mock_config.s3_bucket = "test-bucket"
        mock_config.aws_region = "us-east-1"
        mock_config.youtube_secret_name = "youtube-secret"
        mock_get_settings.return_value = mock_config

        mock_db_client = MagicMock()
        mock_db_client.get_job.return_value = mock_job_record
        mock_db_client_class.return_value = mock_db_client

        mock_s3_client = MagicMock()
        mock_s3_client.download_json.return_value = mock_panel_manifest
        mock_s3_client_class.return_value = mock_s3_client

        mock_secrets_client = MagicMock()
        mock_secrets_client_class.return_value = mock_secrets_client

        mock_youtube_auth = MagicMock()
        mock_youtube_service = MagicMock()
        mock_youtube_auth.get_authenticated_service.return_value = mock_youtube_service
        mock_youtube_auth_class.return_value = mock_youtube_auth

        mock_metadata_gen = MagicMock()
        mock_metadata_gen.generate_metadata.return_value = mock_youtube_metadata
        mock_metadata_gen_class.return_value = mock_metadata_gen

        mock_upload_client = MagicMock()
        mock_upload_client.upload_video.side_effect = YouTubeQuotaError("Quota exceeded")
        mock_upload_client_class.return_value = mock_upload_client

        mock_exists.return_value = True
        mock_getsize.return_value = 100 * 1024 * 1024

        # Execute & Verify
        with pytest.raises(YouTubeQuotaError):
            main()

        # Verify job status was updated with specific quota message
        mock_db_client.update_job_status.assert_called()
        status_calls = mock_db_client.update_job_status.call_args_list

        # Find the failed status call
        failed_calls = [c for c in status_calls if c[1]["status"] == JobStatus.failed]
        assert len(failed_calls) > 0
        assert "YouTube quota exceeded, will retry next day" in failed_calls[0][1]["error_message"]

    @patch("src.uploader.main.get_settings")
    @patch("src.uploader.main.DynamoDBClient")
    @patch("src.uploader.main.S3Client")
    @patch("src.uploader.main.SecretsClient")
    @patch("src.uploader.main.YouTubeAuthManager")
    @patch("src.uploader.main.MetadataGenerator")
    @patch("src.uploader.main.YouTubeUploadClient")
    @patch("os.path.exists")
    @patch("os.path.getsize")
    @patch("os.unlink")
    def test_handles_upload_error(
        self,
        mock_unlink,
        mock_getsize,
        mock_exists,
        mock_upload_client_class,
        mock_metadata_gen_class,
        mock_youtube_auth_class,
        mock_secrets_client_class,
        mock_s3_client_class,
        mock_db_client_class,
        mock_get_settings,
        mock_env,
        mock_job_record,
        mock_panel_manifest,
        mock_youtube_metadata,
    ):
        """Test handling of general upload error."""
        # Setup mocks
        mock_config = MagicMock()
        mock_config.dynamodb_jobs_table = "test-jobs"
        mock_config.s3_bucket = "test-bucket"
        mock_config.aws_region = "us-east-1"
        mock_config.youtube_secret_name = "youtube-secret"
        mock_get_settings.return_value = mock_config

        mock_db_client = MagicMock()
        mock_db_client.get_job.return_value = mock_job_record
        mock_db_client_class.return_value = mock_db_client

        mock_s3_client = MagicMock()
        mock_s3_client.download_json.return_value = mock_panel_manifest
        mock_s3_client_class.return_value = mock_s3_client

        mock_secrets_client = MagicMock()
        mock_secrets_client_class.return_value = mock_secrets_client

        mock_youtube_auth = MagicMock()
        mock_youtube_service = MagicMock()
        mock_youtube_auth.get_authenticated_service.return_value = mock_youtube_service
        mock_youtube_auth_class.return_value = mock_youtube_auth

        mock_metadata_gen = MagicMock()
        mock_metadata_gen.generate_metadata.return_value = mock_youtube_metadata
        mock_metadata_gen_class.return_value = mock_metadata_gen

        mock_upload_client = MagicMock()
        mock_upload_client.upload_video.side_effect = YouTubeUploadError("Upload failed")
        mock_upload_client_class.return_value = mock_upload_client

        mock_exists.return_value = True
        mock_getsize.return_value = 100 * 1024 * 1024

        # Execute & Verify
        with pytest.raises(YouTubeUploadError):
            main()

        # Verify job status was updated to failed
        status_calls = mock_db_client.update_job_status.call_args_list
        failed_calls = [c for c in status_calls if c[1]["status"] == JobStatus.failed]
        assert len(failed_calls) > 0
        assert "Video upload failed" in failed_calls[0][1]["error_message"]


class TestCleanupHandling:
    """Tests for cleanup handling."""

    @patch("src.uploader.main.get_settings")
    @patch("src.uploader.main.DynamoDBClient")
    @patch("src.uploader.main.S3Client")
    @patch("src.uploader.main.SecretsClient")
    @patch("src.uploader.main.YouTubeAuthManager")
    @patch("src.uploader.main.MetadataGenerator")
    @patch("src.uploader.main.YouTubeUploadClient")
    @patch("src.uploader.main.boto3.client")
    @patch("os.path.exists")
    @patch("os.path.getsize")
    @patch("os.unlink")
    def test_handles_cleanup_lambda_failure_gracefully(
        self,
        mock_unlink,
        mock_getsize,
        mock_exists,
        mock_boto3_client,
        mock_upload_client_class,
        mock_metadata_gen_class,
        mock_youtube_auth_class,
        mock_secrets_client_class,
        mock_s3_client_class,
        mock_db_client_class,
        mock_get_settings,
        mock_env,
        mock_job_record,
        mock_panel_manifest,
        mock_youtube_metadata,
    ):
        """Test that cleanup Lambda failure doesn't fail the job."""
        # Setup mocks (similar to happy path)
        mock_config = MagicMock()
        mock_config.dynamodb_jobs_table = "test-jobs"
        mock_config.s3_bucket = "test-bucket"
        mock_config.aws_region = "us-east-1"
        mock_config.youtube_secret_name = "youtube-secret"
        mock_get_settings.return_value = mock_config

        mock_db_client = MagicMock()
        mock_db_client.get_job.return_value = mock_job_record
        mock_db_client_class.return_value = mock_db_client

        mock_s3_client = MagicMock()
        mock_s3_client.download_json.return_value = mock_panel_manifest
        mock_s3_client_class.return_value = mock_s3_client

        mock_secrets_client = MagicMock()
        mock_secrets_client_class.return_value = mock_secrets_client

        mock_youtube_auth = MagicMock()
        mock_youtube_service = MagicMock()
        mock_youtube_auth.get_authenticated_service.return_value = mock_youtube_service
        mock_youtube_auth_class.return_value = mock_youtube_auth

        mock_metadata_gen = MagicMock()
        mock_metadata_gen.generate_metadata.return_value = mock_youtube_metadata
        mock_metadata_gen_class.return_value = mock_metadata_gen

        mock_upload_client = MagicMock()
        mock_upload_client.upload_video.return_value = "https://youtube.com/watch?v=test123"
        mock_upload_client_class.return_value = mock_upload_client

        # Make Lambda invocation fail
        mock_lambda_client = MagicMock()
        mock_lambda_client.invoke.side_effect = Exception("Lambda invocation failed")
        mock_boto3_client.return_value = mock_lambda_client

        mock_exists.return_value = True
        mock_getsize.return_value = 100 * 1024 * 1024

        # Execute - should not raise exception
        main()

        # Verify job was still marked as completed
        status_calls = mock_db_client.update_job_status.call_args_list
        completed_calls = [c for c in status_calls if c[1]["status"] == JobStatus.completed]
        assert len(completed_calls) == 1
