"""Shared pytest fixtures and mock data for manga-video-pipeline tests."""

import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Generator
from unittest.mock import MagicMock, patch

import boto3
import pytest
from moto import mock_aws

# Fix for Python 3.13+ missing audioop module (required by pydub)
import sys
if "pydub" not in sys.modules:
    sys.modules["audioop"] = MagicMock()


# =============================================================================
# Path Constants
# =============================================================================

FIXTURES_DIR = Path(__file__).parent / "fixtures"


# =============================================================================
# Helper Functions
# =============================================================================

def load_fixture(filename: str) -> dict[str, Any]:
    """Load a JSON fixture file."""
    with open(FIXTURES_DIR / filename, encoding="utf-8") as f:
        return json.load(f)


# =============================================================================
# Environment Fixtures
# =============================================================================

@pytest.fixture(autouse=True)
def mock_env_vars(monkeypatch: pytest.MonkeyPatch) -> None:
    """Set required environment variables for all tests."""
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("AWS_SECURITY_TOKEN", "testing")
    monkeypatch.setenv("AWS_SESSION_TOKEN", "testing")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "ap-southeast-1")
    monkeypatch.setenv("S3_BUCKET", "test-manga-pipeline-bucket")


# =============================================================================
# Settings Fixture
# =============================================================================

@pytest.fixture
def mock_settings() -> MagicMock:
    """Return a mock Settings object for testing."""
    settings = MagicMock()
    settings.aws_region = "ap-southeast-1"
    settings.s3_bucket = "test-manga-pipeline-bucket"
    settings.dynamodb_jobs_table = "manga_jobs"
    settings.dynamodb_manga_table = "processed_manga"
    settings.dynamodb_settings_table = "settings"
    settings.deepinfra_secret_name = "manga-pipeline/deepinfra-api-key"
    settings.youtube_secret_name = "manga-pipeline/youtube-oauth"
    settings.admin_secret_name = "manga-pipeline/admin-credentials"
    settings.mangadex_base_url = "https://api.mangadex.org"
    settings.deepinfra_base_url = "https://api.deepinfra.com/v1/openai"
    settings.default_voice_id = "vi-VN-HoaiMyNeural"
    settings.default_tone = "engaging and informative"
    settings.default_daily_quota = 1
    settings.daily_quota = 10
    return settings


# =============================================================================
# AWS Mock Fixtures
# =============================================================================

@pytest.fixture
def mock_dynamodb() -> Generator[boto3.resource, None, None]:
    """Create mocked DynamoDB with all required tables."""
    with mock_aws():
        dynamodb = boto3.resource("dynamodb", region_name="ap-southeast-1")

        # Create manga_jobs table
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

        # Create processed_manga table
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

        # Create settings table
        dynamodb.create_table(
            TableName="settings",
            KeySchema=[{"AttributeName": "setting_key", "KeyType": "HASH"}],
            AttributeDefinitions=[
                {"AttributeName": "setting_key", "AttributeType": "S"},
            ],
            BillingMode="PAY_PER_REQUEST",
        )

        yield dynamodb


@pytest.fixture
def mock_s3() -> Generator[boto3.client, None, None]:
    """Create mocked S3 with test bucket."""
    with mock_aws():
        s3 = boto3.client("s3", region_name="ap-southeast-1")

        # Create test bucket
        s3.create_bucket(
            Bucket="test-manga-pipeline-bucket",
            CreateBucketConfiguration={"LocationConstraint": "ap-southeast-1"},
        )

        yield s3


@pytest.fixture
def mock_secrets() -> Generator[boto3.client, None, None]:
    """Create mocked Secrets Manager with test secrets."""
    with mock_aws():
        secrets = boto3.client("secretsmanager", region_name="ap-southeast-1")

        # DeepInfra API key
        secrets.create_secret(
            Name="manga-pipeline/deepinfra-api-key",
            SecretString=json.dumps({"api_key": "test-deepinfra-api-key-12345"}),
        )

        # YouTube OAuth credentials
        secrets.create_secret(
            Name="manga-pipeline/youtube-oauth",
            SecretString=json.dumps({
                "client_id": "test-client-id.apps.googleusercontent.com",
                "client_secret": "test-client-secret",
                "access_token": "test-access-token",
                "refresh_token": "test-refresh-token",
                "token_uri": "https://oauth2.googleapis.com/token",
                "expiry": "2025-12-31T23:59:59Z",
            }),
        )

        # Admin credentials
        secrets.create_secret(
            Name="manga-pipeline/admin-credentials",
            SecretString=json.dumps({
                "username": "admin",
                # bcrypt hash of "test-password"
                "password_hash": "$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/X4.IAPkU1o3iiYfDa",
            }),
        )

        # JWT secret
        secrets.create_secret(
            Name="manga-pipeline/jwt-secret",
            SecretString=json.dumps({
                "secret_key": "test-jwt-secret-key-for-testing-only",
                "algorithm": "HS256",
            }),
        )

        yield secrets


