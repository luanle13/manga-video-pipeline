"""Tests for script generation Lambda handler."""

from unittest.mock import MagicMock, patch

import pytest

from src.common.models import JobRecord, JobStatus, PipelineSettings, ScriptDocument
from src.scriptgen.handler import handler


@pytest.fixture
def mock_settings():
    """Create mock settings."""
    settings = MagicMock()
    settings.aws_region = "ap-southeast-1"
    settings.s3_bucket = "test-bucket"
    settings.deepinfra_secret_name = "test-secret"
    settings.deepinfra_base_url = "https://api.deepinfra.com/v1/openai"
    return settings


@pytest.fixture
def sample_event():
    """Sample Lambda event."""
    return {
        "job_id": "job-123",
        "manga_id": "manga-456",
        "manga_title": "One Piece",
        "panel_manifest_s3_key": "jobs/job-123/panel_manifest.json",
    }


@pytest.fixture
def sample_job_record():
    """Sample job record."""
    return JobRecord(
        job_id="job-123",
        manga_id="manga-456",
        manga_title="One Piece",
        status=JobStatus.scripting,
    )


@pytest.fixture
def sample_panel_manifest():
    """Sample panel manifest."""
    return {
        "job_id": "job-123",
        "manga_id": "manga-456",
        "manga_title": "One Piece",
        "description": "A pirate adventure story",
        "genres": ["Action", "Adventure"],
        "cover_url": "https://example.com/cover.jpg",
        "total_panels": 9,
        "chapters": [
            {
                "chapter_id": "ch-001",
                "chapter_number": "1",
                "panel_keys": [
                    "jobs/job-123/panels/0000_0000.jpg",
                    "jobs/job-123/panels/0000_0001.jpg",
                    "jobs/job-123/panels/0000_0002.jpg",
                ],
            },
            {
                "chapter_id": "ch-002",
                "chapter_number": "2",
                "panel_keys": [
                    "jobs/job-123/panels/0001_0000.jpg",
                    "jobs/job-123/panels/0001_0001.jpg",
                ],
            },
            {
                "chapter_id": "ch-003",
                "chapter_number": "3",
                "panel_keys": [
                    "jobs/job-123/panels/0002_0000.jpg",
                    "jobs/job-123/panels/0002_0001.jpg",
                    "jobs/job-123/panels/0002_0002.jpg",
                    "jobs/job-123/panels/0002_0003.jpg",
                ],
            },
        ],
    }


@pytest.fixture
def sample_pipeline_settings():
    """Sample pipeline settings."""
    return PipelineSettings(
        tone="exciting and dramatic",
        script_style="chapter_walkthrough",
    )


@pytest.fixture
def sample_script_document():
    """Sample script document."""
    return ScriptDocument(
        job_id="job-123",
        manga_title="One Piece",
        segments=[
            {
                "chapter": "1",
                "text": "Đây là chương đầu tiên của One Piece.",
                "panel_start": 0,
                "panel_end": 2,
            },
            {
                "chapter": "2",
                "text": "Chương hai tiếp tục câu chuyện phiêu lưu.",
                "panel_start": 3,
                "panel_end": 4,
            },
            {
                "chapter": "3",
                "text": "Chương ba đưa chúng ta vào cuộc phiêu lưu mới.",
                "panel_start": 5,
                "panel_end": 8,
            },
        ],
    )


