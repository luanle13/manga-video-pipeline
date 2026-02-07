"""Unit tests for YouTube upload client."""

import time
from unittest.mock import MagicMock, call, patch

import pytest
from googleapiclient.errors import HttpError

from src.uploader.upload_client import (
    YouTubeQuotaError,
    YouTubeUploadClient,
    YouTubeUploadError,
)


@pytest.fixture
def mock_youtube_service():
    """Mock YouTube service."""
    return MagicMock()


@pytest.fixture
def upload_client(mock_youtube_service):
    """YouTube upload client instance."""
    return YouTubeUploadClient(mock_youtube_service)


@pytest.fixture
def sample_metadata():
    """Sample video metadata."""
    return {
        "title": "Test Video Title",
        "description": "Test video description",
        "tags": ["test", "video"],
        "category_id": "24",
        "default_language": "vi",
        "privacy_status": "public",
    }


class TestYouTubeUploadClientInitialization:
    """Tests for YouTubeUploadClient initialization."""

    def test_initializes_successfully(self, mock_youtube_service):
        """Test successful initialization."""
        client = YouTubeUploadClient(mock_youtube_service)

        assert client.youtube_service == mock_youtube_service
        assert client.CHUNK_SIZE == 10 * 1024 * 1024
        assert client.MAX_RETRIES == 5


class TestUploadVideo:
    """Tests for video upload."""

    @patch("src.uploader.upload_client.MediaFileUpload")
    def test_uploads_video_successfully(
        self,
        mock_media_class,
        upload_client,
        mock_youtube_service,
        sample_metadata,
    ):
        """Test successful video upload."""
        # Setup mocks
        mock_media = MagicMock()
        mock_media_class.return_value = mock_media

        mock_insert_request = MagicMock()
        # Simulate upload completion in one chunk
        mock_insert_request.next_chunk.return_value = (None, {"id": "test-video-123"})

        mock_youtube_service.videos().insert.return_value = mock_insert_request

        # Execute
        video_url = upload_client.upload_video("/fake/video.mp4", sample_metadata)

        # Verify
        assert video_url == "https://youtube.com/watch?v=test-video-123"
        mock_youtube_service.videos().insert.assert_called_once()
        mock_insert_request.next_chunk.assert_called_once()

    @patch("src.uploader.upload_client.MediaFileUpload")
    def test_creates_correct_request_structure(
        self,
        mock_media_class,
        upload_client,
        mock_youtube_service,
        sample_metadata,
    ):
        """Test that request is created with correct structure."""
        # Setup mocks
        mock_media = MagicMock()
        mock_media_class.return_value = mock_media

        mock_insert_request = MagicMock()
        mock_insert_request.next_chunk.return_value = (None, {"id": "test-video-123"})
        mock_youtube_service.videos().insert.return_value = mock_insert_request

        # Execute
        upload_client.upload_video("/fake/video.mp4", sample_metadata)

        # Verify request structure
        call_args = mock_youtube_service.videos().insert.call_args
        assert call_args[1]["part"] == "snippet,status"

        body = call_args[1]["body"]
        assert body["snippet"]["title"] == "Test Video Title"
        assert body["snippet"]["description"] == "Test video description"
        assert body["snippet"]["tags"] == ["test", "video"]
        assert body["snippet"]["categoryId"] == "24"
        assert body["snippet"]["defaultLanguage"] == "vi"
        assert body["status"]["privacyStatus"] == "public"

    @patch("src.uploader.upload_client.MediaFileUpload")
    def test_uses_resumable_upload(
        self,
        mock_media_class,
        upload_client,
        mock_youtube_service,
        sample_metadata,
    ):
        """Test that resumable upload is enabled."""
        # Setup mocks
        mock_media = MagicMock()
        mock_media_class.return_value = mock_media

        mock_insert_request = MagicMock()
        mock_insert_request.next_chunk.return_value = (None, {"id": "test-video-123"})
        mock_youtube_service.videos().insert.return_value = mock_insert_request

        # Execute
        upload_client.upload_video("/fake/video.mp4", sample_metadata)

        # Verify MediaFileUpload was called with resumable=True
        mock_media_class.assert_called_once()
        call_kwargs = mock_media_class.call_args[1]
        assert call_kwargs["resumable"] is True
        assert call_kwargs["chunksize"] == 10 * 1024 * 1024

    @patch("src.uploader.upload_client.MediaFileUpload")
    def test_logs_upload_progress(
        self,
        mock_media_class,
        upload_client,
        mock_youtube_service,
        sample_metadata,
    ):
        """Test that upload progress is logged."""
        # Setup mocks
        mock_media = MagicMock()
        mock_media_class.return_value = mock_media

        # Mock progress through multiple chunks
        mock_status_1 = MagicMock()
        mock_status_1.progress.return_value = 0.33

        mock_status_2 = MagicMock()
        mock_status_2.progress.return_value = 0.66

        mock_insert_request = MagicMock()
        mock_insert_request.next_chunk.side_effect = [
            (mock_status_1, None),
            (mock_status_2, None),
            (None, {"id": "test-video-123"}),
        ]
        mock_youtube_service.videos().insert.return_value = mock_insert_request

        # Execute
        upload_client.upload_video("/fake/video.mp4", sample_metadata)

        # Verify next_chunk was called multiple times
        assert mock_insert_request.next_chunk.call_count == 3


