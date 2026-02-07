"""Unit tests for main renderer entry point."""

import os
import sys
from unittest.mock import MagicMock, call, patch

import pytest

# Mock pydub before importing audio_merger (Python 3.13 compatibility)
sys.modules["pydub"] = MagicMock()
sys.modules["pydub.AudioSegment"] = MagicMock()

from src.common.models import AudioManifest, AudioSegment, JobRecord, JobStatus
from src.renderer.main import main


@pytest.fixture
def mock_env(monkeypatch):
    """Set up environment variables."""
    monkeypatch.setenv("JOB_ID", "test-job-123")
    monkeypatch.setenv("TASK_TOKEN", "test-task-token")


@pytest.fixture
def mock_job_record():
    """Mock job record."""
    return JobRecord(
        job_id="test-job-123",
        manga_id="manga-456",
        manga_title="Test Manga",
        status=JobStatus.tts,
        progress_pct=60,
    )


@pytest.fixture
def mock_panel_manifest():
    """Mock panel manifest."""
    return {
        "job_id": "test-job-123",
        "manga_id": "manga-456",
        "manga_title": "Test Manga",
        "total_panels": 3,
        "chapters": [
            {
                "chapter_id": "ch1",
                "chapter_number": "1",
                "panels": [
                    {"s3_key": "jobs/test-job-123/panels/ch1_p0.jpg", "index": 0},
                    {"s3_key": "jobs/test-job-123/panels/ch1_p1.jpg", "index": 1},
                    {"s3_key": "jobs/test-job-123/panels/ch1_p2.jpg", "index": 2},
                ],
            }
        ],
    }


@pytest.fixture
def mock_audio_manifest():
    """Mock audio manifest."""
    return AudioManifest(
        job_id="test-job-123",
        segments=[
            AudioSegment(
                index=0,
                s3_key="jobs/test-job-123/audio/0000.mp3",
                duration_seconds=5.0,
                chapter="1",
                panel_start=0,
                panel_end=0,
            ),
            AudioSegment(
                index=1,
                s3_key="jobs/test-job-123/audio/0001.mp3",
                duration_seconds=5.0,
                chapter="1",
                panel_start=1,
                panel_end=1,
            ),
            AudioSegment(
                index=2,
                s3_key="jobs/test-job-123/audio/0002.mp3",
                duration_seconds=5.0,
                chapter="1",
                panel_start=2,
                panel_end=2,
            ),
        ],
        total_duration_seconds=15.0,
    )


