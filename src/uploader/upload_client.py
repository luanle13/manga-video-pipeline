"""YouTube resumable upload client for large video files."""

import time
from typing import Any

from googleapiclient.discovery import Resource
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload

from src.common.logging_config import setup_logger

logger = setup_logger(__name__)


class YouTubeUploadError(Exception):
    """Raised when YouTube upload fails."""

    pass


class YouTubeQuotaError(Exception):
    """Raised when YouTube quota is exceeded."""

    pass


class YouTubeUploadClient:
    """Client for uploading videos to YouTube with resumable uploads."""

    # Chunk size for resumable uploads (10MB)
    CHUNK_SIZE = 10 * 1024 * 1024

    # Retry configuration
    MAX_RETRIES = 5
    INITIAL_BACKOFF = 1  # seconds

    def __init__(self, youtube_service: Resource) -> None:
        """
        Initialize the YouTube upload client.

        Args:
            youtube_service: Authenticated YouTube API service.
        """
        self.youtube_service = youtube_service

        logger.info("YouTubeUploadClient initialized")

    def upload_video(self, file_path: str, metadata: dict) -> str:
        """
        Upload a video to YouTube using resumable upload.

        Args:
            file_path: Path to the video file.
            metadata: Video metadata dict with:
                - title: Video title
                - description: Video description
                - tags: List of tags
                - category_id: YouTube category ID
                - default_language: Language code
                - privacy_status: Privacy setting (public/private/unlisted)

        Returns:
            YouTube video URL (https://youtube.com/watch?v={video_id}).

        Raises:
            YouTubeUploadError: If upload fails after retries.
            YouTubeQuotaError: If quota is exceeded.
        """
        logger.info(
            "Starting YouTube video upload",
            extra={
                "file_path": file_path,
                "title": metadata.get("title"),
            },
        )

        start_time = time.time()

        # Create video insert request body
        body = {
            "snippet": {
                "title": metadata.get("title", "Untitled Video"),
                "description": metadata.get("description", ""),
                "tags": metadata.get("tags", []),
                "categoryId": metadata.get("category_id", "24"),
                "defaultLanguage": metadata.get("default_language", "vi"),
            },
            "status": {
                "privacyStatus": metadata.get("privacy_status", "public"),
            },
        }

        # Create MediaFileUpload for resumable upload
        media = MediaFileUpload(
            file_path,
            mimetype="video/*",
            resumable=True,
            chunksize=self.CHUNK_SIZE,
        )

        # Create insert request
        try:
            insert_request = self.youtube_service.videos().insert(
                part="snippet,status",
                body=body,
                media_body=media,
            )
        except Exception as e:
            logger.error(
                "Failed to create video insert request",
                extra={"error": str(e)},
                exc_info=True,
            )
            raise YouTubeUploadError("Failed to create upload request") from e

        # Execute upload with retry logic
        video_id = self._execute_resumable_upload(insert_request)

        # Calculate upload stats
        elapsed_time = time.time() - start_time
        elapsed_minutes = elapsed_time / 60

        logger.info(
            "Video upload complete",
            extra={
                "video_id": video_id,
                "elapsed_time_minutes": round(elapsed_minutes, 2),
            },
        )

        # Return YouTube URL
        video_url = f"https://youtube.com/watch?v={video_id}"
        return video_url

    def _execute_resumable_upload(self, insert_request: Any) -> str:
        """
        Execute resumable upload with retry logic.

        Args:
            insert_request: YouTube API insert request.

        Returns:
            Video ID of uploaded video.

        Raises:
            YouTubeUploadError: If upload fails after all retries.
            YouTubeQuotaError: If quota is exceeded.
        """
        response = None
        retry_count = 0
        backoff = self.INITIAL_BACKOFF

        while response is None:
            try:
                status, response = insert_request.next_chunk()

                if status:
                    # Log progress
                    progress_pct = int(status.progress() * 100)
                    logger.info(
                        f"Upload {progress_pct}% complete",
                        extra={"progress_pct": progress_pct},
                    )

            except HttpError as e:
                # Check for quota errors
                if e.resp.status == 403:
                    error_content = str(e.content)
                    if "quotaExceeded" in error_content or "quota" in error_content.lower():
                        logger.error(
                            "YouTube quota exceeded",
                            extra={"status": e.resp.status},
                        )
                        raise YouTubeQuotaError(
                            "YouTube API quota exceeded. Upload cannot proceed."
                        ) from e

                # Check for retryable errors (5xx or rate limit)
                if e.resp.status in [500, 502, 503, 504] or e.resp.status == 429:
                    if retry_count >= self.MAX_RETRIES:
                        logger.error(
                            "Upload failed after maximum retries",
                            extra={
                                "retry_count": retry_count,
                                "status": e.resp.status,
                            },
                        )
                        raise YouTubeUploadError(
                            f"Upload failed after {self.MAX_RETRIES} retries"
                        ) from e

                    # Exponential backoff
                    wait_time = backoff * (2 ** retry_count)
                    logger.warning(
                        f"Upload error (HTTP {e.resp.status}), retrying in {wait_time}s",
                        extra={
                            "retry_count": retry_count + 1,
                            "max_retries": self.MAX_RETRIES,
                            "status": e.resp.status,
                            "wait_time": wait_time,
                        },
                    )

                    time.sleep(wait_time)
                    retry_count += 1

                else:
                    # Non-retryable error
                    logger.error(
                        "Upload failed with non-retryable error",
                        extra={"status": e.resp.status, "error": str(e)},
                        exc_info=True,
                    )
                    raise YouTubeUploadError(
                        f"Upload failed with HTTP {e.resp.status}"
                    ) from e

            except Exception as e:
                logger.error(
                    "Unexpected error during upload",
                    extra={"error": str(e)},
                    exc_info=True,
                )
                raise YouTubeUploadError("Upload failed with unexpected error") from e

        # Extract video ID from response
        if response and "id" in response:
            video_id = response["id"]
            logger.info("Upload successful", extra={"video_id": video_id})
            return video_id
        else:
            logger.error("No video ID in upload response")
            raise YouTubeUploadError("Upload completed but no video ID returned")

    def check_quota_available(self) -> bool:
        """
        Check if YouTube API quota is available.

        Makes a lightweight API call to verify quota availability.
        If quota is exceeded, returns False.

        Returns:
            True if quota is available, False if exceeded.
        """
        logger.info("Checking YouTube API quota availability")

        try:
            # Make a lightweight API call (channels.list costs 1 unit)
            request = self.youtube_service.channels().list(
                part="id",
                mine=True,
            )

            request.execute()

            logger.info("YouTube API quota check passed")
            return True

        except HttpError as e:
            # Check for quota errors
            if e.resp.status == 403:
                error_content = str(e.content)
                if "quotaExceeded" in error_content or "quota" in error_content.lower():
                    logger.warning(
                        "YouTube API quota exceeded",
                        extra={"status": e.resp.status},
                    )
                    return False

            # Other errors - log but assume quota is available
            logger.warning(
                "Quota check failed with unexpected error",
                extra={"status": e.resp.status, "error": str(e)},
            )
            return True

        except Exception as e:
            logger.warning(
                "Quota check failed with unexpected error",
                extra={"error": str(e)},
            )
            # Assume quota is available if check fails for other reasons
            return True
