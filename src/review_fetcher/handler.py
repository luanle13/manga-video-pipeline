"""Lambda handler for review video manga fetching."""

import asyncio
import uuid
from typing import Any

from src.common.config import get_settings
from src.common.db import DynamoDBClient
from src.common.logging_config import set_correlation_id, setup_logger
from src.common.models import (
    JobRecord,
    JobStatus,
    JobType,
    MangaSource,
    ReviewManifest,
)
from src.common.storage import S3Client
from src.review_fetcher.scraper_factory import (
    detect_source_from_url,
    get_all_scrapers,
    get_scraper_for_url,
)
from src.review_fetcher.scrapers.base import BaseMangaScraper

logger = setup_logger(__name__)


async def _download_image(
    url: str,
    s3_key: str,
    s3_client: S3Client,
    scraper: BaseMangaScraper,
) -> str | None:
    """Download an image and upload to S3.

    Args:
        url: Image URL
        s3_key: S3 key to store the image
        s3_client: S3 client instance
        scraper: Scraper to use for downloading

    Returns:
        S3 key if successful, None otherwise
    """
    try:
        image_bytes = await scraper._fetch_bytes(url)
        s3_client.put_object(s3_key, image_bytes)
        return s3_key
    except Exception as e:
        logger.warning(
            "Failed to download image",
            extra={"url": url, "error": str(e)},
        )
        return None


async def _fetch_manga_content(
    manga_url: str | None,
    manga_name: str | None,
    source: MangaSource | None,
    job_id: str,
    s3_client: S3Client,
    max_chapters: int = 50,
) -> ReviewManifest:
    """Fetch manga content from URL or by searching.

    Args:
        manga_url: Direct URL to manga page
        manga_name: Search query (if no URL)
        source: Optional source hint
        job_id: Job ID for S3 storage
        s3_client: S3 client instance
        max_chapters: Maximum number of chapters to fetch

    Returns:
        ReviewManifest with downloaded content

    Raises:
        ValueError: If manga cannot be found
    """
    scraper: BaseMangaScraper | None = None

    try:
        if manga_url:
            # Get scraper for the URL
            scraper = get_scraper_for_url(manga_url)
            async with scraper:
                # Fetch manga info
                logger.info(
                    "Fetching manga info from URL",
                    extra={"url": manga_url, "source": scraper.SOURCE},
                )
                manga_info = await scraper.get_manga_info(manga_url)

                # Fetch chapter content (limited)
                logger.info(
                    "Fetching chapter content",
                    extra={
                        "total_chapters": manga_info.total_chapters,
                        "max_chapters": max_chapters,
                    },
                )
                manga_info = await scraper.get_all_chapter_content(
                    manga_info, max_chapters=max_chapters
                )

        elif manga_name:
            # Search across all scrapers or specific source
            logger.info(
                "Searching for manga",
                extra={"query": manga_name, "source": source},
            )

            if source:
                from src.review_fetcher.scraper_factory import get_scraper_for_source

                scrapers = [get_scraper_for_source(source)]
            else:
                scrapers = get_all_scrapers()

            best_result = None
            best_scraper_class = None

            for s in scrapers:
                async with s:
                    results = await s.search(manga_name)
                    if results:
                        # Use first result as best match
                        best_result = results[0]
                        best_scraper_class = type(s)
                        break

            if not best_result or not best_scraper_class:
                raise ValueError(f"No manga found for query: {manga_name}")

            # Fetch from best result
            scraper = best_scraper_class()
            async with scraper:
                logger.info(
                    "Fetching manga from search result",
                    extra={"url": best_result.url, "title": best_result.title},
                )
                manga_info = await scraper.get_manga_info(best_result.url)
                manga_info = await scraper.get_all_chapter_content(
                    manga_info, max_chapters=max_chapters
                )

        else:
            raise ValueError("Either manga_url or manga_name must be provided")

        # Download cover image
        cover_s3_key = f"jobs/{job_id}/cover.jpg"
        if manga_info.cover_url:
            async with get_scraper_for_url(manga_info.source_url) as dl_scraper:
                result = await _download_image(
                    manga_info.cover_url, cover_s3_key, s3_client, dl_scraper
                )
                if not result:
                    cover_s3_key = ""

        # Download key panels (1 per chapter, up to 30)
        panel_s3_keys: list[str] = []
        panel_urls_to_download: list[tuple[str, str]] = []

        for i, chapter in enumerate(manga_info.chapters[:30]):
            if chapter.key_panel_url:
                panel_key = f"jobs/{job_id}/panels/chapter_{int(chapter.chapter_number)}_panel.jpg"
                panel_urls_to_download.append((chapter.key_panel_url, panel_key))

        if panel_urls_to_download:
            async with get_scraper_for_url(manga_info.source_url) as dl_scraper:
                for url, key in panel_urls_to_download:
                    result = await _download_image(url, key, s3_client, dl_scraper)
                    if result:
                        panel_s3_keys.append(result)

        return ReviewManifest(
            job_id=job_id,
            manga_info=manga_info,
            cover_s3_key=cover_s3_key,
            panel_s3_keys=panel_s3_keys,
        )

    except Exception as e:
        logger.error(
            "Failed to fetch manga content",
            extra={"manga_url": manga_url, "manga_name": manga_name, "error": str(e)},
        )
        raise


