"""Lambda handler for script generation."""

import uuid
from typing import Any

from src.common.config import get_settings
from src.common.db import DynamoDBClient
from src.common.logging_config import set_correlation_id, setup_logger
from src.common.models import ChapterInfo, JobStatus, MangaInfo
from src.common.secrets import SecretsClient
from src.common.storage import S3Client
from src.scriptgen.deepinfra_client import DeepInfraClient
from src.scriptgen.script_builder import ScriptBuilder

logger = setup_logger(__name__)


def handler(event: dict, context: Any) -> dict:
    """
    Lambda handler for generating manga narration scripts.

    Args:
        event: Lambda event with job_id, manga_id, manga_title, panel_manifest_s3_key.
        context: Lambda context.

    Returns:
        Result dict with job_id, script_s3_key, total_segments, estimated_duration_minutes.
    """
    # Generate correlation ID for request tracing
    correlation_id = str(uuid.uuid4())
    set_correlation_id(correlation_id)

    job_id = event.get("job_id")
    manga_id = event.get("manga_id")
    manga_title = event.get("manga_title")
    panel_manifest_s3_key = event.get("panel_manifest_s3_key")

    logger.info(
        "Script generation handler started",
        extra={
            "correlation_id": correlation_id,
            "job_id": job_id,
            "manga_id": manga_id,
        },
    )

    # Initialize configuration and clients
    settings = get_settings()
    db_client = DynamoDBClient(settings)
    s3_client = S3Client(settings)
    secrets_client = SecretsClient(region=settings.aws_region)

    deepinfra_client: DeepInfraClient | None = None

    try:
        # Step 1: Load API key from Secrets Manager
        logger.info("Loading DeepInfra API key from Secrets Manager")
        api_key = secrets_client.get_deepinfra_api_key(settings.deepinfra_secret_name)

        if not api_key:
            raise ValueError("DeepInfra API key is empty")

        # Step 2: Initialize DeepInfra client
        deepinfra_client = DeepInfraClient(
            api_key=api_key,
            base_url=settings.deepinfra_base_url,
        )

        # Step 3: Load job record from DynamoDB
        logger.info("Loading job record", extra={"job_id": job_id})
        job_record = db_client.get_job(job_id)

        if not job_record:
            raise ValueError(f"Job not found: {job_id}")

        # Step 4: Load panel manifest from S3
        logger.info(
            "Loading panel manifest",
            extra={"s3_key": panel_manifest_s3_key},
        )
        panel_manifest = s3_client.download_json(panel_manifest_s3_key)

        # Step 5: Load pipeline settings from DynamoDB
        logger.info("Loading pipeline settings")
        pipeline_settings = db_client.get_settings()

        # Step 6: Reconstruct MangaInfo from panel manifest
        logger.info("Reconstructing MangaInfo from panel manifest")
        chapters = []

        for chapter_data in panel_manifest.get("chapters", []):
            chapter_id = chapter_data.get("chapter_id", "")
            chapter_number = chapter_data.get("chapter_number", "")
            panel_keys = chapter_data.get("panel_keys", [])

            # Create page URLs from panel keys (they're already in S3)
            page_urls = [
                f"s3://{settings.s3_bucket}/{key}" for key in panel_keys
            ]

            chapter = ChapterInfo(
                chapter_id=chapter_id,
                title=f"Chapter {chapter_number}",
                chapter_number=chapter_number,
                page_urls=page_urls,
            )
            chapters.append(chapter)

        manga = MangaInfo(
            manga_id=manga_id,
            title=manga_title,
            description=panel_manifest.get("description", ""),
            genres=panel_manifest.get("genres", []),
            cover_url=panel_manifest.get("cover_url"),
            chapters=chapters,
        )

        logger.info(
            "MangaInfo reconstructed",
            extra={"manga_id": manga_id, "chapters": len(chapters)},
        )

        # Step 7: Generate full script
        logger.info("Starting script generation")
        script_builder = ScriptBuilder(deepinfra_client)
        script_document = script_builder.generate_full_script(
            manga=manga,
            panel_manifest=panel_manifest,
            settings=pipeline_settings,
        )

        # Step 8: Estimate duration
        estimated_duration = script_builder.estimate_duration_minutes(script_document)

        logger.info(
            "Script generation complete",
            extra={
                "job_id": job_id,
                "segments": len(script_document.segments),
                "estimated_duration_minutes": estimated_duration,
            },
        )

        # Step 9: Store script in S3
        script_s3_key = f"jobs/{job_id}/script.json"
        logger.info(
            "Storing script in S3",
            extra={"s3_key": script_s3_key},
        )
        s3_client.upload_json(script_document.model_dump(), script_s3_key)

        # Step 10: Update job status to tts
        db_client.update_job_status(
            job_id=job_id,
            status=JobStatus.tts,
            progress_pct=40,
        )

        logger.info(
            "Script generation handler completed successfully",
            extra={"job_id": job_id},
        )

        return {
            "job_id": job_id,
            "script_s3_key": script_s3_key,
            "total_segments": len(script_document.segments),
            "estimated_duration_minutes": round(estimated_duration, 2),
        }

    except Exception as e:
        logger.error(
            "Script generation handler failed",
            extra={
                "job_id": job_id,
                "error": str(e),
                "error_type": type(e).__name__,
            },
        )

        # Update job status to failed
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
        if deepinfra_client:
            try:
                deepinfra_client.close()
            except Exception:
                pass  # Ignore cleanup errors