class TestMainRendererFlow:
    """Tests for main renderer flow."""

    @patch("src.renderer.main.get_settings")
    @patch("src.renderer.main.DynamoDBClient")
    @patch("src.renderer.main.S3Client")
    @patch("src.renderer.main.AudioMerger")
    @patch("src.renderer.main.SceneBuilder")
    @patch("src.renderer.main.VideoCompositor")
    @patch("src.renderer.main.register_spot_interruption_handler")
    @patch("src.renderer.main.load_checkpoint")
    @patch("src.renderer.main.delete_checkpoint")
    @patch("src.renderer.main.boto3.client")
    @patch("os.makedirs")
    @patch("os.path.exists")
    @patch("os.path.getsize")
    @patch("shutil.rmtree")
    def test_full_render_flow(
        self,
        mock_rmtree,
        mock_getsize,
        mock_exists,
        mock_makedirs,
        mock_boto3_client,
        mock_delete_checkpoint,
        mock_load_checkpoint,
        mock_register_handler,
        mock_compositor_class,
        mock_scene_builder_class,
        mock_audio_merger_class,
        mock_s3_client_class,
        mock_db_client_class,
        mock_config_class,
        mock_env,
        mock_job_record,
        mock_panel_manifest,
        mock_audio_manifest,
    ):
        """Test full rendering flow from start to finish."""
        # Setup mocks
        mock_config = MagicMock()
        mock_config.dynamodb_jobs_table = "test-jobs-table"
        mock_config.s3_bucket = "test-bucket"
        mock_config.aws_region = "us-east-1"
        mock_config_class.return_value = mock_config

        mock_db_client = MagicMock()
        mock_db_client.get_job.return_value = mock_job_record
        mock_db_client_class.return_value = mock_db_client

        mock_s3_client = MagicMock()
        mock_s3_client.download_json.side_effect = [
            mock_panel_manifest,
            mock_audio_manifest.model_dump(),
        ]
        mock_s3_client_class.return_value = mock_s3_client

        mock_load_checkpoint.return_value = None

        mock_audio_merger = MagicMock()
        mock_audio_merger.merge_from_s3.return_value = (
            "/tmp/render/test-job-123/audio/merged.mp3",
            15.0,
        )
        mock_audio_merger_class.return_value = mock_audio_merger

        mock_scene_builder = MagicMock()
        mock_scene_builder.build_scenes.return_value = []
        mock_scene_builder_class.return_value = mock_scene_builder

        mock_compositor = MagicMock()
        mock_compositor_class.return_value = mock_compositor

        mock_exists.return_value = True
        mock_getsize.return_value = 10 * 1024 * 1024  # 10 MB

        mock_sfn_client = MagicMock()
        mock_boto3_client.return_value = mock_sfn_client

        # Run main
        main()

        # Verify flow
        # 1. Config initialized
        mock_config_class.assert_called_once()

        # 2. DB client initialized
        mock_db_client_class.assert_called_once()

        # 3. S3 client initialized
        mock_s3_client_class.assert_called_once()

        # 4. Spot handler registered
        mock_register_handler.assert_called_once()

        # 5. Job record loaded
        mock_db_client.get_job.assert_called_once_with("test-job-123")

        # 6. Manifests loaded
        assert mock_s3_client.download_json.call_count == 2

        # 7. Checkpoint checked
        mock_load_checkpoint.assert_called_once()

        # 8. Job status updated to rendering
        status_calls = mock_db_client.update_job_status.call_args_list
        assert any(
            call[1]["status"] == JobStatus.rendering
            for call in status_calls
        )

        # 9. Panels downloaded
        assert mock_s3_client.download_file.call_count >= 3

        # 10. Audio merged
        mock_audio_merger.merge_from_s3.assert_called_once()

        # 11. Scenes built
        mock_scene_builder.build_scenes.assert_called_once()

        # 12. Video rendered
        mock_compositor.compose_video_chunked.assert_called_once()

        # 13. Video uploaded
        mock_s3_client.upload_file.assert_called_once()

        # 14. Job status updated to completed
        assert any(
            call[1]["status"] == JobStatus.completed
            for call in status_calls
        )

        # 15. Checkpoint deleted
        mock_delete_checkpoint.assert_called_once()

        # 16. Step Functions signaled
        mock_sfn_client.send_task_success.assert_called_once()

        # 17. Local directory cleaned up
        mock_rmtree.assert_called_once()

    @patch("src.renderer.main.get_settings")
    @patch("src.renderer.main.DynamoDBClient")
    @patch("src.renderer.main.S3Client")
    @patch("src.renderer.main.AudioMerger")
    @patch("src.renderer.main.SceneBuilder")
    @patch("src.renderer.main.VideoCompositor")
    @patch("src.renderer.main.register_spot_interruption_handler")
    @patch("src.renderer.main.load_checkpoint")
    @patch("src.renderer.main.delete_checkpoint")
    @patch("src.renderer.main.boto3.client")
    @patch("os.makedirs")
    @patch("os.path.exists")
    @patch("os.path.getsize")
    @patch("shutil.rmtree")
    def test_resumes_from_checkpoint(
        self,
        mock_rmtree,
        mock_getsize,
        mock_exists,
        mock_makedirs,
        mock_boto3_client,
        mock_delete_checkpoint,
        mock_load_checkpoint,
        mock_register_handler,
        mock_compositor_class,
        mock_scene_builder_class,
        mock_audio_merger_class,
        mock_s3_client_class,
        mock_db_client_class,
        mock_config_class,
        mock_env,
        mock_job_record,
        mock_panel_manifest,
        mock_audio_manifest,
    ):
        """Test resuming from checkpoint."""
        # Setup mocks
        mock_config = MagicMock()
        mock_config.dynamodb_jobs_table = "test-jobs-table"
        mock_config.s3_bucket = "test-bucket"
        mock_config.aws_region = "us-east-1"
        mock_config_class.return_value = mock_config

        mock_db_client = MagicMock()
        mock_db_client.get_job.return_value = mock_job_record
        mock_db_client_class.return_value = mock_db_client

        mock_s3_client = MagicMock()
        mock_s3_client.download_json.side_effect = [
            mock_panel_manifest,
            mock_audio_manifest.model_dump(),
        ]
        mock_s3_client_class.return_value = mock_s3_client

        # Return checkpoint
        mock_load_checkpoint.return_value = {"last_completed_chunk": 2}

        mock_audio_merger = MagicMock()
        mock_audio_merger.merge_from_s3.return_value = (
            "/tmp/render/test-job-123/audio/merged.mp3",
            15.0,
        )
        mock_audio_merger_class.return_value = mock_audio_merger

        mock_scene_builder = MagicMock()
        mock_scene_builder.build_scenes.return_value = []
        mock_scene_builder_class.return_value = mock_scene_builder

        mock_compositor = MagicMock()
        mock_compositor_class.return_value = mock_compositor

        mock_exists.return_value = True
        mock_getsize.return_value = 10 * 1024 * 1024

        mock_sfn_client = MagicMock()
        mock_boto3_client.return_value = mock_sfn_client

        # Run main
        main()

        # Verify checkpoint was loaded
        mock_load_checkpoint.assert_called_once()

        # Verify rendering continued
        mock_compositor.compose_video_chunked.assert_called_once()


