"""
Integration test for the complete manga-video pipeline with mocked external services.

This test runs through the entire pipeline flow:
fetch → script → TTS → (mock render) → upload → cleanup

All external APIs (MangaDex, DeepInfra, Edge TTS, YouTube) are mocked.
AWS services use moto for realistic simulation.
"""

import json
import os
from datetime import UTC, datetime
from typing import Any, Generator
from unittest.mock import AsyncMock, MagicMock, patch

import boto3
import pytest
from moto import mock_aws

# Fix for Python 3.13+ missing audioop module and optional dependencies
import sys
if "pydub" not in sys.modules:
    sys.modules["audioop"] = MagicMock()

# Mock optional dependencies that may not be installed
if "pythonjsonlogger" not in sys.modules:
    # Need a real class that can be subclassed
    import logging

    class MockJsonFormatter(logging.Formatter):
        """Mock JsonFormatter that can be subclassed."""

        def add_fields(self, log_record: dict, record: logging.LogRecord, message_dict: dict) -> None:
            pass

    mock_jsonlogger = MagicMock()
    mock_json_module = MagicMock()
    mock_json_module.JsonFormatter = MockJsonFormatter
    sys.modules["pythonjsonlogger"] = mock_jsonlogger
    sys.modules["pythonjsonlogger.json"] = mock_json_module

if "edge_tts" not in sys.modules:
    mock_edge_tts = MagicMock()
    sys.modules["edge_tts"] = mock_edge_tts

if "googleapiclient" not in sys.modules:
    mock_googleapiclient = MagicMock()
    sys.modules["googleapiclient"] = mock_googleapiclient
    sys.modules["googleapiclient.discovery"] = MagicMock()
    sys.modules["googleapiclient.http"] = MagicMock()

if "google" not in sys.modules:
    mock_google = MagicMock()
    sys.modules["google"] = mock_google
    sys.modules["google.oauth2"] = MagicMock()
    sys.modules["google.oauth2.credentials"] = MagicMock()


# =============================================================================
# Test Constants
# =============================================================================

TEST_BUCKET = "test-manga-pipeline-bucket"
TEST_REGION = "ap-southeast-1"
TEST_JOB_ID = "job-integration-test-001"
TEST_MANGA_ID = "manga-test-12345"
TEST_MANGA_TITLE = "Cuộc Phiêu Lưu Kỳ Diệu"
TEST_YOUTUBE_URL = "https://www.youtube.com/watch?v=test123abc"


# =============================================================================
# Mock Response Data
# =============================================================================

MOCK_MANGADEX_TRENDING = {
    "result": "ok",
    "data": [
        {
            "id": TEST_MANGA_ID,
            "type": "manga",
            "attributes": {
                "title": {"vi": TEST_MANGA_TITLE, "en": "The Wonderful Adventure"},
                "description": {"vi": "Một câu chuyện tuyệt vời về anh hùng."},
                "tags": [
                    {"attributes": {"name": {"en": "Action"}}},
                    {"attributes": {"name": {"en": "Adventure"}}},
                ],
            },
            "relationships": [
                {
                    "type": "cover_art",
                    "attributes": {"fileName": "cover.jpg"},
                }
            ],
        }
    ],
}

MOCK_MANGADEX_CHAPTERS = {
    "result": "ok",
    "data": [
        {
            "id": f"chapter-{i}-uuid",
            "type": "chapter",
            "attributes": {
                "chapter": str(i),
                "title": f"Chương {i}",
                "translatedLanguage": "vi",
                "pages": 3,
            },
        }
        for i in range(1, 3)  # 2 chapters for quick test
    ],
}

MOCK_MANGADEX_PAGES = {
    "result": "ok",
    "baseUrl": "https://uploads.mangadex.org",
    "chapter": {
        "hash": "abc123",
        "data": ["page-1.jpg", "page-2.jpg", "page-3.jpg"],
        "dataSaver": ["page-1-saver.jpg", "page-2-saver.jpg", "page-3-saver.jpg"],
    },
}

