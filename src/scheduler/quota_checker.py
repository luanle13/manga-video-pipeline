"""Lambda handler for checking daily video quota."""

from datetime import datetime, timezone
from typing import Any
from zoneinfo import ZoneInfo

from src.common.config import get_settings
from src.common.db import DynamoDBClient
from src.common.logging_config import setup_logger
from src.common.models import JobStatus

logger = setup_logger(__name__)

# Vietnam timezone (UTC+7)
VIETNAM_TZ = ZoneInfo("Asia/Ho_Chi_Minh")

# Job statuses that count toward quota (exclude failed/cancelled)
QUOTA_STATUSES = {
    JobStatus.pending,
    JobStatus.fetching,
    JobStatus.scripting,
    JobStatus.tts,
    JobStatus.rendering,
    JobStatus.uploading,
    JobStatus.completed,
}


def get_vietnam_today() -> str:
    """
    Get today's date in Vietnam timezone (UTC+7).

    Returns:
        Date string in YYYY-MM-DD format.
    """
    now_vietnam = datetime.now(VIETNAM_TZ)
    return now_vietnam.date().isoformat()


def handler(event: dict, context: Any) -> dict:
    """
    Check if daily video quota has been reached.

    Queries DynamoDB for jobs created today (Vietnam timezone) and compares
    against the configured daily quota. Only counts jobs with active statuses
    (excludes failed jobs).

    Args:
        event: Lambda event dict (unused).
        context: Lambda context (unused).

    Returns:
        Dict with:
            - quota: Daily quota limit
            - used: Number of jobs created today
            - remaining: Quota slots remaining
            - quota_reached: Boolean indicating if quota is reached
            - daily_quota: (for Step Functions compatibility)
            - daily_count: (for Step Functions compatibility)
    """
    logger.info("Checking daily video quota")

    # Step 1: Load settings
    settings = get_settings()
    daily_quota = settings.daily_quota

    logger.info(
        "Loaded quota settings",
        extra={"daily_quota": daily_quota},
    )

    # Step 2: Get today's date in Vietnam timezone
    today = get_vietnam_today()

    logger.info(
        "Checking quota for date",
        extra={"date": today, "timezone": "Asia/Ho_Chi_Minh (UTC+7)"},
    )

    # Step 3: Count jobs created today
    db_client = DynamoDBClient(settings)
    used_count = count_todays_jobs(db_client, today)

    logger.info(
        "Counted today's jobs",
        extra={
            "date": today,
            "used_count": used_count,
            "daily_quota": daily_quota,
        },
    )

    # Step 4: Calculate remaining and quota_reached
    remaining = max(0, daily_quota - used_count)
    quota_reached = used_count >= daily_quota

    result = {
        "quota": daily_quota,
        "used": used_count,
        "remaining": remaining,
        "quota_reached": quota_reached,
        # Additional fields for Step Functions compatibility
        "daily_quota": daily_quota,
        "daily_count": used_count,
    }

    logger.info(
        "Quota check complete",
        extra=result,
    )

    return result


def count_todays_jobs(db_client: DynamoDBClient, today: str) -> int:
    """
    Count jobs created today with valid statuses.

    Args:
        db_client: DynamoDB client instance.
        today: Date string in YYYY-MM-DD format.

    Returns:
        Number of jobs created today (excluding failed jobs).
    """
    # TODO: For production, create a GSI on created_at for efficient queries
    # Current implementation uses scan which is acceptable for small tables
    # but won't scale well. GSI would allow Query instead of Scan.

    count = 0

    # Use high-level Table.scan() which returns deserialized items
    table = db_client._jobs_table
    scan_kwargs = {}

    while True:
        response = table.scan(**scan_kwargs)
        items = response.get("Items", [])

        for item in items:
            # Parse created_at timestamp (high-level API returns plain values)
            created_at_str = item.get("created_at", "")
            if not created_at_str:
                continue

            try:
                # Parse ISO timestamp and convert to Vietnam timezone
                created_at_utc = datetime.fromisoformat(str(created_at_str).replace("Z", "+00:00"))
                created_at_vietnam = created_at_utc.astimezone(VIETNAM_TZ)
                created_date = created_at_vietnam.date().isoformat()

                # Check if created today
                if created_date != today:
                    continue

                # Check status (only count active jobs, not failed)
                status_str = item.get("status", "")
                if not status_str:
                    continue

                # Convert string to JobStatus enum for comparison
                try:
                    job_status = JobStatus(str(status_str))
                    if job_status in QUOTA_STATUSES:
                        count += 1
                        logger.debug(
                            "Counted job toward quota",
                            extra={
                                "job_id": item.get("job_id", "unknown"),
                                "status": status_str,
                                "created_at": created_at_str,
                            },
                        )
                except ValueError:
                    # Invalid status value, skip
                    logger.warning(
                        "Invalid job status encountered",
                        extra={
                            "job_id": item.get("job_id", "unknown"),
                            "status": status_str,
                        },
                    )
                    continue

            except (ValueError, AttributeError) as e:
                # Invalid timestamp format, skip
                logger.warning(
                    "Failed to parse job created_at timestamp",
                    extra={
                        "job_id": item.get("job_id", "unknown"),
                        "created_at": created_at_str,
                        "error": str(e),
                    },
                )
                continue

        # Check for pagination
        if "LastEvaluatedKey" in response:
            scan_kwargs["ExclusiveStartKey"] = response["LastEvaluatedKey"]
        else:
            break

    return count