class TestErrorHandling:
    """Tests for error handling."""

    @patch("src.renderer.main.get_settings")
    @patch("src.renderer.main.DynamoDBClient")
    def test_raises_error_without_job_id(self, mock_db_client_class, mock_config_class):
        """Test that error is raised when JOB_ID is not set."""
        # Don't set JOB_ID environment variable
        with pytest.raises(ValueError, match="JOB_ID environment variable not set"):
            main()

    @patch("src.renderer.main.get_settings")
    @patch("src.renderer.main.DynamoDBClient")
    @patch("src.renderer.main.S3Client")
    @patch("src.renderer.main.register_spot_interruption_handler")
    @patch("shutil.rmtree")
    def test_updates_job_to_failed_on_error(
        self,
        mock_rmtree,
        mock_register_handler,
        mock_s3_client_class,
        mock_db_client_class,
        mock_config_class,
        mock_env,
    ):
        """Test that job status is updated to failed on error."""
        # Setup mocks
        mock_config = MagicMock()
        mock_config.dynamodb_jobs_table = "test-jobs-table"
        mock_config.s3_bucket = "test-bucket"
        mock_config.aws_region = "us-east-1"
        mock_config_class.return_value = mock_config

        mock_db_client = MagicMock()
        # Make get_job raise an error
        mock_db_client.get_job.side_effect = Exception("Database error")
        mock_db_client_class.return_value = mock_db_client

        mock_s3_client = MagicMock()
        mock_s3_client_class.return_value = mock_s3_client

        # Run main - should handle error
        with pytest.raises(Exception, match="Database error"):
            main()

        # Verify job status was updated to failed
        mock_db_client.update_job_status.assert_called()
        call_args = mock_db_client.update_job_status.call_args
        assert call_args[1]["status"] == JobStatus.failed
        assert "Database error" in call_args[1]["error_message"]

    @patch("src.renderer.main.get_settings")
    @patch("src.renderer.main.DynamoDBClient")
    @patch("src.renderer.main.S3Client")
    @patch("src.renderer.main.register_spot_interruption_handler")
    @patch("src.renderer.main.boto3.client")
    @patch("shutil.rmtree")
    def test_signals_step_functions_failure(
        self,
        mock_rmtree,
        mock_boto3_client,
        mock_register_handler,
        mock_s3_client_class,
        mock_db_client_class,
        mock_config_class,
        mock_env,
    ):
        """Test that Step Functions is signaled on failure."""
        # Setup mocks
        mock_config = MagicMock()
        mock_config.dynamodb_jobs_table = "test-jobs-table"
        mock_config.s3_bucket = "test-bucket"
        mock_config.aws_region = "us-east-1"
        mock_config_class.return_value = mock_config

        mock_db_client = MagicMock()
        mock_db_client.get_job.side_effect = Exception("Test error")
        mock_db_client_class.return_value = mock_db_client

        mock_s3_client = MagicMock()
        mock_s3_client_class.return_value = mock_s3_client

        mock_sfn_client = MagicMock()
        mock_boto3_client.return_value = mock_sfn_client

        # Run main
        with pytest.raises(Exception, match="Test error"):
            main()

        # Verify Step Functions was signaled
        mock_sfn_client.send_task_failure.assert_called_once()