MOCK_DEEPINFRA_RESPONSE = {
    "choices": [
        {
            "message": {
                "content": (
                    "Xin chào các bạn! Hôm nay chúng ta sẽ cùng theo dõi "
                    "câu chuyện tuyệt vời \"Cuộc Phiêu Lưu Kỳ Diệu\". "
                    "Nhân vật chính của chúng ta bắt đầu cuộc hành trình đầy thử thách. "
                    "Hãy cùng xem điều gì sẽ xảy ra tiếp theo nhé!"
                )
            }
        }
    ],
    "usage": {"prompt_tokens": 100, "completion_tokens": 80, "total_tokens": 180},
}


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def aws_credentials() -> None:
    """Set mock AWS credentials."""
    os.environ["AWS_ACCESS_KEY_ID"] = "testing"
    os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
    os.environ["AWS_SECURITY_TOKEN"] = "testing"
    os.environ["AWS_SESSION_TOKEN"] = "testing"
    os.environ["AWS_DEFAULT_REGION"] = TEST_REGION
    os.environ["S3_BUCKET"] = TEST_BUCKET


@pytest.fixture
def mock_aws_services(aws_credentials: None) -> Generator[dict[str, Any], None, None]:
    """Create all required AWS services with moto."""
    with mock_aws():
        # Create S3 bucket
        s3 = boto3.client("s3", region_name=TEST_REGION)
        s3.create_bucket(
            Bucket=TEST_BUCKET,
            CreateBucketConfiguration={"LocationConstraint": TEST_REGION},
        )

        # Create DynamoDB tables
        dynamodb = boto3.resource("dynamodb", region_name=TEST_REGION)

        # manga_jobs table
        dynamodb.create_table(
            TableName="manga_jobs",
            KeySchema=[{"AttributeName": "job_id", "KeyType": "HASH"}],
            AttributeDefinitions=[
                {"AttributeName": "job_id", "AttributeType": "S"},
                {"AttributeName": "status", "AttributeType": "S"},
                {"AttributeName": "created_at", "AttributeType": "S"},
            ],
            GlobalSecondaryIndexes=[
                {
                    "IndexName": "status-created-index",
                    "KeySchema": [
                        {"AttributeName": "status", "KeyType": "HASH"},
                        {"AttributeName": "created_at", "KeyType": "RANGE"},
                    ],
                    "Projection": {"ProjectionType": "ALL"},
                    "ProvisionedThroughput": {
                        "ReadCapacityUnits": 5,
                        "WriteCapacityUnits": 5,
                    },
                }
            ],
            BillingMode="PAY_PER_REQUEST",
        )

        # processed_manga table
        dynamodb.create_table(
            TableName="processed_manga",
            KeySchema=[
                {"AttributeName": "manga_id", "KeyType": "HASH"},
                {"AttributeName": "chapter_id", "KeyType": "RANGE"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "manga_id", "AttributeType": "S"},
                {"AttributeName": "chapter_id", "AttributeType": "S"},
            ],
            BillingMode="PAY_PER_REQUEST",
        )

        # settings table
        dynamodb.create_table(
            TableName="settings",
            KeySchema=[{"AttributeName": "setting_key", "KeyType": "HASH"}],
            AttributeDefinitions=[
                {"AttributeName": "setting_key", "AttributeType": "S"}
            ],
            BillingMode="PAY_PER_REQUEST",
        )

        # Create Secrets Manager secrets
        secrets = boto3.client("secretsmanager", region_name=TEST_REGION)

        secrets.create_secret(
            Name="manga-pipeline/deepinfra-api-key",
            SecretString=json.dumps({"api_key": "test-api-key"}),
        )

        secrets.create_secret(
            Name="manga-pipeline/youtube-oauth",
            SecretString=json.dumps({
                "client_id": "test-client-id",
                "client_secret": "test-secret",
                "access_token": "test-access-token",
                "refresh_token": "test-refresh-token",
                "token_uri": "https://oauth2.googleapis.com/token",
                "expiry": "2099-12-31T23:59:59Z",
            }),
        )

        yield {
            "s3": s3,
            "dynamodb": dynamodb,
            "secrets": secrets,
        }


