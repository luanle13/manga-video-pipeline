"""S3 client wrapper for file operations."""

import json
from pathlib import Path

import boto3

from src.common.config import Settings
from src.common.logging_config import setup_logger

logger = setup_logger(__name__)


class S3Client:
    """Client wrapper for S3 file operations."""

    def __init__(self, settings: Settings) -> None:
        """
        Initialize the S3 client.

        Args:
            settings: Application settings containing bucket name and region.
        """
        self._settings = settings
        self._bucket = settings.s3_bucket
        self._client = boto3.client("s3", region_name=settings.aws_region)

        logger.info(
            "S3 client initialized",
            extra={"bucket": self._bucket, "region": settings.aws_region},
        )

    def _s3_uri(self, s3_key: str) -> str:
        """Generate S3 URI for a key."""
        return f"s3://{self._bucket}/{s3_key}"

    def upload_file(self, local_path: str, s3_key: str) -> str:
        """
        Upload a local file to S3.

        Args:
            local_path: Path to the local file.
            s3_key: S3 object key.

        Returns:
            Full S3 URI of the uploaded file.
        """
        file_path = Path(local_path)
        file_size = file_path.stat().st_size

        self._client.upload_file(local_path, self._bucket, s3_key)

        logger.info(
            "File uploaded to S3",
            extra={"s3_key": s3_key, "size_bytes": file_size, "operation": "upload_file"},
        )
        return self._s3_uri(s3_key)

    def upload_bytes(
        self, data: bytes, s3_key: str, content_type: str = "application/octet-stream"
    ) -> str:
        """
        Upload bytes data to S3.

        Args:
            data: Bytes data to upload.
            s3_key: S3 object key.
            content_type: MIME content type.

        Returns:
            Full S3 URI of the uploaded object.
        """
        self._client.put_object(
            Bucket=self._bucket,
            Key=s3_key,
            Body=data,
            ContentType=content_type,
        )

        logger.info(
            "Bytes uploaded to S3",
            extra={
                "s3_key": s3_key,
                "size_bytes": len(data),
                "content_type": content_type,
                "operation": "upload_bytes",
            },
        )
        return self._s3_uri(s3_key)

    def upload_json(self, data: dict | list, s3_key: str) -> str:
        """
        Upload JSON data to S3.

        Args:
            data: Dictionary or list to serialize as JSON.
            s3_key: S3 object key.

        Returns:
            Full S3 URI of the uploaded object.
        """
        json_bytes = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")

        self._client.put_object(
            Bucket=self._bucket,
            Key=s3_key,
            Body=json_bytes,
            ContentType="application/json",
        )

        logger.info(
            "JSON uploaded to S3",
            extra={
                "s3_key": s3_key,
                "size_bytes": len(json_bytes),
                "operation": "upload_json",
            },
        )
        return self._s3_uri(s3_key)

    def download_file(self, s3_key: str, local_path: str) -> str:
        """
        Download a file from S3 to local path.

        Args:
            s3_key: S3 object key.
            local_path: Local path to save the file.

        Returns:
            The local path where the file was saved.
        """
        # Ensure parent directory exists
        Path(local_path).parent.mkdir(parents=True, exist_ok=True)

        self._client.download_file(self._bucket, s3_key, local_path)

        file_size = Path(local_path).stat().st_size
        logger.info(
            "File downloaded from S3",
            extra={
                "s3_key": s3_key,
                "local_path": local_path,
                "size_bytes": file_size,
                "operation": "download_file",
            },
        )
        return local_path

    def download_bytes(self, s3_key: str) -> bytes:
        """
        Download object from S3 as bytes.

        Args:
            s3_key: S3 object key.

        Returns:
            The object data as bytes.
        """
        response = self._client.get_object(Bucket=self._bucket, Key=s3_key)
        data = response["Body"].read()

        logger.info(
            "Bytes downloaded from S3",
            extra={"s3_key": s3_key, "size_bytes": len(data), "operation": "download_bytes"},
        )
        return data

    def download_json(self, s3_key: str) -> dict | list:
        """
        Download and parse JSON object from S3.

        Args:
            s3_key: S3 object key.

        Returns:
            Parsed JSON data as dict or list.
        """
        response = self._client.get_object(Bucket=self._bucket, Key=s3_key)
        data = response["Body"].read()
        parsed = json.loads(data.decode("utf-8"))

        logger.info(
            "JSON downloaded from S3",
            extra={"s3_key": s3_key, "size_bytes": len(data), "operation": "download_json"},
        )
        return parsed

    def delete_prefix(self, prefix: str) -> int:
        """
        Delete all objects under a prefix.

        Args:
            prefix: S3 key prefix to delete.

        Returns:
            Number of objects deleted.
        """
        deleted_count = 0
        paginator = self._client.get_paginator("list_objects_v2")

        for page in paginator.paginate(Bucket=self._bucket, Prefix=prefix):
            contents = page.get("Contents", [])
            if not contents:
                continue

            # Delete in batches of up to 1000 (S3 limit)
            objects_to_delete = [{"Key": obj["Key"]} for obj in contents]

            self._client.delete_objects(
                Bucket=self._bucket,
                Delete={"Objects": objects_to_delete},
            )
            deleted_count += len(objects_to_delete)

        logger.info(
            "Objects deleted from S3",
            extra={"prefix": prefix, "deleted_count": deleted_count, "operation": "delete_prefix"},
        )
        return deleted_count

    def list_objects(self, prefix: str) -> list[str]:
        """
        List all object keys under a prefix.

        Args:
            prefix: S3 key prefix to list.

        Returns:
            List of object keys.
        """
        keys: list[str] = []
        paginator = self._client.get_paginator("list_objects_v2")

        for page in paginator.paginate(Bucket=self._bucket, Prefix=prefix):
            contents = page.get("Contents", [])
            keys.extend(obj["Key"] for obj in contents)

        logger.info(
            "Objects listed from S3",
            extra={"prefix": prefix, "count": len(keys), "operation": "list_objects"},
        )
        return keys

    def get_presigned_url(self, s3_key: str, expires_in: int = 3600) -> str:
        """
        Generate a presigned URL for an S3 object.

        Args:
            s3_key: S3 object key.
            expires_in: URL expiration time in seconds (default: 1 hour).

        Returns:
            Presigned URL string.
        """
        url = self._client.generate_presigned_url(
            "get_object",
            Params={"Bucket": self._bucket, "Key": s3_key},
            ExpiresIn=expires_in,
        )

        logger.info(
            "Presigned URL generated",
            extra={"s3_key": s3_key, "expires_in": expires_in, "operation": "get_presigned_url"},
        )
        return url