class TestUploadRetry:
    """Tests for upload retry logic."""

    @patch("src.uploader.upload_client.MediaFileUpload")
    @patch("src.uploader.upload_client.time.sleep")
    def test_retries_on_500_error(
        self,
        mock_sleep,
        mock_media_class,
        upload_client,
        mock_youtube_service,
        sample_metadata,
    ):
        """Test retry on HTTP 500 error."""
        # Setup mocks
        mock_media = MagicMock()
        mock_media_class.return_value = mock_media

        # Create HttpError for 500
        http_error = HttpError(
            resp=MagicMock(status=500),
            content=b"Internal Server Error",
        )

        mock_insert_request = MagicMock()
        # Fail once, then succeed
        mock_insert_request.next_chunk.side_effect = [
            http_error,
            (None, {"id": "test-video-123"}),
        ]
        mock_youtube_service.videos().insert.return_value = mock_insert_request

        # Execute
        video_url = upload_client.upload_video("/fake/video.mp4", sample_metadata)

        # Verify success after retry
        assert video_url == "https://youtube.com/watch?v=test-video-123"
        assert mock_insert_request.next_chunk.call_count == 2
        mock_sleep.assert_called_once()

    @patch("src.uploader.upload_client.MediaFileUpload")
    @patch("src.uploader.upload_client.time.sleep")
    def test_retries_on_503_error(
        self,
        mock_sleep,
        mock_media_class,
        upload_client,
        mock_youtube_service,
        sample_metadata,
    ):
        """Test retry on HTTP 503 error."""
        # Setup mocks
        mock_media = MagicMock()
        mock_media_class.return_value = mock_media

        http_error = HttpError(
            resp=MagicMock(status=503),
            content=b"Service Unavailable",
        )

        mock_insert_request = MagicMock()
        mock_insert_request.next_chunk.side_effect = [
            http_error,
            (None, {"id": "test-video-123"}),
        ]
        mock_youtube_service.videos().insert.return_value = mock_insert_request

        # Execute
        upload_client.upload_video("/fake/video.mp4", sample_metadata)

        # Verify retry happened
        assert mock_insert_request.next_chunk.call_count == 2

    @patch("src.uploader.upload_client.MediaFileUpload")
    @patch("src.uploader.upload_client.time.sleep")
    def test_retries_on_rate_limit(
        self,
        mock_sleep,
        mock_media_class,
        upload_client,
        mock_youtube_service,
        sample_metadata,
    ):
        """Test retry on rate limit (429)."""
        # Setup mocks
        mock_media = MagicMock()
        mock_media_class.return_value = mock_media

        http_error = HttpError(
            resp=MagicMock(status=429),
            content=b"Rate Limit Exceeded",
        )

        mock_insert_request = MagicMock()
        mock_insert_request.next_chunk.side_effect = [
            http_error,
            (None, {"id": "test-video-123"}),
        ]
        mock_youtube_service.videos().insert.return_value = mock_insert_request

        # Execute
        upload_client.upload_video("/fake/video.mp4", sample_metadata)

        # Verify retry happened
        assert mock_insert_request.next_chunk.call_count == 2

    @patch("src.uploader.upload_client.MediaFileUpload")
    @patch("src.uploader.upload_client.time.sleep")
    def test_exponential_backoff(
        self,
        mock_sleep,
        mock_media_class,
        upload_client,
        mock_youtube_service,
        sample_metadata,
    ):
        """Test exponential backoff timing."""
        # Setup mocks
        mock_media = MagicMock()
        mock_media_class.return_value = mock_media

        http_error = HttpError(
            resp=MagicMock(status=500),
            content=b"Internal Server Error",
        )

        mock_insert_request = MagicMock()
        # Fail 3 times, then succeed
        mock_insert_request.next_chunk.side_effect = [
            http_error,
            http_error,
            http_error,
            (None, {"id": "test-video-123"}),
        ]
        mock_youtube_service.videos().insert.return_value = mock_insert_request

        # Execute
        upload_client.upload_video("/fake/video.mp4", sample_metadata)

        # Verify exponential backoff: 1s, 2s, 4s
        sleep_calls = [call[0][0] for call in mock_sleep.call_args_list]
        assert sleep_calls == [1, 2, 4]

    @patch("src.uploader.upload_client.MediaFileUpload")
    @patch("src.uploader.upload_client.time.sleep")
    def test_fails_after_max_retries(
        self,
        mock_sleep,
        mock_media_class,
        upload_client,
        mock_youtube_service,
        sample_metadata,
    ):
        """Test failure after maximum retries exceeded."""
        # Setup mocks
        mock_media = MagicMock()
        mock_media_class.return_value = mock_media

        http_error = HttpError(
            resp=MagicMock(status=500),
            content=b"Internal Server Error",
        )

        mock_insert_request = MagicMock()
        # Keep failing
        mock_insert_request.next_chunk.side_effect = http_error
        mock_youtube_service.videos().insert.return_value = mock_insert_request

        # Execute & Verify
        with pytest.raises(YouTubeUploadError, match="failed after 5 retries"):
            upload_client.upload_video("/fake/video.mp4", sample_metadata)

        # Should have tried 6 times (initial + 5 retries)
        assert mock_insert_request.next_chunk.call_count == 6


