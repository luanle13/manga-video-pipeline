"""Main entry point for the YouTube uploader running on EC2 Spot instances."""

import os

import boto3

from src.common.config import get_settings
from src.common.db import DynamoDBClient
from src.common.logging_config import setup_logger
from src.common.models import JobRecord, JobStatus, MangaInfo
from src.common.secrets import SecretsClient
from src.common.storage import S3Client
from src.uploader.metadata_generator import MetadataGenerator
from src.uploader.upload_client import YouTubeQuotaError, YouTubeUploadClient, YouTubeUploadError
from src.uploader.youtube_auth import YouTubeAuthManager, YouTubeAuthError

logger = setup_logger(__name__)


def main() -> None:
    """
    Main entry point for the YouTube uploader.

    Orchestrates the video upload process:
    1. Load job and video file
    2. Authenticate with YouTube
    3. Generate metadata
    4. Upload video
    5. Update job status
    6. Trigger cleanup
    """
    job_id = None
    local_video_path = None

    try:
        # Step 1: Read job_id from environment
        job_id = os.environ.get("JOB_ID")
        if not job_id:
            raise ValueError("JOB_ID environment variable not set")

        logger.info(
            "Starting YouTube uploader",
            extra={"job_id": job_id},
        )

        # Step 2: Initialize config, logger, DB, S3, Secrets
        logger.info("Initializing components")
        config = get_settings()
        db_client = DynamoDBClient(
            table_name=config.dynamodb_jobs_table,
            region=config.aws_region,
        )
        s3_client = S3Client(
            bucket_name=config.s3_bucket,
            region=config.aws_region,
        )
        secrets_client = SecretsClient(
            region=config.aws_region,
        )

        # Step 3: Load job record from DynamoDB
        logger.info("Loading job record", extra={"job_id": job_id})
        job_record = db_client.get_job(job_id)
        if not job_record:
            raise ValueError(f"Job {job_id} not found in database")

        logger.info(
            "Job record loaded",
            extra={
                "job_id": job_id,
                "status": job_record.status,
                "manga_title": job_record.manga_title,
            },
        )

        # Step 4: Load manga info for metadata generation
        panel_manifest_key = f"jobs/{job_id}/panel_manifest.json"
        logger.info(
            "Loading panel manifest for manga info",
            extra={"s3_key": panel_manifest_key},
        )
        panel_manifest = s3_client.download_json(panel_manifest_key)
        if not panel_manifest:
            raise ValueError(f"Panel manifest not found at {panel_manifest_key}")

        # Reconstruct MangaInfo from panel manifest
        manga_info = _reconstruct_manga_info(panel_manifest)

        logger.info(
            "Manga info loaded",
            extra={
                "manga_id": manga_info.manga_id,
                "manga_title": manga_info.title,
                "chapter_count": len(manga_info.chapters),
            },
        )

        # Step 5: Check if video exists locally, otherwise download from S3
        local_video_dir = f"/tmp/render/{job_id}"
        local_video_path = os.path.join(local_video_dir, "video.mp4")

        if os.path.exists(local_video_path):
            logger.info(
                "Using local video file",
                extra={"path": local_video_path},
            )
        else:
            # Download from S3
            logger.info("Local video not found, downloading from S3")
            os.makedirs(local_video_dir, exist_ok=True)

            video_s3_key = f"jobs/{job_id}/video.mp4"
            s3_client.download_file(video_s3_key, local_video_path)

            logger.info(
                "Video downloaded from S3",
                extra={
                    "s3_key": video_s3_key,
                    "local_path": local_video_path,
                    "file_size_mb": round(os.path.getsize(local_video_path) / (1024 * 1024), 2),
                },
            )

        # Step 6: Initialize YouTubeAuthManager and get authenticated service
        logger.info("Authenticating with YouTube")
        youtube_auth = YouTubeAuthManager(
            secrets_client=secrets_client,
            secret_name=config.youtube_secret_name,
        )

        try:
            youtube_service = youtube_auth.get_authenticated_service()
            logger.info("YouTube authentication successful")
        except YouTubeAuthError as e:
            logger.error(
                "YouTube authentication failed",
                extra={"error": str(e)},
            )
            db_client.update_job_status(
                job_id=job_id,
                status=JobStatus.failed,
                error_message=f"YouTube authentication failed: {str(e)}",
            )
            raise

        # Step 7: Generate metadata using MetadataGenerator
        logger.info("Generating YouTube metadata")
        metadata_generator = MetadataGenerator()
        metadata = metadata_generator.generate_metadata(manga_info, job_record)

        logger.info(
            "Metadata generated",
            extra={
                "title": metadata.get("title"),
                "tags_count": len(metadata.get("tags", [])),
            },
        )

        # Step 8: Upload video using YouTubeUploadClient
        logger.info("Starting YouTube video upload")
        db_client.update_job_status(
            job_id=job_id,
            status=JobStatus.uploading,
            progress_pct=90,
        )

        upload_client = YouTubeUploadClient(youtube_service)

        try:
            youtube_url = upload_client.upload_video(local_video_path, metadata)
            logger.info(
                "Video uploaded successfully",
                extra={"youtube_url": youtube_url},
            )
        except YouTubeQuotaError as e:
            logger.error(
                "YouTube quota exceeded",
                extra={"error": str(e)},
            )
            db_client.update_job_status(
                job_id=job_id,
                status=JobStatus.failed,
                error_message="YouTube quota exceeded, will retry next day",
            )
            raise
        except YouTubeUploadError as e:
            logger.error(
                "Video upload failed",
                extra={"error": str(e)},
            )
            db_client.update_job_status(
                job_id=job_id,
                status=JobStatus.failed,
                error_message=f"Video upload failed: {str(e)}",
            )
            raise

        # Step 9: Update job record with YouTube URL and status=completed
        logger.info("Updating job status to completed")
        db_client.update_job_status(
            job_id=job_id,
            status=JobStatus.completed,
            youtube_url=youtube_url,
            progress_pct=100,
        )

        # Step 10: Trigger cleanup Lambda
        logger.info("Triggering cleanup Lambda")
        try:
            lambda_client = boto3.client("lambda", region_name=config.aws_region)

            # Invoke cleanup Lambda asynchronously
            lambda_client.invoke(
                FunctionName=f"manga-pipeline-cleanup-{config.aws_region}",
                InvocationType="Event",  # Async invocation
                Payload=str.encode(f'{{"job_id": "{job_id}"}}'),
            )

            logger.info("Cleanup Lambda invoked successfully")
        except Exception as cleanup_error:
            # Log but don't fail the job - cleanup is not critical
            logger.warning(
                "Failed to invoke cleanup Lambda (non-critical)",
                extra={"error": str(cleanup_error)},
            )

        # Step 11: Log success
        logger.info(
            "YouTube upload completed successfully",
            extra={
                "job_id": job_id,
                "youtube_url": youtube_url,
            },
        )

    except Exception as e:
        logger.error(
            "YouTube upload failed",
            extra={
                "job_id": job_id,
                "error": str(e),
            },
            exc_info=True,
        )

        # Update job status to failed (if not already updated)
        if job_id:
            try:
                config = get_settings()
                db_client = DynamoDBClient(
                    table_name=config.dynamodb_jobs_table,
                    region=config.aws_region,
                )
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

        raise

    finally:
        # Clean up local video file if downloaded
        if local_video_path and os.path.exists(local_video_path):
            try:
                logger.info("Cleaning up local video file")
                os.unlink(local_video_path)

                # Remove directory if empty
                local_video_dir = os.path.dirname(local_video_path)
                if os.path.exists(local_video_dir) and not os.listdir(local_video_dir):
                    os.rmdir(local_video_dir)

                logger.info("Local video file cleaned up")
            except Exception as cleanup_error:
                logger.warning(
                    "Failed to clean up local video file",
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
    from src.common.models import ChapterInfo

    # Reconstruct chapters
    chapters = []
    for chapter_data in panel_manifest.get("chapters", []):
        chapter_info = ChapterInfo(
            chapter_id=chapter_data.get("chapter_id", ""),
            title=chapter_data.get("title", ""),
            chapter_number=chapter_data.get("chapter_number"),
            page_urls=[],  # Not needed for metadata generation
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


if __name__ == "__main__":
    main()
