"""Lambda handler for manga fetching orchestration."""

import uuid
from typing import Any

from src.common.config import get_settings
from src.common.db import DynamoDBClient
from src.common.logging_config import set_correlation_id, setup_logger
from src.common.models import JobRecord, JobStatus
from src.common.storage import S3Client
from src.fetcher.mangadex_client import MangaDexClient
from src.fetcher.panel_downloader import PanelDownloader

logger = setup_logger(__name__)


def handler(event: dict, context: Any) -> dict:
    """
    Lambda handler for fetching manga and downloading panels.

    Args:
        event: Lambda event (can be empty for scheduled triggers).
        context: Lambda context.

    Returns:
        Result dict with job_id and manga info, or status if no manga available.
    """
    # Generate correlation ID for request tracing
    correlation_id = str(uuid.uuid4())
    set_correlation_id(correlation_id)

    logger.info(
        "Fetcher handler started",
        extra={"correlation_id": correlation_id, "event": event},
    )

    # Initialize configuration and clients
    settings = get_settings()
    db_client = DynamoDBClient(settings)
    s3_client = S3Client(settings)
    mangadex_client = MangaDexClient(
        base_url=settings.mangadex_base_url,
        timeout=30,
    )
    panel_downloader = PanelDownloader(
        mangadex_client=mangadex_client,
        s3_client=s3_client,
    )

    job_id: str | None = None
    job_record: JobRecord | None = None

    try:
        # Step 1: Get trending manga
        logger.info("Fetching trending manga")
        trending_manga = mangadex_client.get_trending_manga(limit=20)

        # Step 2: Find a suitable manga (not hentai, not already processed)
        selected_manga_data: dict | None = None

        for manga_data in trending_manga:
            manga_id = manga_data.get("id", "")

            # Check if hentai
            if mangadex_client.is_hentai(manga_data):
                logger.debug(
                    "Skipping hentai manga",
                    extra={"manga_id": manga_id},
                )
                continue

            # Check if already processed
            if db_client.is_manga_processed(manga_id):
                logger.debug(
                    "Skipping already processed manga",
                    extra={"manga_id": manga_id},
                )
                continue

            # This manga passes all filters
            selected_manga_data = manga_data
            logger.info(
                "Selected manga for processing",
                extra={"manga_id": manga_id},
            )
            break

        # Step 3: If no manga available, return early
        if selected_manga_data is None:
            logger.info("No suitable manga available for processing")
            return {"status": "no_manga_available"}

        manga_id = selected_manga_data.get("id", "")

        # Step 4: Fetch full manga details
        logger.info("Fetching manga details", extra={"manga_id": manga_id})
        manga_info = mangadex_client.get_manga_details(manga_id)

        # Step 5: Fetch chapters
        logger.info("Fetching chapters", extra={"manga_id": manga_id})
        chapters = mangadex_client.get_chapters(manga_id)
        manga_info.chapters = chapters

        if not chapters:
            logger.warning(
                "No chapters found for manga",
                extra={"manga_id": manga_id},
            )
            return {"status": "no_chapters_available", "manga_id": manga_id}

        # Step 6: Create job record
        job_id = str(uuid.uuid4())
        job_record = JobRecord(
            job_id=job_id,
            manga_id=manga_id,
            manga_title=manga_info.title,
            status=JobStatus.fetching,
        )
        db_client.create_job(job_record)

        logger.info(
            "Job created",
            extra={"job_id": job_id, "manga_id": manga_id},
        )

        # Step 7: Download panels
        logger.info(
            "Starting panel download",
            extra={"job_id": job_id, "chapter_count": len(chapters)},
        )
        panel_manifest = panel_downloader.download_manga_panels(manga_info, job_id)

        # Panel manifest is already stored by panel_downloader
        panel_manifest_key = f"jobs/{job_id}/panel_manifest.json"

        logger.info(
            "Panel download complete",
            extra={
                "job_id": job_id,
                "total_panels": panel_manifest.get("total_panels", 0),
            },
        )

        # Step 8: Update job status to scripting
        db_client.update_job_status(
            job_id=job_id,
            status=JobStatus.scripting,
            progress_pct=20,
        )

        # Step 9: Mark manga as processed
        db_client.mark_manga_processed(
            manga_id=manga_id,
            title=manga_info.title,
        )

        logger.info(
            "Fetcher handler completed successfully",
            extra={"job_id": job_id, "manga_id": manga_id},
        )

        return {
            "job_id": job_id,
            "manga_id": manga_id,
            "manga_title": manga_info.title,
            "panel_manifest_s3_key": panel_manifest_key,
        }

    except Exception as e:
        logger.error(
            "Fetcher handler failed",
            extra={
                "job_id": job_id,
                "error": str(e),
                "error_type": type(e).__name__,
            },
        )

        # Update job status to failed if job was created
        if job_id is not None:
            try:
                db_client.update_job_status(
                    job_id=job_id,
                    status=JobStatus.failed,
                    error_message=str(e),
                )
            except Exception as update_error:
                logger.error(
                    "Failed to update job status to failed",
                    extra={"job_id": job_id, "error": str(update_error)},
                )

        raise

    finally:
        # Clean up clients
        try:
            mangadex_client.close()
            panel_downloader.close()
        except Exception:
            pass  # Ignore cleanup errors