class TestHappyPath:
    """Tests for successful handler execution."""

    def test_handler_generates_script_successfully(
        self,
        mock_settings,
        sample_event,
        sample_job_record,
        sample_panel_manifest,
        sample_pipeline_settings,
        sample_script_document,
    ):
        """Test that handler successfully generates script."""
        with patch("src.scriptgen.handler.get_settings") as mock_get_settings, \
             patch("src.scriptgen.handler.DynamoDBClient") as mock_db_class, \
             patch("src.scriptgen.handler.S3Client") as mock_s3_class, \
             patch("src.scriptgen.handler.SecretsClient") as mock_secrets_class, \
             patch("src.scriptgen.handler.DeepInfraClient") as mock_deepinfra_class, \
             patch("src.scriptgen.handler.ScriptBuilder") as mock_builder_class, \
             patch("src.scriptgen.handler.uuid.uuid4") as mock_uuid:

            # Setup mocks
            mock_get_settings.return_value = mock_settings
            mock_uuid.return_value = MagicMock(__str__=lambda x: "correlation-id-123")

            # Mock DB client
            mock_db = MagicMock()
            mock_db.get_job.return_value = sample_job_record
            mock_db.get_settings.return_value = sample_pipeline_settings
            mock_db_class.return_value = mock_db

            # Mock S3 client
            mock_s3 = MagicMock()
            mock_s3.download_json.return_value = sample_panel_manifest
            mock_s3_class.return_value = mock_s3

            # Mock Secrets client
            mock_secrets = MagicMock()
            mock_secrets.get_deepinfra_api_key.return_value = "test-api-key"
            mock_secrets_class.return_value = mock_secrets

            # Mock DeepInfra client
            mock_deepinfra = MagicMock()
            mock_deepinfra_class.return_value = mock_deepinfra

            # Mock ScriptBuilder
            mock_builder = MagicMock()
            mock_builder.generate_full_script.return_value = sample_script_document
            mock_builder.estimate_duration_minutes.return_value = 2.5
            mock_builder_class.return_value = mock_builder

            # Execute handler
            result = handler(sample_event, None)

            # Verify result
            assert result["job_id"] == "job-123"
            assert result["script_s3_key"] == "jobs/job-123/script.json"
            assert result["total_segments"] == 3
            assert result["estimated_duration_minutes"] == 2.5

            # Verify API key was loaded from Secrets Manager
            mock_secrets.get_deepinfra_api_key.assert_called_once_with("test-secret")

            # Verify DeepInfra client was initialized with API key
            mock_deepinfra_class.assert_called_once_with(
                api_key="test-api-key",
                base_url="https://api.deepinfra.com/v1/openai",
            )

            # Verify script was uploaded to S3
            mock_s3.upload_json.assert_called_once()
            upload_call = mock_s3.upload_json.call_args
            assert upload_call[0][1] == "jobs/job-123/script.json"

            # Verify job status was updated
            mock_db.update_job_status.assert_called_once_with(
                job_id="job-123",
                status=JobStatus.tts,
                progress_pct=40,
            )

            # Verify client cleanup
            mock_deepinfra.close.assert_called_once()

    def test_api_key_loaded_from_secrets_manager(
        self,
        mock_settings,
        sample_event,
        sample_job_record,
        sample_panel_manifest,
        sample_pipeline_settings,
        sample_script_document,
    ):
        """Test that API key is loaded from Secrets Manager, not hardcoded."""
        with patch("src.scriptgen.handler.get_settings") as mock_get_settings, \
             patch("src.scriptgen.handler.DynamoDBClient") as mock_db_class, \
             patch("src.scriptgen.handler.S3Client") as mock_s3_class, \
             patch("src.scriptgen.handler.SecretsClient") as mock_secrets_class, \
             patch("src.scriptgen.handler.DeepInfraClient") as mock_deepinfra_class, \
             patch("src.scriptgen.handler.ScriptBuilder") as mock_builder_class, \
             patch("src.scriptgen.handler.uuid.uuid4"):

            # Setup mocks
            mock_get_settings.return_value = mock_settings

            mock_db = MagicMock()
            mock_db.get_job.return_value = sample_job_record
            mock_db.get_settings.return_value = sample_pipeline_settings
            mock_db_class.return_value = mock_db

            mock_s3 = MagicMock()
            mock_s3.download_json.return_value = sample_panel_manifest
            mock_s3_class.return_value = mock_s3

            mock_secrets = MagicMock()
            mock_secrets.get_deepinfra_api_key.return_value = "secret-api-key-from-sm"
            mock_secrets_class.return_value = mock_secrets

            mock_deepinfra = MagicMock()
            mock_deepinfra_class.return_value = mock_deepinfra

            mock_builder = MagicMock()
            mock_builder.generate_full_script.return_value = sample_script_document
            mock_builder.estimate_duration_minutes.return_value = 1.0
            mock_builder_class.return_value = mock_builder

            # Execute handler
            handler(sample_event, None)

            # Verify Secrets Manager was called
            mock_secrets.get_deepinfra_api_key.assert_called_once()

            # Verify the API key from Secrets Manager was used
            mock_deepinfra_class.assert_called_once()
            call_kwargs = mock_deepinfra_class.call_args.kwargs
            assert call_kwargs["api_key"] == "secret-api-key-from-sm"

    def test_script_stored_in_correct_s3_location(
        self,
        mock_settings,
        sample_event,
        sample_job_record,
        sample_panel_manifest,
        sample_pipeline_settings,
        sample_script_document,
    ):
        """Test that script is stored in correct S3 location."""
        with patch("src.scriptgen.handler.get_settings") as mock_get_settings, \
             patch("src.scriptgen.handler.DynamoDBClient") as mock_db_class, \
             patch("src.scriptgen.handler.S3Client") as mock_s3_class, \
             patch("src.scriptgen.handler.SecretsClient") as mock_secrets_class, \
             patch("src.scriptgen.handler.DeepInfraClient") as mock_deepinfra_class, \
             patch("src.scriptgen.handler.ScriptBuilder") as mock_builder_class, \
             patch("src.scriptgen.handler.uuid.uuid4"):

            # Setup mocks
            mock_get_settings.return_value = mock_settings

            mock_db = MagicMock()
            mock_db.get_job.return_value = sample_job_record
            mock_db.get_settings.return_value = sample_pipeline_settings
            mock_db_class.return_value = mock_db

            mock_s3 = MagicMock()
            mock_s3.download_json.return_value = sample_panel_manifest
            mock_s3_class.return_value = mock_s3

            mock_secrets = MagicMock()
            mock_secrets.get_deepinfra_api_key.return_value = "test-key"
            mock_secrets_class.return_value = mock_secrets

            mock_deepinfra = MagicMock()
            mock_deepinfra_class.return_value = mock_deepinfra

            mock_builder = MagicMock()
            mock_builder.generate_full_script.return_value = sample_script_document
            mock_builder.estimate_duration_minutes.return_value = 1.0
            mock_builder_class.return_value = mock_builder

            # Execute handler
            result = handler(sample_event, None)

            # Verify S3 key format
            expected_key = "jobs/job-123/script.json"
            assert result["script_s3_key"] == expected_key

            # Verify upload was called with correct key
            mock_s3.upload_json.assert_called_once()
            upload_key = mock_s3.upload_json.call_args[0][1]
            assert upload_key == expected_key

    def test_job_status_updated_correctly(
        self,
        mock_settings,
        sample_event,
        sample_job_record,
        sample_panel_manifest,
        sample_pipeline_settings,
        sample_script_document,
    ):
        """Test that job status is updated to tts with correct progress."""
        with patch("src.scriptgen.handler.get_settings") as mock_get_settings, \
             patch("src.scriptgen.handler.DynamoDBClient") as mock_db_class, \
             patch("src.scriptgen.handler.S3Client") as mock_s3_class, \
             patch("src.scriptgen.handler.SecretsClient") as mock_secrets_class, \
             patch("src.scriptgen.handler.DeepInfraClient") as mock_deepinfra_class, \
             patch("src.scriptgen.handler.ScriptBuilder") as mock_builder_class, \
             patch("src.scriptgen.handler.uuid.uuid4"):

            # Setup mocks
            mock_get_settings.return_value = mock_settings

            mock_db = MagicMock()
            mock_db.get_job.return_value = sample_job_record
            mock_db.get_settings.return_value = sample_pipeline_settings
            mock_db_class.return_value = mock_db

            mock_s3 = MagicMock()
            mock_s3.download_json.return_value = sample_panel_manifest
            mock_s3_class.return_value = mock_s3

            mock_secrets = MagicMock()
            mock_secrets.get_deepinfra_api_key.return_value = "test-key"
            mock_secrets_class.return_value = mock_secrets

            mock_deepinfra = MagicMock()
            mock_deepinfra_class.return_value = mock_deepinfra

            mock_builder = MagicMock()
            mock_builder.generate_full_script.return_value = sample_script_document
            mock_builder.estimate_duration_minutes.return_value = 1.0
            mock_builder_class.return_value = mock_builder

            # Execute handler
            handler(sample_event, None)

            # Verify job status update
            mock_db.update_job_status.assert_called_once_with(
                job_id="job-123",
                status=JobStatus.tts,
                progress_pct=40,
            )

    def test_manga_info_reconstructed_correctly(
        self,
        mock_settings,
        sample_event,
        sample_job_record,
        sample_panel_manifest,
        sample_pipeline_settings,
        sample_script_document,
    ):
        """Test that MangaInfo is reconstructed correctly from panel manifest."""
        with patch("src.scriptgen.handler.get_settings") as mock_get_settings, \
             patch("src.scriptgen.handler.DynamoDBClient") as mock_db_class, \
             patch("src.scriptgen.handler.S3Client") as mock_s3_class, \
             patch("src.scriptgen.handler.SecretsClient") as mock_secrets_class, \
             patch("src.scriptgen.handler.DeepInfraClient") as mock_deepinfra_class, \
             patch("src.scriptgen.handler.ScriptBuilder") as mock_builder_class, \
             patch("src.scriptgen.handler.uuid.uuid4"):

            # Setup mocks
            mock_get_settings.return_value = mock_settings

            mock_db = MagicMock()
            mock_db.get_job.return_value = sample_job_record
            mock_db.get_settings.return_value = sample_pipeline_settings
            mock_db_class.return_value = mock_db

            mock_s3 = MagicMock()
            mock_s3.download_json.return_value = sample_panel_manifest
            mock_s3_class.return_value = mock_s3

            mock_secrets = MagicMock()
            mock_secrets.get_deepinfra_api_key.return_value = "test-key"
            mock_secrets_class.return_value = mock_secrets

            mock_deepinfra = MagicMock()
            mock_deepinfra_class.return_value = mock_deepinfra

            mock_builder = MagicMock()
            mock_builder.generate_full_script.return_value = sample_script_document
            mock_builder.estimate_duration_minutes.return_value = 1.0
            mock_builder_class.return_value = mock_builder

            # Execute handler
            handler(sample_event, None)

            # Verify generate_full_script was called
            mock_builder.generate_full_script.assert_called_once()

            # Check the manga argument
            call_kwargs = mock_builder.generate_full_script.call_args.kwargs
            manga = call_kwargs["manga"]

            # Verify manga details
            assert manga.manga_id == "manga-456"
            assert manga.title == "One Piece"
            assert manga.description == "A pirate adventure story"
            assert manga.genres == ["Action", "Adventure"]
            assert manga.cover_url == "https://example.com/cover.jpg"

            # Verify chapters
            assert len(manga.chapters) == 3
            assert manga.chapters[0].chapter_id == "ch-001"
            assert manga.chapters[0].chapter_number == "1"
            assert len(manga.chapters[0].page_urls) == 3
            assert manga.chapters[1].chapter_number == "2"
            assert len(manga.chapters[1].page_urls) == 2
            assert manga.chapters[2].chapter_number == "3"
            assert len(manga.chapters[2].page_urls) == 4