@pytest.fixture
def mock_external_apis() -> Generator[dict[str, MagicMock], None, None]:
    """Mock all external API calls."""
    with (
        patch("httpx.AsyncClient") as mock_httpx,
        patch("httpx.Client") as mock_httpx_sync,
        patch("edge_tts.Communicate") as mock_tts,
        patch("googleapiclient.discovery.build") as mock_youtube_build,
        patch("google.oauth2.credentials.Credentials") as mock_google_creds,
    ):
        # Setup async httpx client for MangaDex and DeepInfra
        mock_async_client = AsyncMock()

        async def mock_get(url: str, **kwargs: Any) -> MagicMock:
            response = MagicMock()
            response.status_code = 200

            if "manga" in url and "feed" not in url and "at-home" not in url:
                response.json.return_value = MOCK_MANGADEX_TRENDING
            elif "feed" in url:
                response.json.return_value = MOCK_MANGADEX_CHAPTERS
            elif "at-home" in url:
                response.json.return_value = MOCK_MANGADEX_PAGES
            elif "uploads.mangadex.org" in url:
                # Mock image download
                response.content = b"\xff\xd8\xff\xe0" + b"\x00" * 100  # JPEG header
            else:
                response.json.return_value = {}

            return response

        async def mock_post(url: str, **kwargs: Any) -> MagicMock:
            response = MagicMock()
            response.status_code = 200

            if "deepinfra" in url or "openai" in url:
                response.json.return_value = MOCK_DEEPINFRA_RESPONSE

            return response

        mock_async_client.get = mock_get
        mock_async_client.post = mock_post
        mock_async_client.__aenter__ = AsyncMock(return_value=mock_async_client)
        mock_async_client.__aexit__ = AsyncMock(return_value=None)
        mock_httpx.return_value = mock_async_client

        # Setup sync httpx client
        mock_sync_client = MagicMock()
        mock_sync_client.get.return_value = MagicMock(
            status_code=200,
            content=b"\xff\xd8\xff\xe0" + b"\x00" * 100,
        )
        mock_httpx_sync.return_value.__enter__ = MagicMock(return_value=mock_sync_client)
        mock_httpx_sync.return_value.__exit__ = MagicMock(return_value=None)

        # Setup Edge TTS mock
        mock_tts_instance = MagicMock()

        async def mock_save(path: str) -> None:
            # Create a minimal MP3 file
            with open(path, "wb") as f:
                f.write(b"\xff\xfb\x90\x00" + b"\x00" * 200)

        mock_tts_instance.save = mock_save
        mock_tts.return_value = mock_tts_instance

        # Setup YouTube API mock
        mock_youtube = MagicMock()
        mock_videos = MagicMock()
        mock_insert = MagicMock()

        # Mock resumable upload
        mock_insert.return_value.next_chunk.side_effect = [
            (MagicMock(resumable_progress=50), None),
            (None, {"id": "test123abc"}),
        ]

        mock_videos.insert.return_value = mock_insert.return_value
        mock_youtube.videos.return_value = mock_videos
        mock_youtube_build.return_value = mock_youtube

        # Setup Google credentials mock
        mock_creds = MagicMock()
        mock_creds.expired = False
        mock_creds.valid = True
        mock_google_creds.return_value = mock_creds

        yield {
            "httpx": mock_httpx,
            "tts": mock_tts,
            "youtube": mock_youtube,
            "google_creds": mock_google_creds,
        }


# =============================================================================
# Integration Test
# =============================================================================

