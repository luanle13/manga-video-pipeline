"""Lambda handler for manual YouTube upload trigger."""

import os
import uuid
from typing import Any

from src.common.config import get_settings
from src.common.db import DynamoDBClient
from src.common.logging_config import set_correlation_id, setup_logger
from src.common.models import ChapterInfo, JobStatus, MangaInfo
from src.common.secrets import SecretsClient
from src.common.storage import S3Client
from src.uploader.metadata_generator import MetadataGenerator
from src.uploader.upload_client import (
    YouTubeQuotaError,
    YouTubeUploadClient,
    YouTubeUploadError,
)
from src.uploader.youtube_auth import YouTubeAuthError, YouTubeAuthManager

logger = setup_logger(__name__)


def handler(event: dict, context: Any) -> dict:
    """
    Lambda handler for manually triggering YouTube upload.

    This handler is invoked from the dashboard when a user approves a video
    for upload in manual review mode.

    Args:
        event: Lambda event containing job_id.
        context: Lambda context.

    Returns:
        Result dict with job_id and youtube_url on success.
    """
    # Generate correlation ID for request tracing
    correlation_id = str(uuid.uuid4())
    set_correlation_id(correlation_id)

    job_id = event.get("job_id")
    if not job_id:
        logger.error("Missing job_id in event")
        return {"error": "Missing job_id", "status": "error"}

    logger.info(
        "Manual YouTube upload triggered",
        extra={"job_id": job_id, "correlation_id": correlation_id},
    )

    local_video_path = None

    try:
        # Initialize configuration and clients
        settings = get_settings()
        db_client = DynamoDBClient(settings)
        s3_client = S3Client(settings)
        secrets_client = SecretsClient(region=settings.aws_region)

        # Load job record
        job_record = db_client.get_job(job_id)
        if not job_record:
            logger.error("Job not found", extra={"job_id": job_id})
            return {"error": f"Job {job_id} not found", "status": "error"}

        logger.info(
            "Job record loaded",
            extra={
                "job_id": job_id,
                "status": job_record.status,
                "manga_title": job_record.manga_title,
            },
        )

        # Verify job is in correct state
        if job_record.status not in [JobStatus.awaiting_review, JobStatus.uploading]:
            logger.error(
                "Job not in uploadable state",
                extra={"job_id": job_id, "status": job_record.status},
            )
            return {
                "error": f"Job not in uploadable state (current: {job_record.status})",
                "status": "error",
            }

        # Update status to uploading
        db_client.update_job_status(
            job_id=job_id,
            status=JobStatus.uploading,
            progress_pct=90,
        )

        # Load manga info from panel manifest
        panel_manifest_key = f"jobs/{job_id}/panel_manifest.json"
        logger.info(
            "Loading panel manifest",
            extra={"s3_key": panel_manifest_key},
        )
        panel_manifest = s3_client.download_json(panel_manifest_key)
        if not panel_manifest:
            raise ValueError(f"Panel manifest not found at {panel_manifest_key}")

        manga_info = _reconstruct_manga_info(panel_manifest)

        # Download video from S3 to /tmp
        video_s3_key = f"jobs/{job_id}/video.mp4"
        local_video_path = f"/tmp/{job_id}_video.mp4"

        logger.info(
            "Downloading video from S3",
            extra={"s3_key": video_s3_key},
        )
        s3_client.download_file(video_s3_key, local_video_path)

        file_size_mb = os.path.getsize(local_video_path) / (1024 * 1024)
        logger.info(
            "Video downloaded",
            extra={"local_path": local_video_path, "size_mb": round(file_size_mb, 2)},
        )

        # Authenticate with YouTube
        logger.info("Authenticating with YouTube")
        youtube_auth = YouTubeAuthManager(
            secrets_client=secrets_client,
            secret_name=settings.youtube_secret_name,
        )

        try:
            youtube_service = youtube_auth.get_authenticated_service()
            logger.info("YouTube authentication successful")
        except YouTubeAuthError as e:
            logger.error("YouTube authentication failed", extra={"error": str(e)})
            db_client.update_job_status(
                job_id=job_id,
                status=JobStatus.failed,
                error_message=f"YouTube authentication failed: {str(e)}",
            )
            return {"error": "YouTube authentication failed", "status": "error"}

        # Generate metadata
        logger.info("Generating YouTube metadata")
        metadata_generator = MetadataGenerator()
        metadata = metadata_generator.generate_metadata(manga_info, job_record)

        logger.info(
            "Metadata generated",
            extra={"title": metadata.get("title")},
        )

        # Upload video
        logger.info("Starting YouTube upload")
        upload_client = YouTubeUploadClient(youtube_service)

        try:
            youtube_url = upload_client.upload_video(local_video_path, metadata)
            logger.info(
                "Video uploaded successfully",
                extra={"youtube_url": youtube_url},
            )
        except YouTubeQuotaError as e:
            logger.error("YouTube quota exceeded", extra={"error": str(e)})
            db_client.update_job_status(
                job_id=job_id,
                status=JobStatus.failed,
                error_message="YouTube quota exceeded, try again tomorrow",
            )
            return {"error": "YouTube quota exceeded", "status": "error"}
        except YouTubeUploadError as e:
            logger.error("YouTube upload failed", extra={"error": str(e)})
            db_client.update_job_status(
                job_id=job_id,
                status=JobStatus.failed,
                error_message=f"YouTube upload failed: {str(e)}",
            )
            return {"error": "YouTube upload failed", "status": "error"}

        # Update job to completed
        db_client.update_job_status(
            job_id=job_id,
            status=JobStatus.completed,
            youtube_url=youtube_url,
            progress_pct=100,
        )

        logger.info(
            "Manual YouTube upload completed successfully",
            extra={"job_id": job_id, "youtube_url": youtube_url},
        )

        return {
            "job_id": job_id,
            "youtube_url": youtube_url,
            "status": "success",
        }

    except Exception as e:
        logger.error(
            "Manual YouTube upload failed",
            extra={"job_id": job_id, "error": str(e)},
            exc_info=True,
        )

        # Update job status to failed
        try:
            settings = get_settings()
            db_client = DynamoDBClient(settings)
            db_client.update_job_status(
                job_id=job_id,
                status=JobStatus.failed,
                error_message=str(e),
            )
        except Exception as update_error:
            logger.error(
                "Failed to update job status",
                extra={"error": str(update_error)},
            )

        return {"error": str(e), "status": "error"}

    finally:
        # Clean up local video file
        if local_video_path and os.path.exists(local_video_path):
            try:
                os.unlink(local_video_path)
                logger.info("Local video file cleaned up")
            except Exception as cleanup_error:
                logger.warning(
                    "Failed to clean up local video",
                    extra={"error": str(cleanup_error)},
                )


def _reconstruct_manga_info(panel_manifest: dict) -> MangaInfo:
    """
    Reconstruct MangaInfo from panel manifest.

    Args:
        panel_manifest: Panel manifest with manga metadata.

    Returns:
        MangaInfo object.
    """
    # Reconstruct chapters
    chapters = []
    for chapter_data in panel_manifest.get("chapters", []):
        chapter_info = ChapterInfo(
            chapter_id=chapter_data.get("chapter_id", ""),
            title=chapter_data.get("title", ""),
            chapter_number=chapter_data.get("chapter_number"),
            page_urls=[],
        )
        chapters.append(chapter_info)

    # Create MangaInfo
    manga_info = MangaInfo(
        manga_id=panel_manifest.get("manga_id", ""),
        title=panel_manifest.get("manga_title", ""),
        description=panel_manifest.get("description", ""),
        genres=panel_manifest.get("genres", []),
        cover_url=panel_manifest.get("cover_url"),
        chapters=chapters,
    )

    return manga_info