class TestQuotaHandling:
    """Tests for quota error handling."""

    @patch("src.uploader.upload_client.MediaFileUpload")
    def test_raises_quota_error_on_quota_exceeded(
        self,
        mock_media_class,
        upload_client,
        mock_youtube_service,
        sample_metadata,
    ):
        """Test that quota error is raised on quota exceeded."""
        # Setup mocks
        mock_media = MagicMock()
        mock_media_class.return_value = mock_media

        http_error = HttpError(
            resp=MagicMock(status=403),
            content=b'{"error": {"errors": [{"reason": "quotaExceeded"}]}}',
        )

        mock_insert_request = MagicMock()
        mock_insert_request.next_chunk.side_effect = http_error
        mock_youtube_service.videos().insert.return_value = mock_insert_request

        # Execute & Verify
        with pytest.raises(YouTubeQuotaError, match="quota exceeded"):
            upload_client.upload_video("/fake/video.mp4", sample_metadata)

    @patch("src.uploader.upload_client.MediaFileUpload")
    def test_does_not_retry_quota_error(
        self,
        mock_media_class,
        upload_client,
        mock_youtube_service,
        sample_metadata,
    ):
        """Test that quota errors are not retried."""
        # Setup mocks
        mock_media = MagicMock()
        mock_media_class.return_value = mock_media

        http_error = HttpError(
            resp=MagicMock(status=403),
            content=b'{"error": {"message": "quota exceeded"}}',
        )

        mock_insert_request = MagicMock()
        mock_insert_request.next_chunk.side_effect = http_error
        mock_youtube_service.videos().insert.return_value = mock_insert_request

        # Execute & Verify
        with pytest.raises(YouTubeQuotaError):
            upload_client.upload_video("/fake/video.mp4", sample_metadata)

        # Should only try once (no retries)
        assert mock_insert_request.next_chunk.call_count == 1