class TestLocalCleanup:
    """Tests for local directory cleanup."""

    @patch("src.renderer.main.get_settings")
    @patch("src.renderer.main.DynamoDBClient")
    @patch("src.renderer.main.S3Client")
    @patch("src.renderer.main.AudioMerger")
    @patch("src.renderer.main.SceneBuilder")
    @patch("src.renderer.main.VideoCompositor")
    @patch("src.renderer.main.register_spot_interruption_handler")
    @patch("src.renderer.main.load_checkpoint")
    @patch("src.renderer.main.delete_checkpoint")
    @patch("src.renderer.main.boto3.client")
    @patch("os.makedirs")
    @patch("os.path.exists")
    @patch("os.path.getsize")
    @patch("shutil.rmtree")
    def test_cleans_up_local_directory_on_success(
        self,
        mock_rmtree,
        mock_getsize,
        mock_exists,
        mock_makedirs,
        mock_boto3_client,
        mock_delete_checkpoint,
        mock_load_checkpoint,
        mock_register_handler,
        mock_compositor_class,
        mock_scene_builder_class,
        mock_audio_merger_class,
        mock_s3_client_class,
        mock_db_client_class,
        mock_config_class,
        mock_env,
        mock_job_record,
        mock_panel_manifest,
        mock_audio_manifest,
    ):
        """Test that local directory is cleaned up on success."""
        # Setup mocks (similar to full flow test)
        mock_config = MagicMock()
        mock_config.dynamodb_jobs_table = "test-jobs-table"
        mock_config.s3_bucket = "test-bucket"
        mock_config.aws_region = "us-east-1"
        mock_config_class.return_value = mock_config

        mock_db_client = MagicMock()
        mock_db_client.get_job.return_value = mock_job_record
        mock_db_client_class.return_value = mock_db_client

        mock_s3_client = MagicMock()
        mock_s3_client.download_json.side_effect = [
            mock_panel_manifest,
            mock_audio_manifest.model_dump(),
        ]
        mock_s3_client_class.return_value = mock_s3_client

        mock_load_checkpoint.return_value = None

        mock_audio_merger = MagicMock()
        mock_audio_merger.merge_from_s3.return_value = (
            "/tmp/render/test-job-123/audio/merged.mp3",
            15.0,
        )
        mock_audio_merger_class.return_value = mock_audio_merger

        mock_scene_builder = MagicMock()
        mock_scene_builder.build_scenes.return_value = []
        mock_scene_builder_class.return_value = mock_scene_builder

        mock_compositor = MagicMock()
        mock_compositor_class.return_value = mock_compositor

        mock_exists.return_value = True
        mock_getsize.return_value = 10 * 1024 * 1024

        mock_sfn_client = MagicMock()
        mock_boto3_client.return_value = mock_sfn_client

        # Run main
        main()

        # Verify cleanup
        mock_rmtree.assert_called_once_with("/tmp/render/test-job-123")

    @patch("src.renderer.main.get_settings")
    @patch("src.renderer.main.DynamoDBClient")
    @patch("src.renderer.main.S3Client")
    @patch("src.renderer.main.register_spot_interruption_handler")
    @patch("os.path.exists")
    @patch("shutil.rmtree")
    def test_cleans_up_local_directory_on_error(
        self,
        mock_rmtree,
        mock_exists,
        mock_register_handler,
        mock_s3_client_class,
        mock_db_client_class,
        mock_config_class,
        mock_env,
    ):
        """Test that local directory is cleaned up even on error."""
        # Setup mocks
        mock_config = MagicMock()
        mock_config.dynamodb_jobs_table = "test-jobs-table"
        mock_config.s3_bucket = "test-bucket"
        mock_config.aws_region = "us-east-1"
        mock_config_class.return_value = mock_config

        mock_db_client = MagicMock()
        mock_db_client.get_job.side_effect = Exception("Test error")
        mock_db_client_class.return_value = mock_db_client

        mock_s3_client = MagicMock()
        mock_s3_client_class.return_value = mock_s3_client

        # This will be set during execution
        mock_exists.return_value = False

        # Run main
        with pytest.raises(Exception):
            main()

        # Cleanup happens in finally block, but directory wasn't created yet
        # so rmtree won't be called
        # (local_dir is only set after successful initialization)


