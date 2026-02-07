"""Tests for TTS generation Lambda handler."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.common.models import (
    AudioManifest,
    AudioSegment,
    JobRecord,
    JobStatus,
    PipelineSettings,
    ScriptDocument,
    ScriptSegment,
)
from src.ttsgen.handler import handler


@pytest.fixture
def mock_settings():
    """Create mock settings."""
    settings = MagicMock()
    settings.aws_region = "ap-southeast-1"
    settings.s3_bucket = "test-bucket"
    return settings


@pytest.fixture
def sample_event():
    """Sample Lambda event."""
    return {
        "job_id": "job-123",
        "script_s3_key": "jobs/job-123/script.json",
    }


@pytest.fixture
def sample_event_with_offset():
    """Sample Lambda event with segment offset for continuation."""
    return {
        "job_id": "job-123",
        "script_s3_key": "jobs/job-123/script.json",
        "segment_offset": 100,
    }


@pytest.fixture
def sample_job_record():
    """Sample job record."""
    return JobRecord(
        job_id="job-123",
        manga_id="manga-456",
        manga_title="One Piece",
        status=JobStatus.tts,
    )


@pytest.fixture
def sample_pipeline_settings():
    """Sample pipeline settings with voice_id."""
    return PipelineSettings(
        voice_id="vi-VN-HoaiMyNeural",
        tone="exciting and dramatic",
        script_style="chapter_walkthrough",
    )


@pytest.fixture
def sample_script_document():
    """Sample script document with segments."""
    return ScriptDocument(
        job_id="job-123",
        manga_title="One Piece",
        segments=[
            ScriptSegment(
                chapter="1",
                text="Đây là chương đầu tiên của One Piece.",
                panel_start=0,
                panel_end=2,
            ),
            ScriptSegment(
                chapter="2",
                text="Chương hai tiếp tục câu chuyện phiêu lưu.",
                panel_start=3,
                panel_end=4,
            ),
            ScriptSegment(
                chapter="3",
                text="Chương ba đưa chúng ta vào cuộc phiêu lưu mới.",
                panel_start=5,
                panel_end=8,
            ),
        ],
    )


@pytest.fixture
def large_script_document():
    """Large script document that would require continuation."""
    segments = []
    for i in range(200):  # More segments than can fit in 12 minutes
        segments.append(
            ScriptSegment(
                chapter=str(i // 10 + 1),
                text=f"Đây là đoạn văn số {i}.",
                panel_start=i * 2,
                panel_end=i * 2 + 1,
            )
        )
    return ScriptDocument(
        job_id="job-123",
        manga_title="One Piece",
        segments=segments,
    )


@pytest.fixture
def sample_audio_manifest():
    """Sample audio manifest."""
    return AudioManifest(
        job_id="job-123",
        segments=[
            AudioSegment(
                index=0,
                s3_key="jobs/job-123/audio/0000.mp3",
                duration_seconds=3.5,
                chapter="1",
                panel_start=0,
                panel_end=2,
            ),
            AudioSegment(
                index=1,
                s3_key="jobs/job-123/audio/0001.mp3",
                duration_seconds=4.2,
                chapter="2",
                panel_start=3,
                panel_end=4,
            ),
            AudioSegment(
                index=2,
                s3_key="jobs/job-123/audio/0002.mp3",
                duration_seconds=3.8,
                chapter="3",
                panel_start=5,
                panel_end=8,
            ),
        ],
        total_duration_seconds=11.5,
    )


class TestHappyPath:
    """Tests for successful handler execution."""

    def test_handler_processes_all_segments_successfully(
        self,
        mock_settings,
        sample_event,
        sample_job_record,
        sample_pipeline_settings,
        sample_script_document,
        sample_audio_manifest,
    ):
        """Test that handler successfully processes all segments."""
        with patch("src.ttsgen.handler.get_settings") as mock_get_settings, \
             patch("src.ttsgen.handler.DynamoDBClient") as mock_db_class, \
             patch("src.ttsgen.handler.S3Client") as mock_s3_class, \
             patch("src.ttsgen.handler.EdgeTTSClient") as mock_tts_class, \
             patch("src.ttsgen.handler.TTSSegmentProcessor") as mock_processor_class, \
             patch("src.ttsgen.handler.asyncio.run") as mock_asyncio_run, \
             patch("src.ttsgen.handler.uuid.uuid4") as mock_uuid:

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
            mock_s3.download_json.return_value = sample_script_document.model_dump()
            mock_s3_class.return_value = mock_s3

            # Mock TTS client
            mock_tts = MagicMock()
            mock_tts_class.return_value = mock_tts

            # Mock segment processor
            mock_processor = MagicMock()
            mock_processor_class.return_value = mock_processor

            # Mock asyncio.run to return manifest
            mock_asyncio_run.return_value = sample_audio_manifest

            # Call handler
            result = handler(sample_event, context=None)

            # Verify TTS client initialized with correct voice_id
            mock_tts_class.assert_called_once_with(voice_id="vi-VN-HoaiMyNeural")

            # Verify segment processor initialized
            mock_processor_class.assert_called_once_with(
                tts_client=mock_tts,
                s3_client=mock_s3,
            )

            # Verify asyncio.run was called
            assert mock_asyncio_run.call_count == 1

            # Verify job status updated to rendering with 60% progress
            mock_db.update_job_status.assert_called_once_with(
                job_id="job-123",
                status=JobStatus.rendering,
                progress_pct=60,
            )

            # Verify result
            assert result["job_id"] == "job-123"
            assert result["audio_manifest_s3_key"] == "jobs/job-123/audio_manifest.json"
            assert result["total_duration_seconds"] == 11.5
            assert result["segments_processed"] == 3
            assert result["total_segments"] == 3
            assert result["continuation_needed"] is False

    def test_handler_loads_voice_id_from_settings(
        self,
        mock_settings,
        sample_event,
        sample_job_record,
        sample_script_document,
        sample_audio_manifest,
    ):
        """Test that handler loads voice_id from pipeline settings."""
        custom_settings = PipelineSettings(
            voice_id="vi-VN-NamMinhNeural",  # Different voice
            tone="dramatic",
            script_style="summary",
        )

        with patch("src.ttsgen.handler.get_settings") as mock_get_settings, \
             patch("src.ttsgen.handler.DynamoDBClient") as mock_db_class, \
             patch("src.ttsgen.handler.S3Client") as mock_s3_class, \
             patch("src.ttsgen.handler.EdgeTTSClient") as mock_tts_class, \
             patch("src.ttsgen.handler.TTSSegmentProcessor") as mock_processor_class, \
             patch("src.ttsgen.handler.asyncio.run") as mock_asyncio_run, \
             patch("src.ttsgen.handler.uuid.uuid4") as mock_uuid:

            mock_get_settings.return_value = mock_settings
            mock_uuid.return_value = MagicMock(__str__=lambda x: "correlation-id-123")

            # Mock DB client to return custom settings
            mock_db = MagicMock()
            mock_db.get_job.return_value = sample_job_record
            mock_db.get_settings.return_value = custom_settings
            mock_db_class.return_value = mock_db

            # Mock S3 client
            mock_s3 = MagicMock()
            mock_s3.download_json.return_value = sample_script_document.model_dump()
            mock_s3_class.return_value = mock_s3

            # Mock TTS components
            mock_tts = MagicMock()
            mock_tts_class.return_value = mock_tts
            mock_processor_class.return_value = MagicMock()
            mock_asyncio_run.return_value = sample_audio_manifest

            # Call handler
            handler(sample_event, context=None)

            # Verify TTS client initialized with custom voice_id
            mock_tts_class.assert_called_once_with(voice_id="vi-VN-NamMinhNeural")


class TestContinuationLogic:
    """Tests for continuation logic with long scripts."""

    def test_handler_sets_continuation_needed_for_large_script(
        self,
        mock_settings,
        sample_event,
        sample_job_record,
        sample_pipeline_settings,
        large_script_document,
    ):
        """Test that handler sets continuation_needed flag for large scripts."""
        with patch("src.ttsgen.handler.get_settings") as mock_get_settings, \
             patch("src.ttsgen.handler.DynamoDBClient") as mock_db_class, \
             patch("src.ttsgen.handler.S3Client") as mock_s3_class, \
             patch("src.ttsgen.handler.EdgeTTSClient") as mock_tts_class, \
             patch("src.ttsgen.handler.TTSSegmentProcessor") as mock_processor_class, \
             patch("src.ttsgen.handler.asyncio.run") as mock_asyncio_run, \
             patch("src.ttsgen.handler.uuid.uuid4") as mock_uuid, \
             patch("src.ttsgen.handler.PROCESSING_TIME_LIMIT_SECONDS", 600), \
             patch("src.ttsgen.handler.ESTIMATED_SECONDS_PER_SEGMENT", 5):

            mock_get_settings.return_value = mock_settings
            mock_uuid.return_value = MagicMock(__str__=lambda x: "correlation-id-123")

            # Mock DB client
            mock_db = MagicMock()
            mock_db.get_job.return_value = sample_job_record
            mock_db.get_settings.return_value = sample_pipeline_settings
            mock_db_class.return_value = mock_db

            # Mock S3 client
            mock_s3 = MagicMock()
            mock_s3.download_json.return_value = large_script_document.model_dump()
            mock_s3_class.return_value = mock_s3

            # Mock TTS components
            mock_tts_class.return_value = MagicMock()
            mock_processor_class.return_value = MagicMock()

            # Create partial manifest (120 segments processed)
            partial_manifest = AudioManifest(
                job_id="job-123",
                segments=[
                    AudioSegment(
                        index=i,
                        s3_key=f"jobs/job-123/audio/{i:04d}.mp3",
                        duration_seconds=3.0,
                        chapter=str(i // 10 + 1),
                        panel_start=i * 2,
                        panel_end=i * 2 + 1,
                    )
                    for i in range(120)
                ],
                total_duration_seconds=360.0,
            )
            mock_asyncio_run.return_value = partial_manifest

            # Call handler
            result = handler(sample_event, context=None)

            # Verify continuation is needed (200 total segments, only 120 processed)
            assert result["continuation_needed"] is True
            assert result["next_segment_offset"] == 120
            assert result["segments_processed"] == 120
            assert result["total_segments"] == 200

            # Verify job status is still tts (not rendering yet)
            calls = mock_db.update_job_status.call_args_list
            assert any(call[1]["status"] == JobStatus.tts for call in calls)

    def test_handler_processes_from_offset_on_continuation(
        self,
        mock_settings,
        sample_event_with_offset,
        sample_job_record,
        sample_pipeline_settings,
        large_script_document,
    ):
        """Test that handler processes from segment_offset on continuation."""
        with patch("src.ttsgen.handler.get_settings") as mock_get_settings, \
             patch("src.ttsgen.handler.DynamoDBClient") as mock_db_class, \
             patch("src.ttsgen.handler.S3Client") as mock_s3_class, \
             patch("src.ttsgen.handler.EdgeTTSClient") as mock_tts_class, \
             patch("src.ttsgen.handler.TTSSegmentProcessor") as mock_processor_class, \
             patch("src.ttsgen.handler.asyncio.run") as mock_asyncio_run, \
             patch("src.ttsgen.handler.uuid.uuid4") as mock_uuid:

            mock_get_settings.return_value = mock_settings
            mock_uuid.return_value = MagicMock(__str__=lambda x: "correlation-id-123")

            # Mock DB client
            mock_db = MagicMock()
            mock_db.get_job.return_value = sample_job_record
            mock_db.get_settings.return_value = sample_pipeline_settings
            mock_db_class.return_value = mock_db

            # Mock S3 client
            mock_s3 = MagicMock()
            mock_s3.download_json.side_effect = [
                large_script_document.model_dump(),  # First call: load script
                # Second call: load existing manifest
                AudioManifest(
                    job_id="job-123",
                    segments=[
                        AudioSegment(
                            index=i,
                            s3_key=f"jobs/job-123/audio/{i:04d}.mp3",
                            duration_seconds=3.0,
                            chapter=str(i // 10 + 1),
                            panel_start=i * 2,
                            panel_end=i * 2 + 1,
                        )
                        for i in range(100)
                    ],
                    total_duration_seconds=300.0,
                ).model_dump(),
            ]
            mock_s3_class.return_value = mock_s3

            # Mock TTS components
            mock_tts_class.return_value = MagicMock()
            mock_processor_class.return_value = MagicMock()

            # Mock final manifest after continuation
            final_manifest = AudioManifest(
                job_id="job-123",
                segments=[
                    AudioSegment(
                        index=i,
                        s3_key=f"jobs/job-123/audio/{i:04d}.mp3",
                        duration_seconds=3.0,
                        chapter=str(i // 10 + 1),
                        panel_start=i * 2,
                        panel_end=i * 2 + 1,
                    )
                    for i in range(200)
                ],
                total_duration_seconds=600.0,
            )
            mock_asyncio_run.return_value = final_manifest

            # Call handler with offset
            result = handler(sample_event_with_offset, context=None)

            # Verify existing manifest was loaded
            assert mock_s3.download_json.call_count == 2

            # Verify continuation completed
            assert result["continuation_needed"] is False
            assert result["total_segments"] == 200


class TestJobStatusUpdates:
    """Tests for job status updates."""

    def test_handler_updates_status_to_rendering_when_complete(
        self,
        mock_settings,
        sample_event,
        sample_job_record,
        sample_pipeline_settings,
        sample_script_document,
        sample_audio_manifest,
    ):
        """Test that handler updates job status to rendering when complete."""
        with patch("src.ttsgen.handler.get_settings") as mock_get_settings, \
             patch("src.ttsgen.handler.DynamoDBClient") as mock_db_class, \
             patch("src.ttsgen.handler.S3Client") as mock_s3_class, \
             patch("src.ttsgen.handler.EdgeTTSClient"), \
             patch("src.ttsgen.handler.TTSSegmentProcessor"), \
             patch("src.ttsgen.handler.asyncio.run") as mock_asyncio_run, \
             patch("src.ttsgen.handler.uuid.uuid4") as mock_uuid:

            mock_get_settings.return_value = mock_settings
            mock_uuid.return_value = MagicMock(__str__=lambda x: "correlation-id-123")

            # Mock DB client
            mock_db = MagicMock()
            mock_db.get_job.return_value = sample_job_record
            mock_db.get_settings.return_value = sample_pipeline_settings
            mock_db_class.return_value = mock_db

            # Mock S3 client
            mock_s3 = MagicMock()
            mock_s3.download_json.return_value = sample_script_document.model_dump()
            mock_s3_class.return_value = mock_s3

            # Mock processing
            mock_asyncio_run.return_value = sample_audio_manifest

            # Call handler
            handler(sample_event, context=None)

            # Verify job status updated to rendering with 60%
            mock_db.update_job_status.assert_called_once_with(
                job_id="job-123",
                status=JobStatus.rendering,
                progress_pct=60,
            )

    def test_handler_updates_status_to_failed_on_error(
        self,
        mock_settings,
        sample_event,
        sample_job_record,
        sample_pipeline_settings,
        sample_script_document,
    ):
        """Test that handler updates job status to failed on error."""
        with patch("src.ttsgen.handler.get_settings") as mock_get_settings, \
             patch("src.ttsgen.handler.DynamoDBClient") as mock_db_class, \
             patch("src.ttsgen.handler.S3Client") as mock_s3_class, \
             patch("src.ttsgen.handler.EdgeTTSClient"), \
             patch("src.ttsgen.handler.TTSSegmentProcessor"), \
             patch("src.ttsgen.handler.asyncio.run") as mock_asyncio_run, \
             patch("src.ttsgen.handler.uuid.uuid4") as mock_uuid:

            mock_get_settings.return_value = mock_settings
            mock_uuid.return_value = MagicMock(__str__=lambda x: "correlation-id-123")

            # Mock DB client
            mock_db = MagicMock()
            mock_db.get_job.return_value = sample_job_record
            mock_db.get_settings.return_value = sample_pipeline_settings
            mock_db_class.return_value = mock_db

            # Mock S3 client
            mock_s3 = MagicMock()
            mock_s3.download_json.return_value = sample_script_document.model_dump()
            mock_s3_class.return_value = mock_s3

            # Mock processing to raise error
            mock_asyncio_run.side_effect = Exception("TTS processing failed")

            # Call handler and expect exception
            with pytest.raises(Exception, match="TTS processing failed"):
                handler(sample_event, context=None)

            # Verify job status updated to failed
            mock_db.update_job_status.assert_called_once_with(
                job_id="job-123",
                status=JobStatus.failed,
                error_message="TTS processing failed",
            )


class TestErrorHandling:
    """Tests for error handling."""

    def test_handler_raises_error_if_job_not_found(
        self,
        mock_settings,
        sample_event,
        sample_pipeline_settings,
    ):
        """Test that handler raises error if job not found."""
        with patch("src.ttsgen.handler.get_settings") as mock_get_settings, \
             patch("src.ttsgen.handler.DynamoDBClient") as mock_db_class, \
             patch("src.ttsgen.handler.S3Client") as mock_s3_class, \
             patch("src.ttsgen.handler.uuid.uuid4") as mock_uuid:

            mock_get_settings.return_value = mock_settings
            mock_uuid.return_value = MagicMock(__str__=lambda x: "correlation-id-123")

            # Mock DB client to return None for job
            mock_db = MagicMock()
            mock_db.get_job.return_value = None
            mock_db.get_settings.return_value = sample_pipeline_settings
            mock_db_class.return_value = mock_db

            # Mock S3 client
            mock_s3_class.return_value = MagicMock()

            # Call handler and expect error
            with pytest.raises(ValueError, match="Job not found"):
                handler(sample_event, context=None)

    def test_handler_raises_error_if_script_not_found(
        self,
        mock_settings,
        sample_event,
        sample_job_record,
        sample_pipeline_settings,
    ):
        """Test that handler raises error if script not found in S3."""
        with patch("src.ttsgen.handler.get_settings") as mock_get_settings, \
             patch("src.ttsgen.handler.DynamoDBClient") as mock_db_class, \
             patch("src.ttsgen.handler.S3Client") as mock_s3_class, \
             patch("src.ttsgen.handler.uuid.uuid4") as mock_uuid:

            mock_get_settings.return_value = mock_settings
            mock_uuid.return_value = MagicMock(__str__=lambda x: "correlation-id-123")

            # Mock DB client
            mock_db = MagicMock()
            mock_db.get_job.return_value = sample_job_record
            mock_db.get_settings.return_value = sample_pipeline_settings
            mock_db_class.return_value = mock_db

            # Mock S3 client to raise error
            mock_s3 = MagicMock()
            mock_s3.download_json.side_effect = Exception("S3 object not found")
            mock_s3_class.return_value = mock_s3

            # Call handler and expect error
            with pytest.raises(Exception, match="S3 object not found"):
                handler(sample_event, context=None)

            # Verify job status updated to failed
            mock_db.update_job_status.assert_called_once_with(
                job_id="job-123",
                status=JobStatus.failed,
                error_message="S3 object not found",
            )


class TestEventValidation:
    """Tests for event validation."""

    def test_handler_accepts_event_without_offset(
        self,
        mock_settings,
        sample_event,
        sample_job_record,
        sample_pipeline_settings,
        sample_script_document,
        sample_audio_manifest,
    ):
        """Test that handler works with event without segment_offset."""
        with patch("src.ttsgen.handler.get_settings") as mock_get_settings, \
             patch("src.ttsgen.handler.DynamoDBClient") as mock_db_class, \
             patch("src.ttsgen.handler.S3Client") as mock_s3_class, \
             patch("src.ttsgen.handler.EdgeTTSClient"), \
             patch("src.ttsgen.handler.TTSSegmentProcessor"), \
             patch("src.ttsgen.handler.asyncio.run") as mock_asyncio_run, \
             patch("src.ttsgen.handler.uuid.uuid4") as mock_uuid:

            mock_get_settings.return_value = mock_settings
            mock_uuid.return_value = MagicMock(__str__=lambda x: "correlation-id-123")

            mock_db = MagicMock()
            mock_db.get_job.return_value = sample_job_record
            mock_db.get_settings.return_value = sample_pipeline_settings
            mock_db_class.return_value = mock_db

            mock_s3 = MagicMock()
            mock_s3.download_json.return_value = sample_script_document.model_dump()
            mock_s3_class.return_value = mock_s3

            mock_asyncio_run.return_value = sample_audio_manifest

            # Call handler (event has no segment_offset)
            result = handler(sample_event, context=None)

            # Should default to offset 0
            assert result["segments_processed"] == 3
            assert result["total_segments"] == 3