class TestNonRetryableErrors:
    """Tests for non-retryable errors."""

    @patch("src.uploader.upload_client.MediaFileUpload")
    def test_does_not_retry_400_error(
        self,
        mock_media_class,
        upload_client,
        mock_youtube_service,
        sample_metadata,
    ):
        """Test that 400 errors are not retried."""
        # Setup mocks
        mock_media = MagicMock()
        mock_media_class.return_value = mock_media

        http_error = HttpError(
            resp=MagicMock(status=400),
            content=b"Bad Request",
        )

        mock_insert_request = MagicMock()
        mock_insert_request.next_chunk.side_effect = http_error
        mock_youtube_service.videos().insert.return_value = mock_insert_request

        # Execute & Verify
        with pytest.raises(YouTubeUploadError, match="HTTP 400"):
            upload_client.upload_video("/fake/video.mp4", sample_metadata)

        # Should only try once (no retries)
        assert mock_insert_request.next_chunk.call_count == 1

    @patch("src.uploader.upload_client.MediaFileUpload")
    def test_raises_error_on_missing_video_id(
        self,
        mock_media_class,
        upload_client,
        mock_youtube_service,
        sample_metadata,
    ):
        """Test error when response doesn't contain video ID."""
        # Setup mocks
        mock_media = MagicMock()
        mock_media_class.return_value = mock_media

        mock_insert_request = MagicMock()
        # Response without video ID
        mock_insert_request.next_chunk.return_value = (None, {})
        mock_youtube_service.videos().insert.return_value = mock_insert_request

        # Execute & Verify
        with pytest.raises(YouTubeUploadError, match="no video ID"):
            upload_client.upload_video("/fake/video.mp4", sample_metadata)


class TestCheckQuotaAvailable:
    """Tests for quota availability check."""

    def test_returns_true_when_quota_available(
        self,
        upload_client,
        mock_youtube_service,
    ):
        """Test that True is returned when quota is available."""
        # Setup mock
        mock_channels = MagicMock()
        mock_list = MagicMock()
        mock_list.execute.return_value = {"items": [{"id": "channel-123"}]}
        mock_channels.list.return_value = mock_list
        mock_youtube_service.channels.return_value = mock_channels

        # Execute
        result = upload_client.check_quota_available()

        # Verify
        assert result is True
        mock_channels.list.assert_called_once_with(part="id", mine=True)

    def test_returns_false_when_quota_exceeded(
        self,
        upload_client,
        mock_youtube_service,
    ):
        """Test that False is returned when quota is exceeded."""
        # Setup mock
        http_error = HttpError(
            resp=MagicMock(status=403),
            content=b'{"error": {"errors": [{"reason": "quotaExceeded"}]}}',
        )

        mock_channels = MagicMock()
        mock_list = MagicMock()
        mock_list.execute.side_effect = http_error
        mock_channels.list.return_value = mock_list
        mock_youtube_service.channels.return_value = mock_channels

        # Execute
        result = upload_client.check_quota_available()

        # Verify
        assert result is False

    def test_returns_true_on_other_errors(
        self,
        upload_client,
        mock_youtube_service,
    ):
        """Test that True is returned on non-quota errors (assume available)."""
        # Setup mock
        http_error = HttpError(
            resp=MagicMock(status=500),
            content=b"Internal Server Error",
        )

        mock_channels = MagicMock()
        mock_list = MagicMock()
        mock_list.execute.side_effect = http_error
        mock_channels.list.return_value = mock_list
        mock_youtube_service.channels.return_value = mock_channels

        # Execute
        result = upload_client.check_quota_available()

        # Verify - assume quota is available on other errors
        assert result is True


class TestRequestCreation:
    """Tests for request creation."""

    @patch("src.uploader.upload_client.MediaFileUpload")
    def test_handles_missing_metadata_fields(
        self,
        mock_media_class,
        upload_client,
        mock_youtube_service,
    ):
        """Test handling of missing metadata fields with defaults."""
        # Setup mocks
        mock_media = MagicMock()
        mock_media_class.return_value = mock_media

        mock_insert_request = MagicMock()
        mock_insert_request.next_chunk.return_value = (None, {"id": "test-video-123"})
        mock_youtube_service.videos().insert.return_value = mock_insert_request

        # Execute with minimal metadata
        upload_client.upload_video("/fake/video.mp4", {})

        # Verify defaults are used
        call_args = mock_youtube_service.videos().insert.call_args
        body = call_args[1]["body"]

        assert body["snippet"]["title"] == "Untitled Video"
        assert body["snippet"]["description"] == ""
        assert body["snippet"]["tags"] == []
        assert body["snippet"]["categoryId"] == "24"
        assert body["status"]["privacyStatus"] == "public"
