"""DynamoDB client wrapper for all table operations."""

from datetime import datetime

import boto3
from boto3.dynamodb.conditions import Attr
from botocore.exceptions import ClientError

from src.common.config import Settings
from src.common.logging_config import setup_logger
from src.common.models import JobRecord, JobStatus, PipelineSettings, utcnow

logger = setup_logger(__name__)

# Constants
SETTINGS_PK = "pipeline_settings"


class DynamoDBClient:
    """Client wrapper for DynamoDB operations."""

    def __init__(self, settings: Settings) -> None:
        """
        Initialize the DynamoDB client.

        Args:
            settings: Application settings containing table names and region.
        """
        self._settings = settings
        self._dynamodb = boto3.resource("dynamodb", region_name=settings.aws_region)
        self._jobs_table = self._dynamodb.Table(settings.dynamodb_jobs_table)
        self._manga_table = self._dynamodb.Table(settings.dynamodb_manga_table)
        self._settings_table = self._dynamodb.Table(settings.dynamodb_settings_table)

        logger.info(
            "DynamoDB client initialized",
            extra={
                "region": settings.aws_region,
                "jobs_table": settings.dynamodb_jobs_table,
                "manga_table": settings.dynamodb_manga_table,
                "settings_table": settings.dynamodb_settings_table,
            },
        )

    # -------------------------------------------------------------------------
    # Job operations
    # -------------------------------------------------------------------------

    def create_job(self, job: JobRecord) -> None:
        """
        Create a new job record in DynamoDB.

        Args:
            job: The job record to create.
        """
        now = utcnow()
        item = job.model_dump()
        item["created_at"] = now.isoformat()
        item["updated_at"] = now.isoformat()
        # Add date partition key for daily queries
        item["created_date"] = now.strftime("%Y-%m-%d")

        self._jobs_table.put_item(Item=item)

        logger.info(
            "Job created",
            extra={"job_id": job.job_id, "manga_id": job.manga_id, "status": job.status},
        )

    def get_job(self, job_id: str) -> JobRecord | None:
        """
        Retrieve a job by its ID.

        Args:
            job_id: The unique job identifier.

        Returns:
            The job record if found, None otherwise.
        """
        response = self._jobs_table.get_item(Key={"job_id": job_id})
        item = response.get("Item")

        if not item:
            logger.debug("Job not found", extra={"job_id": job_id})
            return None

        # Parse datetime strings back to datetime objects
        if "created_at" in item and isinstance(item["created_at"], str):
            item["created_at"] = datetime.fromisoformat(item["created_at"])
        if "updated_at" in item and isinstance(item["updated_at"], str):
            item["updated_at"] = datetime.fromisoformat(item["updated_at"])

        # Remove extra fields not in JobRecord
        item.pop("created_date", None)

        logger.debug("Job retrieved", extra={"job_id": job_id})
        return JobRecord(**item)

    def update_job_status(
        self,
        job_id: str,
        status: JobStatus,
        error_message: str | None = None,
        youtube_url: str | None = None,
        progress_pct: int | None = None,
    ) -> None:
        """
        Update the status and optional fields of a job.

        Args:
            job_id: The unique job identifier.
            status: The new job status.
            error_message: Optional error message (for failed jobs).
            youtube_url: Optional YouTube URL (for completed jobs).
            progress_pct: Optional progress percentage.
        """
        now = utcnow()
        update_expr = "SET #status = :status, updated_at = :updated_at"
        expr_names = {"#status": "status"}
        expr_values = {
            ":status": str(status),
            ":updated_at": now.isoformat(),
        }

        if error_message is not None:
            update_expr += ", error_message = :error_message"
            expr_values[":error_message"] = error_message

        if youtube_url is not None:
            update_expr += ", youtube_url = :youtube_url"
            expr_values[":youtube_url"] = youtube_url

        if progress_pct is not None:
            update_expr += ", progress_pct = :progress_pct"
            expr_values[":progress_pct"] = progress_pct

        self._jobs_table.update_item(
            Key={"job_id": job_id},
            UpdateExpression=update_expr,
            ExpressionAttributeNames=expr_names,
            ExpressionAttributeValues=expr_values,
        )

        logger.info(
            "Job status updated",
            extra={
                "job_id": job_id,
                "status": status,
                "progress_pct": progress_pct,
            },
        )

    def list_jobs(
        self, status: JobStatus | None = None, limit: int = 20
    ) -> list[JobRecord]:
        """
        List jobs, optionally filtered by status.

        Args:
            status: Optional status filter.
            limit: Maximum number of jobs to return.

        Returns:
            List of job records.
        """
        scan_kwargs = {"Limit": limit}

        if status is not None:
            scan_kwargs["FilterExpression"] = Attr("status").eq(str(status))

        response = self._jobs_table.scan(**scan_kwargs)
        items = response.get("Items", [])

        jobs = []
        for item in items:
            # Parse datetime strings
            if "created_at" in item and isinstance(item["created_at"], str):
                item["created_at"] = datetime.fromisoformat(item["created_at"])
            if "updated_at" in item and isinstance(item["updated_at"], str):
                item["updated_at"] = datetime.fromisoformat(item["updated_at"])
            item.pop("created_date", None)
            jobs.append(JobRecord(**item))

        logger.debug(
            "Jobs listed",
            extra={"count": len(jobs), "status_filter": str(status) if status else None},
        )
        return jobs

    def get_daily_job_count(self, date_str: str) -> int:
        """
        Get the count of jobs created on a specific date.

        Args:
            date_str: Date string in YYYY-MM-DD format.

        Returns:
            Number of jobs created on that date.
        """
        # Use GSI on created_date if available, otherwise scan with filter
        response = self._jobs_table.scan(
            FilterExpression=Attr("created_date").eq(date_str),
            Select="COUNT",
        )
        count = response.get("Count", 0)

        logger.debug("Daily job count retrieved", extra={"date": date_str, "count": count})
        return count

    # -------------------------------------------------------------------------
    # Manga tracking operations
    # -------------------------------------------------------------------------

    def is_manga_processed(self, manga_id: str) -> bool:
        """
        Check if a manga has already been processed.

        Args:
            manga_id: The manga identifier.

        Returns:
            True if manga has been processed, False otherwise.
        """
        response = self._manga_table.get_item(Key={"manga_id": manga_id})
        exists = "Item" in response

        logger.debug(
            "Manga processed check",
            extra={"manga_id": manga_id, "is_processed": exists},
        )
        return exists

    def mark_manga_processed(
        self, manga_id: str, title: str, youtube_url: str = ""
    ) -> None:
        """
        Mark a manga as processed. Uses conditional write to prevent overwriting.

        Args:
            manga_id: The manga identifier.
            title: The manga title.
            youtube_url: Optional YouTube URL for the video.
        """
        now = utcnow()
        item = {
            "manga_id": manga_id,
            "title": title,
            "youtube_url": youtube_url,
            "processed_at": now.isoformat(),
        }

        try:
            # Use condition to prevent overwriting existing records
            self._manga_table.put_item(
                Item=item,
                ConditionExpression=Attr("manga_id").not_exists(),
            )
            logger.info(
                "Manga marked as processed",
                extra={"manga_id": manga_id, "title": title},
            )
        except ClientError as e:
            if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
                logger.warning(
                    "Manga already processed, skipping",
                    extra={"manga_id": manga_id},
                )
            else:
                raise

    def list_processed_manga(self, limit: int = 50) -> list[dict]:
        """
        List processed manga records.

        Args:
            limit: Maximum number of records to return.

        Returns:
            List of processed manga records as dictionaries.
        """
        response = self._manga_table.scan(Limit=limit)
        items = response.get("Items", [])

        logger.debug("Processed manga listed", extra={"count": len(items)})
        return items

    # -------------------------------------------------------------------------
    # Settings operations
    # -------------------------------------------------------------------------

    def get_settings(self) -> PipelineSettings:
        """
        Retrieve pipeline settings from DynamoDB.

        Returns:
            Pipeline settings (defaults if not found).
        """
        response = self._settings_table.get_item(Key={"setting_key": SETTINGS_PK})
        item = response.get("Item")

        if not item:
            logger.debug("Settings not found, returning defaults")
            return PipelineSettings()

        # Remove the partition key before creating PipelineSettings
        item.pop("setting_key", None)
        item.pop("updated_at", None)

        logger.debug("Settings retrieved")
        return PipelineSettings(**item)

    def update_settings(self, settings: PipelineSettings) -> None:
        """
        Update pipeline settings in DynamoDB.

        Args:
            settings: The new settings to save.
        """
        now = utcnow()
        item = settings.model_dump()
        item["setting_key"] = SETTINGS_PK
        item["updated_at"] = now.isoformat()

        self._settings_table.put_item(Item=item)

        logger.info("Settings updated", extra={"settings": item})