@pytest.fixture
def mock_ssm() -> Generator[boto3.client, None, None]:
    """Create mocked SSM Parameter Store."""
    with mock_aws():
        ssm = boto3.client("ssm", region_name="ap-southeast-1")

        # Create test parameters
        ssm.put_parameter(
            Name="/manga-video-pipeline/renderer/current-job-id",
            Value="test-job-123",
            Type="String",
        )

        ssm.put_parameter(
            Name="/manga-video-pipeline/renderer/task-token",
            Value="test-task-token",
            Type="SecureString",
        )

        yield ssm


# =============================================================================
# Sample Data Fixtures
# =============================================================================

@pytest.fixture
def sample_manga_info() -> dict[str, Any]:
    """Return sample MangaInfo with 3 chapters, 5 pages each."""
    from src.common.models import ChapterInfo, MangaInfo

    chapters = []
    for i in range(1, 4):
        chapter = ChapterInfo(
            chapter_id=f"chapter-{i:03d}-uuid",
            title=f"Chương {i}: Khởi đầu mới" if i == 1 else f"Chương {i}: Cuộc phiêu lưu tiếp tục",
            chapter_number=str(i),
            page_urls=[
                f"https://uploads.mangadex.org/data/abc123/page-{j}.jpg"
                for j in range(1, 6)
            ],
        )
        chapters.append(chapter)

    manga = MangaInfo(
        manga_id="manga-uuid-12345",
        title="Cuộc Phiêu Lưu Kỳ Diệu",
        description="Một câu chuyện về những anh hùng trẻ tuổi chiến đấu để bảo vệ thế giới.",
        genres=["Action", "Adventure", "Fantasy"],
        cover_url="https://uploads.mangadex.org/covers/manga-uuid/cover.jpg",
        chapters=chapters,
    )

    return manga.model_dump()


@pytest.fixture
def sample_job_record() -> dict[str, Any]:
    """Return sample JobRecord in pending status."""
    from src.common.models import JobRecord, JobStatus

    job = JobRecord(
        job_id="job-2024-01-15-abc123",
        manga_id="manga-uuid-12345",
        manga_title="Cuộc Phiêu Lưu Kỳ Diệu",
        status=JobStatus.pending,
        created_at=datetime(2024, 1, 15, 10, 30, 0, tzinfo=UTC),
        updated_at=datetime(2024, 1, 15, 10, 30, 0, tzinfo=UTC),
        youtube_url=None,
        error_message=None,
        progress_pct=0,
    )

    return job.model_dump()


@pytest.fixture
def sample_script_document() -> dict[str, Any]:
    """Return sample ScriptDocument with 3 segments."""
    from src.common.models import ScriptDocument, ScriptSegment

    segments = [
        ScriptSegment(
            chapter="Chương 1",
            text="Xin chào các bạn! Hôm nay chúng ta sẽ cùng theo dõi câu chuyện tuyệt vời về Cuộc Phiêu Lưu Kỳ Diệu. "
                 "Trong chương đầu tiên, chúng ta gặp nhân vật chính - một chàng trai trẻ với ước mơ trở thành anh hùng.",
            panel_start=0,
            panel_end=4,
        ),
        ScriptSegment(
            chapter="Chương 2",
            text="Tiếp theo, nhân vật chính của chúng ta bắt đầu cuộc hành trình. "
                 "Anh ấy gặp nhiều thử thách nhưng không bao giờ bỏ cuộc. "
                 "Hãy cùng xem anh ấy vượt qua như thế nào nhé!",
            panel_start=5,
            panel_end=9,
        ),
        ScriptSegment(
            chapter="Chương 3",
            text="Trong chương cuối cùng, mọi thứ đã thay đổi. "
                 "Nhân vật chính đã trưởng thành và học được nhiều bài học quý giá. "
                 "Đây là kết thúc của tập này, nhưng câu chuyện vẫn còn tiếp tục!",
            panel_start=10,
            panel_end=14,
        ),
    ]

    script = ScriptDocument(
        job_id="job-2024-01-15-abc123",
        manga_title="Cuộc Phiêu Lưu Kỳ Diệu",
        segments=segments,
    )

    return script.model_dump()