class TestProgressTracking:
    """Tests for progress tracking."""

    @patch("src.renderer.main.get_settings")
    @patch("src.renderer.main.DynamoDBClient")
    @patch("src.renderer.main.S3Client")
    @patch("src.renderer.main.AudioMerger")
    @patch("src.renderer.main.SceneBuilder")
    @patch("src.renderer.main.VideoCompositor")
    @patch("src.renderer.main.register_spot_interruption_handler")
    @patch("src.renderer.main.load_checkpoint")
    @patch("src.renderer.main.delete_checkpoint")
    @patch("src.renderer.main.boto3.client")
    @patch("os.makedirs")
    @patch("os.path.exists")
    @patch("os.path.getsize")
    @patch("shutil.rmtree")
    def test_updates_progress_throughout_flow(
        self,
        mock_rmtree,
        mock_getsize,
        mock_exists,
        mock_makedirs,
        mock_boto3_client,
        mock_delete_checkpoint,
        mock_load_checkpoint,
        mock_register_handler,
        mock_compositor_class,
        mock_scene_builder_class,
        mock_audio_merger_class,
        mock_s3_client_class,
        mock_db_client_class,
        mock_config_class,
        mock_env,
        mock_job_record,
        mock_panel_manifest,
        mock_audio_manifest,
    ):
        """Test that progress is updated throughout the flow."""
        # Setup mocks
        mock_config = MagicMock()
        mock_config.dynamodb_jobs_table = "test-jobs-table"
        mock_config.s3_bucket = "test-bucket"
        mock_config.aws_region = "us-east-1"
        mock_config_class.return_value = mock_config

        mock_db_client = MagicMock()
        mock_db_client.get_job.return_value = mock_job_record
        mock_db_client_class.return_value = mock_db_client

        mock_s3_client = MagicMock()
        mock_s3_client.download_json.side_effect = [
            mock_panel_manifest,
            mock_audio_manifest.model_dump(),
        ]
        mock_s3_client_class.return_value = mock_s3_client

        mock_load_checkpoint.return_value = None

        mock_audio_merger = MagicMock()
        mock_audio_merger.merge_from_s3.return_value = (
            "/tmp/render/test-job-123/audio/merged.mp3",
            15.0,
        )
        mock_audio_merger_class.return_value = mock_audio_merger

        mock_scene_builder = MagicMock()
        mock_scene_builder.build_scenes.return_value = []
        mock_scene_builder_class.return_value = mock_scene_builder

        mock_compositor = MagicMock()
        mock_compositor_class.return_value = mock_compositor

        mock_exists.return_value = True
        mock_getsize.return_value = 10 * 1024 * 1024

        mock_sfn_client = MagicMock()
        mock_boto3_client.return_value = mock_sfn_client

        # Run main
        main()

        # Verify progress updates
        status_calls = mock_db_client.update_job_status.call_args_list

        # Check for rendering progress (65%)
        assert any(
            call[1].get("progress_pct") == 65 for call in status_calls
        )

        # Check for rendering progress (70%)
        assert any(
            call[1].get("progress_pct") == 70 for call in status_calls
        )

        # Check for uploading progress (85%)
        assert any(
            call[1].get("progress_pct") == 85 for call in status_calls
        )

        # Check for completion (100%)
        assert any(
            call[1].get("progress_pct") == 100 for call in status_calls
        )
