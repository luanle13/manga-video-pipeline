"""Spot interruption handler for EC2 Spot instances."""

import json
import signal
import sys
from typing import Any, Callable

from src.common.logging_config import setup_logger
from src.common.storage import S3Client

logger = setup_logger(__name__)

# Global state for signal handler
_checkpoint_callback: Callable[[], None] | None = None


def register_spot_interruption_handler(
    job_id: str,
    s3_client: S3Client,
    checkpoint_callback: Callable[[], dict[str, Any]] | None = None,
) -> None:
    """
    Register a SIGTERM handler for EC2 Spot interruption warnings.

    AWS sends SIGTERM 2 minutes before terminating a Spot instance.
    This handler saves a checkpoint and exits gracefully.

    Args:
        job_id: Job ID for checkpoint file naming.
        s3_client: S3 client for saving checkpoint.
        checkpoint_callback: Optional callback that returns checkpoint data.
                            If not provided, saves empty checkpoint.
    """
    global _checkpoint_callback

    def sigterm_handler(signum: int, frame: Any) -> None:
        """Handle SIGTERM signal from Spot interruption."""
        logger.warning(
            "Received SIGTERM - Spot instance interruption detected",
            extra={"job_id": job_id, "signal": signum},
        )

        try:
            # Get checkpoint data from callback if provided
            if checkpoint_callback:
                checkpoint_data = checkpoint_callback()
            else:
                checkpoint_data = {}

            # Save checkpoint to S3
            save_checkpoint(job_id, checkpoint_data, s3_client)

            logger.info(
                "Checkpoint saved successfully, exiting gracefully",
                extra={"job_id": job_id},
            )

        except Exception as e:
            logger.error(
                "Failed to save checkpoint on interruption",
                extra={"job_id": job_id, "error": str(e)},
                exc_info=True,
            )

        # Exit gracefully
        sys.exit(0)

    # Register the handler
    signal.signal(signal.SIGTERM, sigterm_handler)

    logger.info(
        "Spot interruption handler registered",
        extra={"job_id": job_id},
    )


def save_checkpoint(
    job_id: str,
    checkpoint_data: dict[str, Any],
    s3_client: S3Client,
) -> None:
    """
    Save checkpoint data to S3.

    Args:
        job_id: Job ID for checkpoint file naming.
        checkpoint_data: Checkpoint data to save (e.g., {"last_completed_chunk": 5}).
        s3_client: S3 client for uploading.
    """
    checkpoint_key = f"jobs/{job_id}/checkpoint.json"

    logger.info(
        "Saving checkpoint to S3",
        extra={
            "job_id": job_id,
            "checkpoint_key": checkpoint_key,
            "checkpoint_data": checkpoint_data,
        },
    )

    try:
        # Convert checkpoint data to JSON
        checkpoint_json = json.dumps(checkpoint_data, indent=2)

        # Upload to S3
        s3_client.put_object(checkpoint_key, checkpoint_json.encode("utf-8"))

        logger.info(
            "Checkpoint saved successfully",
            extra={"job_id": job_id, "checkpoint_key": checkpoint_key},
        )

    except Exception as e:
        logger.error(
            "Failed to save checkpoint",
            extra={"job_id": job_id, "error": str(e)},
            exc_info=True,
        )
        raise


def load_checkpoint(
    job_id: str,
    s3_client: S3Client,
) -> dict[str, Any] | None:
    """
    Load checkpoint data from S3 if it exists.

    Args:
        job_id: Job ID for checkpoint file naming.
        s3_client: S3 client for downloading.

    Returns:
        Checkpoint data dict if found, None otherwise.
    """
    checkpoint_key = f"jobs/{job_id}/checkpoint.json"

    logger.info(
        "Checking for existing checkpoint",
        extra={"job_id": job_id, "checkpoint_key": checkpoint_key},
    )

    try:
        # Try to download checkpoint from S3
        checkpoint_bytes = s3_client.download_as_bytes(checkpoint_key)

        if checkpoint_bytes is None:
            logger.info(
                "No checkpoint found, starting fresh",
                extra={"job_id": job_id},
            )
            return None

        # Parse checkpoint JSON
        checkpoint_data = json.loads(checkpoint_bytes.decode("utf-8"))

        logger.info(
            "Checkpoint loaded successfully",
            extra={
                "job_id": job_id,
                "checkpoint_data": checkpoint_data,
            },
        )

        return checkpoint_data

    except Exception as e:
        logger.warning(
            "Failed to load checkpoint, starting fresh",
            extra={"job_id": job_id, "error": str(e)},
        )
        return None


def delete_checkpoint(
    job_id: str,
    s3_client: S3Client,
) -> None:
    """
    Delete checkpoint file from S3 after successful completion.

    Args:
        job_id: Job ID for checkpoint file naming.
        s3_client: S3 client for deletion.
    """
    checkpoint_key = f"jobs/{job_id}/checkpoint.json"

    logger.info(
        "Deleting checkpoint file",
        extra={"job_id": job_id, "checkpoint_key": checkpoint_key},
    )

    try:
        s3_client.delete_object(checkpoint_key)

        logger.info(
            "Checkpoint deleted successfully",
            extra={"job_id": job_id},
        )

    except Exception as e:
        logger.warning(
            "Failed to delete checkpoint (non-critical)",
            extra={"job_id": job_id, "error": str(e)},
        )