@pytest.fixture
def sample_audio_manifest() -> dict[str, Any]:
    """Return sample AudioManifest with 3 segments."""
    from src.common.models import AudioManifest, AudioSegment

    segments = [
        AudioSegment(
            index=0,
            s3_key="jobs/job-2024-01-15-abc123/audio/segment_000.mp3",
            duration_seconds=45.5,
            chapter="Chương 1",
            panel_start=0,
            panel_end=4,
        ),
        AudioSegment(
            index=1,
            s3_key="jobs/job-2024-01-15-abc123/audio/segment_001.mp3",
            duration_seconds=38.2,
            chapter="Chương 2",
            panel_start=5,
            panel_end=9,
        ),
        AudioSegment(
            index=2,
            s3_key="jobs/job-2024-01-15-abc123/audio/segment_002.mp3",
            duration_seconds=42.8,
            chapter="Chương 3",
            panel_start=10,
            panel_end=14,
        ),
    ]

    manifest = AudioManifest(
        job_id="job-2024-01-15-abc123",
        segments=segments,
        total_duration_seconds=126.5,
    )

    return manifest.model_dump()


@pytest.fixture
def sample_pipeline_settings() -> dict[str, Any]:
    """Return sample PipelineSettings."""
    from src.common.models import PipelineSettings

    settings = PipelineSettings(
        daily_quota=5,
        voice_id="vi-VN-HoaiMyNeural",
        tone="engaging and informative",
        script_style="chapter_walkthrough",
    )

    return settings.model_dump()


# =============================================================================
# API Response Fixtures
# =============================================================================

@pytest.fixture
def mangadex_trending_response() -> dict[str, Any]:
    """Load MangaDex trending API response fixture."""
    return load_fixture("mangadex_trending.json")


@pytest.fixture
def mangadex_chapters_response() -> dict[str, Any]:
    """Load MangaDex chapters API response fixture."""
    return load_fixture("mangadex_chapters.json")


@pytest.fixture
def mangadex_pages_response() -> dict[str, Any]:
    """Load MangaDex at-home/pages API response fixture."""
    return load_fixture("mangadex_pages.json")


@pytest.fixture
def deepinfra_response() -> dict[str, Any]:
    """Load DeepInfra LLM response fixture."""
    return load_fixture("deepinfra_response.json")


# =============================================================================
# File Fixtures
# =============================================================================

@pytest.fixture
def sample_panel_path() -> Path:
    """Return path to sample panel image."""
    return FIXTURES_DIR / "sample_panel.jpg"


@pytest.fixture
def sample_panel_bytes() -> bytes:
    """Return sample panel image as bytes."""
    panel_path = FIXTURES_DIR / "sample_panel.jpg"
    with open(panel_path, "rb") as f:
        return f.read()


# =============================================================================
# Mock Client Fixtures
# =============================================================================

@pytest.fixture
def mock_httpx_client() -> Generator[MagicMock, None, None]:
    """Create a mock httpx client for API testing."""
    with patch("httpx.AsyncClient") as mock_client:
        mock_instance = MagicMock()
        mock_client.return_value.__aenter__.return_value = mock_instance
        yield mock_instance


@pytest.fixture
def mock_edge_tts() -> Generator[MagicMock, None, None]:
    """Create a mock edge-tts Communicate class."""
    with patch("edge_tts.Communicate") as mock_tts:
        mock_instance = MagicMock()
        mock_tts.return_value = mock_instance

        # Mock async save method
        async def mock_save(path: str) -> None:
            # Create a small valid MP3 file header for testing
            with open(path, "wb") as f:
                # Minimal MP3 header
                f.write(b"\xff\xfb\x90\x00" + b"\x00" * 100)

        mock_instance.save = mock_save
        yield mock_tts


# =============================================================================
# Utility Fixtures
# =============================================================================

@pytest.fixture
def temp_dir(tmp_path: Path) -> Path:
    """Return a temporary directory for test files."""
    return tmp_path


@pytest.fixture
def job_id() -> str:
    """Return a consistent test job ID."""
    return "job-2024-01-15-abc123"


@pytest.fixture
def manga_id() -> str:
    """Return a consistent test manga ID."""
    return "manga-uuid-12345"