def handler(event: dict, context: Any) -> dict:
    """
    Lambda handler for fetching manga for review video generation.

    Args:
        event: Lambda event with either:
            - manga_url: Direct URL to manga page
            - manga_name: Search query (manga name)
            - source: Optional source hint (truyenqq, nettruyen, etc.)
            - job_id: Optional existing job_id (for retries)
        context: Lambda context.

    Returns:
        Result dict with job_id and review_manifest_s3_key.
    """
    # Generate correlation ID for request tracing
    correlation_id = str(uuid.uuid4())
    set_correlation_id(correlation_id)

    logger.info(
        "Review Fetcher handler started",
        extra={"correlation_id": correlation_id, "event": event},
    )

    # Initialize configuration and clients
    settings = get_settings()
    db_client = DynamoDBClient(settings)
    s3_client = S3Client(settings)

    # Parse input
    manga_url = event.get("manga_url")
    manga_name = event.get("manga_name")
    source_str = event.get("source")
    job_id = event.get("job_id") or str(uuid.uuid4())

    # Validate input
    if not manga_url and not manga_name:
        raise ValueError("Either manga_url or manga_name must be provided")

    # Parse source if provided
    source: MangaSource | None = None
    if source_str:
        try:
            source = MangaSource(source_str)
        except ValueError:
            logger.warning(
                "Invalid source provided",
                extra={"source": source_str},
            )

    # If URL provided, detect source from it
    if manga_url and not source:
        try:
            source = detect_source_from_url(manga_url)
        except ValueError:
            pass  # Will fail later with appropriate error

    job_record: JobRecord | None = None

    try:
        # Create or update job record
        if event.get("job_id"):
            # Existing job - update status
            db_client.update_job_status(
                job_id=job_id,
                status=JobStatus.fetching,
                progress_pct=0,
            )
        else:
            # New job - create record
            job_record = JobRecord(
                job_id=job_id,
                manga_id="",  # Will be updated after fetching
                manga_title=manga_name or manga_url or "",
                job_type=JobType.review_video,
                source=source or MangaSource.truyenqq,
                source_url=manga_url,
                status=JobStatus.fetching,
            )
            db_client.create_job(job_record)

        logger.info(
            "Job created/updated for review fetching",
            extra={"job_id": job_id},
        )

        # Fetch manga content (async)
        review_manifest = asyncio.run(
            _fetch_manga_content(
                manga_url=manga_url,
                manga_name=manga_name,
                source=source,
                job_id=job_id,
                s3_client=s3_client,
                max_chapters=settings.max_chapters,
            )
        )

        # Update job with manga info
        db_client.update_job(
            job_id=job_id,
            updates={
                "manga_id": review_manifest.manga_info.source_url,
                "manga_title": review_manifest.manga_info.title,
                "source_url": review_manifest.manga_info.source_url,
            },
        )

        # Store review manifest in S3
        manifest_key = f"jobs/{job_id}/review_manifest.json"
        s3_client.put_json(manifest_key, review_manifest.model_dump())

        logger.info(
            "Review manifest created",
            extra={
                "job_id": job_id,
                "manga_title": review_manifest.manga_info.title,
                "chapter_count": review_manifest.manga_info.total_chapters,
                "panel_count": len(review_manifest.panel_s3_keys),
            },
        )

        # Update job status to scripting
        db_client.update_job_status(
            job_id=job_id,
            status=JobStatus.scripting,
            progress_pct=20,
        )

        logger.info(
            "Review Fetcher handler completed successfully",
            extra={"job_id": job_id},
        )

        return {
            "status": "success",
            "job_id": job_id,
            "manga_title": review_manifest.manga_info.title,
            "chapter_count": review_manifest.manga_info.total_chapters,
            "review_manifest_s3_key": manifest_key,
        }

    except Exception as e:
        logger.error(
            "Review Fetcher handler failed",
            extra={
                "job_id": job_id,
                "error": str(e),
                "error_type": type(e).__name__,
            },
        )

        # Update job status to failed
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
