"""Lambda handler for cleaning up temporary job artifacts from S3."""

from datetime import UTC, datetime
from typing import Any

from src.common.config import get_settings
from src.common.db import DynamoDBClient
from src.common.logging_config import setup_logger
from src.common.storage import S3Client

logger = setup_logger(__name__)


def handler(event: dict, context: Any) -> dict:
    """
    Clean up temporary S3 objects for a completed job.

    Deletes all objects under the job prefix: jobs/{job_id}/
    Updates the job record with cleanup timestamp.

    Args:
        event: Lambda event dict with:
            - job_id: Job ID to clean up
        context: Lambda context (unused).

    Returns:
        Dict with:
            - job_id: Job ID cleaned
            - objects_deleted: Number of objects deleted
            - bytes_freed: Total bytes freed
    """
    job_id = event.get("job_id")
    if not job_id:
        logger.error("Missing job_id in event")
        raise ValueError("job_id is required in event")

    logger.info(
        "Starting cleanup for job",
        extra={"job_id": job_id},
    )

    # Step 1: Initialize config, logger, DB, S3
    settings = get_settings()
    db_client = DynamoDBClient(settings)
    s3_client = S3Client(settings)

    # Step 2: Delete all S3 objects under prefix: jobs/{job_id}/
    prefix = f"jobs/{job_id}/"

    logger.info(
        "Deleting S3 objects",
        extra={"prefix": prefix},
    )

    objects_deleted, bytes_freed = s3_client.delete_prefix_with_metrics(prefix)

    # Step 3: Log deletion metrics
    bytes_freed_mb = bytes_freed / (1024 * 1024) if bytes_freed > 0 else 0

    logger.info(
        "S3 objects deleted",
        extra={
            "job_id": job_id,
            "objects_deleted": objects_deleted,
            "bytes_freed": bytes_freed,
            "bytes_freed_mb": round(bytes_freed_mb, 2),
        },
    )

    # Step 4: Update job record with cleanup_at field and mark manga as processed
    try:
        # Get current job to update it
        job = db_client.get_job(job_id)
        if job:
            # Update the job record with cleanup timestamp
            cleanup_at = datetime.now(UTC)

            # Update using the DynamoDB client directly
            db_client._client.update_item(
                TableName=db_client._table_name,
                Key={"job_id": {"S": job_id}},
                UpdateExpression="SET cleanup_at = :cleanup_at, updated_at = :updated_at",
                ExpressionAttributeValues={
                    ":cleanup_at": {"S": cleanup_at.isoformat()},
                    ":updated_at": {"S": cleanup_at.isoformat()},
                },
            )

            logger.info(
                "Job record updated with cleanup timestamp",
                extra={"job_id": job_id, "cleanup_at": cleanup_at.isoformat()},
            )

            # Step 4b: Mark manga as processed (only after successful pipeline completion)
            # This prevents re-processing the same manga, but only if the entire pipeline succeeded
            if job.manga_id and job.manga_title:
                db_client.mark_manga_processed(
                    manga_id=job.manga_id,
                    title=job.manga_title,
                )
                logger.info(
                    "Manga marked as processed",
                    extra={"manga_id": job.manga_id, "title": job.manga_title},
                )
        else:
            logger.warning(
                "Job not found in database, skipping record update",
                extra={"job_id": job_id},
            )
    except Exception as e:
        # Log error but don't fail the cleanup - cleanup already succeeded
        logger.warning(
            "Failed to update job record or mark manga as processed",
            extra={"job_id": job_id, "error": str(e)},
        )

    # Step 5: Return success response
    response = {
        "job_id": job_id,
        "objects_deleted": objects_deleted,
        "bytes_freed": bytes_freed,
    }

    logger.info(
        "Cleanup completed successfully",
        extra=response,
    )

    return response