class TestErrorHandling:
    """Tests for error handling."""

    def test_error_updates_job_to_failed(
        self,
        mock_settings,
        sample_event,
    ):
        """Test that errors update job status to failed."""
        with patch("src.scriptgen.handler.get_settings") as mock_get_settings, \
             patch("src.scriptgen.handler.DynamoDBClient") as mock_db_class, \
             patch("src.scriptgen.handler.S3Client") as mock_s3_class, \
             patch("src.scriptgen.handler.SecretsClient") as mock_secrets_class, \
             patch("src.scriptgen.handler.uuid.uuid4"):

            # Setup mocks
            mock_get_settings.return_value = mock_settings

            mock_db = MagicMock()
            mock_db.get_job.side_effect = Exception("Database error")
            mock_db_class.return_value = mock_db

            mock_s3_class.return_value = MagicMock()

            mock_secrets = MagicMock()
            mock_secrets.get_deepinfra_api_key.return_value = "test-key"
            mock_secrets_class.return_value = mock_secrets

            # Execute handler and expect exception
            with pytest.raises(Exception, match="Database error"):
                handler(sample_event, None)

            # Verify job status was updated to failed
            mock_db.update_job_status.assert_called_once_with(
                job_id="job-123",
                status=JobStatus.failed,
                error_message="Database error",
            )

    def test_missing_api_key_raises_error(
        self,
        mock_settings,
        sample_event,
        sample_job_record,
    ):
        """Test that missing API key raises error."""
        with patch("src.scriptgen.handler.get_settings") as mock_get_settings, \
             patch("src.scriptgen.handler.DynamoDBClient") as mock_db_class, \
             patch("src.scriptgen.handler.S3Client") as mock_s3_class, \
             patch("src.scriptgen.handler.SecretsClient") as mock_secrets_class, \
             patch("src.scriptgen.handler.uuid.uuid4"):

            # Setup mocks
            mock_get_settings.return_value = mock_settings

            mock_db = MagicMock()
            mock_db.get_job.return_value = sample_job_record
            mock_db_class.return_value = mock_db

            mock_s3_class.return_value = MagicMock()

            mock_secrets = MagicMock()
            mock_secrets.get_deepinfra_api_key.return_value = ""  # Empty API key
            mock_secrets_class.return_value = mock_secrets

            # Execute handler and expect exception
            with pytest.raises(ValueError, match="DeepInfra API key is empty"):
                handler(sample_event, None)

            # Verify job was marked as failed
            mock_db.update_job_status.assert_called_once()
            call_kwargs = mock_db.update_job_status.call_args.kwargs
            assert call_kwargs["status"] == JobStatus.failed

    def test_missing_job_raises_error(
        self,
        mock_settings,
        sample_event,
    ):
        """Test that missing job record raises error."""
        with patch("src.scriptgen.handler.get_settings") as mock_get_settings, \
             patch("src.scriptgen.handler.DynamoDBClient") as mock_db_class, \
             patch("src.scriptgen.handler.S3Client") as mock_s3_class, \
             patch("src.scriptgen.handler.SecretsClient") as mock_secrets_class, \
             patch("src.scriptgen.handler.uuid.uuid4"):

            # Setup mocks
            mock_get_settings.return_value = mock_settings

            mock_db = MagicMock()
            mock_db.get_job.return_value = None  # Job not found
            mock_db_class.return_value = mock_db

            mock_s3_class.return_value = MagicMock()

            mock_secrets = MagicMock()
            mock_secrets.get_deepinfra_api_key.return_value = "test-key"
            mock_secrets_class.return_value = mock_secrets

            # Execute handler and expect exception
            with pytest.raises(ValueError, match="Job not found"):
                handler(sample_event, None)

    def test_error_during_status_update_is_logged(
        self,
        mock_settings,
        sample_event,
    ):
        """Test that errors during status update are logged but don't crash."""
        with patch("src.scriptgen.handler.get_settings") as mock_get_settings, \
             patch("src.scriptgen.handler.DynamoDBClient") as mock_db_class, \
             patch("src.scriptgen.handler.S3Client") as mock_s3_class, \
             patch("src.scriptgen.handler.SecretsClient") as mock_secrets_class, \
             patch("src.scriptgen.handler.uuid.uuid4"):

            # Setup mocks
            mock_get_settings.return_value = mock_settings

            mock_db = MagicMock()
            mock_db.get_job.side_effect = Exception("Original error")
            # Status update also fails
            mock_db.update_job_status.side_effect = Exception("Update error")
            mock_db_class.return_value = mock_db

            mock_s3_class.return_value = MagicMock()

            mock_secrets = MagicMock()
            mock_secrets.get_deepinfra_api_key.return_value = "test-key"
            mock_secrets_class.return_value = mock_secrets

            # Execute handler and expect the original exception
            with pytest.raises(Exception, match="Original error"):
                handler(sample_event, None)

            # Verify status update was attempted
            mock_db.update_job_status.assert_called_once()