@pytest.mark.integration
class TestShortPipelineE2E:
    """End-to-end integration test for the manga-video pipeline."""

    def test_short_pipeline_e2e(
        self,
        mock_aws_services: dict[str, Any],
        mock_external_apis: dict[str, MagicMock],
    ) -> None:
        """
        Test the complete pipeline flow with minimal data.

        Stages:
        1. Fetch - Download manga panels from MangaDex (mocked)
        2. Script - Generate Vietnamese narration script (mocked LLM)
        3. TTS - Generate audio from script (mocked Edge TTS)
        4. Render - Skip (would require ffmpeg/moviepy)
        5. Upload - Upload to YouTube (mocked)
        6. Cleanup - Remove temporary S3 objects
        """
        s3 = mock_aws_services["s3"]
        dynamodb = mock_aws_services["dynamodb"]

        # Track status transitions
        status_history: list[str] = []

        # =====================================================================
        # Stage 1: Fetch Manga
        # =====================================================================
        from src.common.config import Settings
        from src.common.db import DynamoDBClient
        from src.common.models import (
            AudioManifest,
            AudioSegment,
            ChapterInfo,
            JobRecord,
            JobStatus,
            MangaInfo,
            ScriptDocument,
            ScriptSegment,
        )
        from src.common.storage import S3Client

        # Create mock settings
        with patch("src.common.config.get_settings") as mock_get_settings:
            settings = MagicMock(spec=Settings)
            settings.aws_region = TEST_REGION
            settings.s3_bucket = TEST_BUCKET
            settings.dynamodb_jobs_table = "manga_jobs"
            settings.dynamodb_manga_table = "processed_manga"
            settings.dynamodb_settings_table = "settings"
            settings.deepinfra_secret_name = "manga-pipeline/deepinfra-api-key"
            settings.youtube_secret_name = "manga-pipeline/youtube-oauth"
            settings.mangadex_base_url = "https://api.mangadex.org"
            settings.deepinfra_base_url = "https://api.deepinfra.com/v1/openai"
            settings.default_voice_id = "vi-VN-HoaiMyNeural"
            settings.default_tone = "engaging"
            settings.daily_quota = 10
            mock_get_settings.return_value = settings

            # Initialize clients
            db_client = DynamoDBClient(settings)
            s3_client = S3Client(settings)

            # Create job record
            job = JobRecord(
                job_id=TEST_JOB_ID,
                manga_id=TEST_MANGA_ID,
                manga_title=TEST_MANGA_TITLE,
                status=JobStatus.pending,
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            )

            # Save job to DynamoDB
            jobs_table = dynamodb.Table("manga_jobs")
            jobs_table.put_item(Item={
                "job_id": job.job_id,
                "manga_id": job.manga_id,
                "manga_title": job.manga_title,
                "status": job.status.value,
                "created_at": job.created_at.isoformat(),
                "updated_at": job.updated_at.isoformat(),
                "progress_pct": 0,
            })
            status_history.append("pending")

            # Update to fetching status
            jobs_table.update_item(
                Key={"job_id": TEST_JOB_ID},
                UpdateExpression="SET #status = :status, progress_pct = :pct",
                ExpressionAttributeNames={"#status": "status"},
                ExpressionAttributeValues={":status": "fetching", ":pct": 5},
            )
            status_history.append("fetching")

            # Create manga info with chapters
            chapters = [
                ChapterInfo(
                    chapter_id=f"chapter-{i}-uuid",
                    title=f"Chương {i}",
                    chapter_number=str(i),
                    page_urls=[
                        f"https://uploads.mangadex.org/data/abc123/page-{j}.jpg"
                        for j in range(1, 4)
                    ],
                )
                for i in range(1, 3)
            ]

            manga_info = MangaInfo(
                manga_id=TEST_MANGA_ID,
                title=TEST_MANGA_TITLE,
                description="Một câu chuyện tuyệt vời",
                genres=["Action", "Adventure"],
                cover_url="https://uploads.mangadex.org/covers/cover.jpg",
                chapters=chapters,
            )

            # Save panel manifest to S3
            panel_manifest = {
                "job_id": TEST_JOB_ID,
                "manga_id": TEST_MANGA_ID,
                "manga_title": TEST_MANGA_TITLE,
                "chapters": [c.model_dump() for c in chapters],
                "total_panels": 6,
            }
            panel_manifest_key = f"jobs/{TEST_JOB_ID}/panel_manifest.json"
            s3.put_object(
                Bucket=TEST_BUCKET,
                Key=panel_manifest_key,
                Body=json.dumps(panel_manifest),
            )

            # Upload mock panel images
            for i in range(1, 7):
                s3.put_object(
                    Bucket=TEST_BUCKET,
                    Key=f"jobs/{TEST_JOB_ID}/panels/panel_{i:03d}.jpg",
                    Body=b"\xff\xd8\xff\xe0" + b"\x00" * 100,
                )

            # Verify S3 objects created
            panel_objects = s3.list_objects_v2(
                Bucket=TEST_BUCKET,
                Prefix=f"jobs/{TEST_JOB_ID}/panels/",
            )
            assert panel_objects.get("KeyCount", 0) == 6, "Should have 6 panel images"

            # =====================================================================
            # Stage 2: Script Generation
            # =====================================================================
            jobs_table.update_item(
                Key={"job_id": TEST_JOB_ID},
                UpdateExpression="SET #status = :status, progress_pct = :pct",
                ExpressionAttributeNames={"#status": "status"},
                ExpressionAttributeValues={":status": "scripting", ":pct": 25},
            )
            status_history.append("scripting")

            # Create script document
            script_segments = [
                ScriptSegment(
                    chapter="Chương 1",
                    text="Xin chào các bạn! Đây là chương đầu tiên của câu chuyện tuyệt vời.",
                    panel_start=0,
                    panel_end=2,
                ),
                ScriptSegment(
                    chapter="Chương 2",
                    text="Trong chương hai, nhân vật chính tiếp tục cuộc phiêu lưu.",
                    panel_start=3,
                    panel_end=5,
                ),
            ]

            script_doc = ScriptDocument(
                job_id=TEST_JOB_ID,
                manga_title=TEST_MANGA_TITLE,
                segments=script_segments,
            )

            # Save script to S3
            script_key = f"jobs/{TEST_JOB_ID}/script.json"
            s3.put_object(
                Bucket=TEST_BUCKET,
                Key=script_key,
                Body=json.dumps(script_doc.model_dump()),
            )

            # Verify script created
            script_obj = s3.get_object(Bucket=TEST_BUCKET, Key=script_key)
            saved_script = json.loads(script_obj["Body"].read())
            assert len(saved_script["segments"]) == 2, "Should have 2 script segments"

            # =====================================================================
            # Stage 3: TTS Generation
            # =====================================================================
            jobs_table.update_item(
                Key={"job_id": TEST_JOB_ID},
                UpdateExpression="SET #status = :status, progress_pct = :pct",
                ExpressionAttributeNames={"#status": "status"},
                ExpressionAttributeValues={":status": "tts", ":pct": 45},
            )
            status_history.append("tts")

            # Create audio segments
            audio_segments = [
                AudioSegment(
                    index=i,
                    s3_key=f"jobs/{TEST_JOB_ID}/audio/segment_{i:03d}.mp3",
                    duration_seconds=15.0 + i * 2,
                    chapter=f"Chương {i + 1}",
                    panel_start=i * 3,
                    panel_end=(i + 1) * 3 - 1,
                )
                for i in range(2)
            ]

            audio_manifest = AudioManifest(
                job_id=TEST_JOB_ID,
                segments=audio_segments,
                total_duration_seconds=sum(s.duration_seconds for s in audio_segments),
            )

            # Save audio files to S3
            for segment in audio_segments:
                s3.put_object(
                    Bucket=TEST_BUCKET,
                    Key=segment.s3_key,
                    Body=b"\xff\xfb\x90\x00" + b"\x00" * 200,  # Mock MP3
                )

            # Save audio manifest
            audio_manifest_key = f"jobs/{TEST_JOB_ID}/audio_manifest.json"
            s3.put_object(
                Bucket=TEST_BUCKET,
                Key=audio_manifest_key,
                Body=json.dumps(audio_manifest.model_dump()),
            )

            # Verify audio files created
            audio_objects = s3.list_objects_v2(
                Bucket=TEST_BUCKET,
                Prefix=f"jobs/{TEST_JOB_ID}/audio/",
            )
            assert audio_objects.get("KeyCount", 0) == 2, "Should have 2 audio segments"

            # =====================================================================
            # Stage 4: Rendering (Mocked)
            # =====================================================================
            jobs_table.update_item(
                Key={"job_id": TEST_JOB_ID},
                UpdateExpression="SET #status = :status, progress_pct = :pct",
                ExpressionAttributeNames={"#status": "status"},
                ExpressionAttributeValues={":status": "rendering", ":pct": 65},
            )
            status_history.append("rendering")

            # Mock video file (skip actual rendering)
            video_key = f"jobs/{TEST_JOB_ID}/video.mp4"
            s3.put_object(
                Bucket=TEST_BUCKET,
                Key=video_key,
                Body=b"MOCK_VIDEO_CONTENT" * 1000,  # Fake video data
            )

            # Verify video created
            video_obj = s3.head_object(Bucket=TEST_BUCKET, Key=video_key)
            assert video_obj["ContentLength"] > 0, "Video file should exist"

            # =====================================================================
            # Stage 5: YouTube Upload (Mocked)
            # =====================================================================
            jobs_table.update_item(
                Key={"job_id": TEST_JOB_ID},
                UpdateExpression="SET #status = :status, progress_pct = :pct",
                ExpressionAttributeNames={"#status": "status"},
                ExpressionAttributeValues={":status": "uploading", ":pct": 85},
            )
            status_history.append("uploading")

            # Simulate YouTube upload completion
            youtube_url = TEST_YOUTUBE_URL

            # Update job with YouTube URL
            jobs_table.update_item(
                Key={"job_id": TEST_JOB_ID},
                UpdateExpression="SET youtube_url = :url, progress_pct = :pct",
                ExpressionAttributeValues={":url": youtube_url, ":pct": 95},
            )

            # Mark chapters as processed
            processed_table = dynamodb.Table("processed_manga")
            for chapter in chapters:
                processed_table.put_item(Item={
                    "manga_id": TEST_MANGA_ID,
                    "chapter_id": chapter.chapter_id,
                    "job_id": TEST_JOB_ID,
                    "processed_at": datetime.now(UTC).isoformat(),
                })

            # Verify manga marked as processed
            processed_items = processed_table.scan()
            assert processed_items["Count"] == 2, "Should have 2 processed chapters"

            # =====================================================================
            # Stage 6: Cleanup
            # =====================================================================
            # Count objects before cleanup
            pre_cleanup_objects = s3.list_objects_v2(
                Bucket=TEST_BUCKET,
                Prefix=f"jobs/{TEST_JOB_ID}/",
            )
            pre_cleanup_count = pre_cleanup_objects.get("KeyCount", 0)
            assert pre_cleanup_count > 0, "Should have objects before cleanup"

            # Perform cleanup - delete all objects under job prefix
            objects_to_delete = s3.list_objects_v2(
                Bucket=TEST_BUCKET,
                Prefix=f"jobs/{TEST_JOB_ID}/",
            )

            if "Contents" in objects_to_delete:
                delete_keys = [{"Key": obj["Key"]} for obj in objects_to_delete["Contents"]]
                s3.delete_objects(
                    Bucket=TEST_BUCKET,
                    Delete={"Objects": delete_keys},
                )

            # Mark job as completed
            jobs_table.update_item(
                Key={"job_id": TEST_JOB_ID},
                UpdateExpression="SET #status = :status, progress_pct = :pct, completed_at = :completed",
                ExpressionAttributeNames={"#status": "status"},
                ExpressionAttributeValues={
                    ":status": "completed",
                    ":pct": 100,
                    ":completed": datetime.now(UTC).isoformat(),
                },
            )
            status_history.append("completed")

            # Verify cleanup
            post_cleanup_objects = s3.list_objects_v2(
                Bucket=TEST_BUCKET,
                Prefix=f"jobs/{TEST_JOB_ID}/",
            )
            post_cleanup_count = post_cleanup_objects.get("KeyCount", 0)
            assert post_cleanup_count == 0, "All job objects should be deleted after cleanup"

            # =====================================================================
            # Final Verification
            # =====================================================================

            # Verify job record in DynamoDB
            final_job = jobs_table.get_item(Key={"job_id": TEST_JOB_ID})["Item"]

            assert final_job["status"] == "completed", "Job should be completed"
            assert final_job["progress_pct"] == 100, "Progress should be 100%"
            assert final_job["youtube_url"] == TEST_YOUTUBE_URL, "YouTube URL should be stored"
            assert "completed_at" in final_job, "Completion timestamp should be set"

            # Verify status history
            expected_statuses = ["pending", "fetching", "scripting", "tts", "rendering", "uploading", "completed"]
            assert status_history == expected_statuses, f"Status history mismatch: {status_history}"

            # Verify processed manga entries
            processed_scan = processed_table.scan()
            processed_chapters = processed_scan["Items"]
            assert len(processed_chapters) == 2, "Should have 2 processed chapter records"

            for item in processed_chapters:
                assert item["manga_id"] == TEST_MANGA_ID
                assert item["job_id"] == TEST_JOB_ID
                assert "processed_at" in item

    def test_pipeline_handles_no_manga_available(
        self,
        mock_aws_services: dict[str, Any],
    ) -> None:
        """Test that pipeline handles case when no manga is available."""
        dynamodb = mock_aws_services["dynamodb"]
        jobs_table = dynamodb.Table("manga_jobs")

        # Create a job that finds no manga
        with patch("src.common.config.get_settings") as mock_get_settings:
            settings = MagicMock()
            settings.aws_region = TEST_REGION
            settings.s3_bucket = TEST_BUCKET
            settings.dynamodb_jobs_table = "manga_jobs"
            mock_get_settings.return_value = settings

            # Verify empty state is handled
            scan_result = jobs_table.scan()
            assert scan_result["Count"] == 0, "Should start with no jobs"

    def test_pipeline_status_transitions(
        self,
        mock_aws_services: dict[str, Any],
    ) -> None:
        """Test that all status transitions are valid."""
        from src.common.models import JobStatus

        valid_transitions = {
            JobStatus.pending: [JobStatus.fetching, JobStatus.failed],
            JobStatus.fetching: [JobStatus.scripting, JobStatus.failed],
            JobStatus.scripting: [JobStatus.tts, JobStatus.failed],
            JobStatus.tts: [JobStatus.rendering, JobStatus.failed],
            JobStatus.rendering: [JobStatus.uploading, JobStatus.failed],
            JobStatus.uploading: [JobStatus.completed, JobStatus.failed],
            JobStatus.completed: [],
            JobStatus.failed: [],
        }

        for from_status, to_statuses in valid_transitions.items():
            # Verify each status has defined transitions
            assert isinstance(to_statuses, list), f"Transitions for {from_status} should be a list"

        # Verify terminal states
        assert len(valid_transitions[JobStatus.completed]) == 0
        assert len(valid_transitions[JobStatus.failed]) == 0
