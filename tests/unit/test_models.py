"""Tests for Pydantic data models."""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from src.common.models import (
    AudioManifest,
    AudioSegment,
    ChapterInfo,
    JobRecord,
    JobStatus,
    MangaInfo,
    PipelineSettings,
    ScriptDocument,
    ScriptSegment,
)


class TestChapterInfo:
    """Tests for ChapterInfo model."""

    def test_valid_construction(self) -> None:
        """Test valid ChapterInfo construction."""
        chapter = ChapterInfo(
            chapter_id="ch-123",
            title="Chapter 1: The Beginning",
            chapter_number="1",
            page_urls=["https://example.com/page1.jpg", "https://example.com/page2.jpg"],
        )
        assert chapter.chapter_id == "ch-123"
        assert chapter.title == "Chapter 1: The Beginning"
        assert chapter.chapter_number == "1"
        assert len(chapter.page_urls) == 2

    def test_chapter_number_optional(self) -> None:
        """Test that chapter_number can be None."""
        chapter = ChapterInfo(
            chapter_id="ch-123",
            title="Prologue",
            chapter_number=None,
            page_urls=[],
        )
        assert chapter.chapter_number is None

    def test_serialization_to_dict(self) -> None:
        """Test serialization to dictionary."""
        chapter = ChapterInfo(
            chapter_id="ch-123",
            title="Chapter 1",
            chapter_number="1",
            page_urls=["https://example.com/page1.jpg"],
        )
        data = chapter.model_dump()
        assert data == {
            "chapter_id": "ch-123",
            "title": "Chapter 1",
            "chapter_number": "1",
            "page_urls": ["https://example.com/page1.jpg"],
        }

    def test_serialization_to_json(self) -> None:
        """Test serialization to JSON."""
        chapter = ChapterInfo(
            chapter_id="ch-123",
            title="Chapter 1",
            chapter_number="1",
            page_urls=[],
        )
        json_str = chapter.model_dump_json()
        assert '"chapter_id":"ch-123"' in json_str


class TestMangaInfo:
    """Tests for MangaInfo model."""

    def test_valid_construction(self) -> None:
        """Test valid MangaInfo construction."""
        manga = MangaInfo(
            manga_id="manga-456",
            title="One Piece",
            description="A pirate adventure manga",
            genres=["Action", "Adventure", "Comedy"],
            cover_url="https://example.com/cover.jpg",
            chapters=[
                ChapterInfo(
                    chapter_id="ch-1",
                    title="Chapter 1",
                    chapter_number="1",
                    page_urls=["https://example.com/p1.jpg"],
                )
            ],
        )
        assert manga.manga_id == "manga-456"
        assert manga.title == "One Piece"
        assert len(manga.genres) == 3
        assert len(manga.chapters) == 1

    def test_cover_url_optional(self) -> None:
        """Test that cover_url can be None."""
        manga = MangaInfo(
            manga_id="manga-456",
            title="Test Manga",
            description="Description",
            genres=[],
            cover_url=None,
            chapters=[],
        )
        assert manga.cover_url is None

    def test_serialization_to_dict(self) -> None:
        """Test serialization to dictionary."""
        manga = MangaInfo(
            manga_id="manga-456",
            title="Test",
            description="Desc",
            genres=["Action"],
            cover_url=None,
            chapters=[],
        )
        data = manga.model_dump()
        assert data["manga_id"] == "manga-456"
        assert data["chapters"] == []


class TestJobStatus:
    """Tests for JobStatus enum."""

    def test_enum_values(self) -> None:
        """Test all enum values exist."""
        assert JobStatus.pending == "pending"
        assert JobStatus.fetching == "fetching"
        assert JobStatus.scripting == "scripting"
        assert JobStatus.tts == "tts"
        assert JobStatus.rendering == "rendering"
        assert JobStatus.uploading == "uploading"
        assert JobStatus.completed == "completed"
        assert JobStatus.failed == "failed"

    def test_enum_is_str(self) -> None:
        """Test that JobStatus values are strings."""
        assert isinstance(JobStatus.pending, str)
        assert JobStatus.pending == "pending"

    def test_all_statuses_count(self) -> None:
        """Test that we have exactly 8 statuses."""
        assert len(JobStatus) == 8


class TestJobRecord:
    """Tests for JobRecord model."""

    def test_valid_construction(self) -> None:
        """Test valid JobRecord construction."""
        job = JobRecord(
            job_id="job-789",
            manga_id="manga-456",
            manga_title="One Piece",
        )
        assert job.job_id == "job-789"
        assert job.manga_id == "manga-456"
        assert job.manga_title == "One Piece"
        assert job.status == JobStatus.pending
        assert job.youtube_url is None
        assert job.error_message is None
        assert job.progress_pct == 0

    def test_default_timestamps(self) -> None:
        """Test that timestamps are set by default."""
        job = JobRecord(
            job_id="job-789",
            manga_id="manga-456",
            manga_title="Test",
        )
        assert job.created_at is not None
        assert job.updated_at is not None
        assert job.created_at.tzinfo == UTC

    def test_custom_status(self) -> None:
        """Test setting a custom status."""
        job = JobRecord(
            job_id="job-789",
            manga_id="manga-456",
            manga_title="Test",
            status=JobStatus.completed,
            youtube_url="https://youtube.com/watch?v=abc123",
            progress_pct=100,
        )
        assert job.status == JobStatus.completed
        assert job.youtube_url == "https://youtube.com/watch?v=abc123"
        assert job.progress_pct == 100

    def test_failed_job_with_error(self) -> None:
        """Test a failed job with error message."""
        job = JobRecord(
            job_id="job-789",
            manga_id="manga-456",
            manga_title="Test",
            status=JobStatus.failed,
            error_message="API rate limit exceeded",
        )
        assert job.status == JobStatus.failed
        assert job.error_message == "API rate limit exceeded"

    def test_serialization_to_dict(self) -> None:
        """Test serialization to dictionary."""
        job = JobRecord(
            job_id="job-789",
            manga_id="manga-456",
            manga_title="Test",
        )
        data = job.model_dump()
        assert data["job_id"] == "job-789"
        assert data["status"] == "pending"

    def test_serialization_to_json(self) -> None:
        """Test serialization to JSON."""
        job = JobRecord(
            job_id="job-789",
            manga_id="manga-456",
            manga_title="Test",
            created_at=datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC),
            updated_at=datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC),
        )
        json_str = job.model_dump_json()
        assert '"job_id":"job-789"' in json_str
        assert '"status":"pending"' in json_str


class TestScriptSegment:
    """Tests for ScriptSegment model."""

    def test_valid_construction(self) -> None:
        """Test valid ScriptSegment construction."""
        segment = ScriptSegment(
            chapter="Chapter 1",
            text="This is the narration for the first panel.",
            panel_start=0,
            panel_end=3,
        )
        assert segment.chapter == "Chapter 1"
        assert segment.text == "This is the narration for the first panel."
        assert segment.panel_start == 0
        assert segment.panel_end == 3

    def test_serialization_to_dict(self) -> None:
        """Test serialization to dictionary."""
        segment = ScriptSegment(
            chapter="Chapter 1",
            text="Narration text",
            panel_start=0,
            panel_end=5,
        )
        data = segment.model_dump()
        assert data == {
            "chapter": "Chapter 1",
            "text": "Narration text",
            "panel_start": 0,
            "panel_end": 5,
        }


class TestScriptDocument:
    """Tests for ScriptDocument model."""

    def test_valid_construction(self) -> None:
        """Test valid ScriptDocument construction."""
        doc = ScriptDocument(
            job_id="job-789",
            manga_title="One Piece",
            segments=[
                ScriptSegment(
                    chapter="Chapter 1",
                    text="Narration",
                    panel_start=0,
                    panel_end=3,
                )
            ],
        )
        assert doc.job_id == "job-789"
        assert doc.manga_title == "One Piece"
        assert len(doc.segments) == 1

    def test_empty_segments(self) -> None:
        """Test with empty segments list."""
        doc = ScriptDocument(
            job_id="job-789",
            manga_title="Test",
            segments=[],
        )
        assert doc.segments == []


class TestAudioSegment:
    """Tests for AudioSegment model."""

    def test_valid_construction(self) -> None:
        """Test valid AudioSegment construction."""
        segment = AudioSegment(
            index=0,
            s3_key="audio/job-789/segment-0.mp3",
            duration_seconds=15.5,
            chapter="Chapter 1",
            panel_start=0,
            panel_end=3,
        )
        assert segment.index == 0
        assert segment.s3_key == "audio/job-789/segment-0.mp3"
        assert segment.duration_seconds == 15.5
        assert segment.chapter == "Chapter 1"
        assert segment.panel_start == 0
        assert segment.panel_end == 3

    def test_serialization_to_dict(self) -> None:
        """Test serialization to dictionary."""
        segment = AudioSegment(
            index=0,
            s3_key="audio/segment.mp3",
            duration_seconds=10.0,
            chapter="Ch1",
            panel_start=0,
            panel_end=2,
        )
        data = segment.model_dump()
        assert data["index"] == 0
        assert data["duration_seconds"] == 10.0


class TestAudioManifest:
    """Tests for AudioManifest model."""

    def test_valid_construction(self) -> None:
        """Test valid AudioManifest construction."""
        manifest = AudioManifest(
            job_id="job-789",
            segments=[
                AudioSegment(
                    index=0,
                    s3_key="audio/s0.mp3",
                    duration_seconds=10.0,
                    chapter="Ch1",
                    panel_start=0,
                    panel_end=2,
                ),
                AudioSegment(
                    index=1,
                    s3_key="audio/s1.mp3",
                    duration_seconds=15.0,
                    chapter="Ch1",
                    panel_start=3,
                    panel_end=5,
                ),
            ],
            total_duration_seconds=25.0,
        )
        assert manifest.job_id == "job-789"
        assert len(manifest.segments) == 2
        assert manifest.total_duration_seconds == 25.0

    def test_empty_manifest(self) -> None:
        """Test with empty segments."""
        manifest = AudioManifest(
            job_id="job-789",
            segments=[],
            total_duration_seconds=0.0,
        )
        assert manifest.segments == []
        assert manifest.total_duration_seconds == 0.0


class TestPipelineSettings:
    """Tests for PipelineSettings model."""

    def test_valid_construction_with_defaults(self) -> None:
        """Test valid PipelineSettings with default values."""
        settings = PipelineSettings()
        assert settings.daily_quota == 1
        assert settings.voice_id == "vi-VN-HoaiMyNeural"
        assert settings.tone == "engaging and informative"
        assert settings.script_style == "chapter_walkthrough"

    def test_valid_construction_with_custom_values(self) -> None:
        """Test valid PipelineSettings with custom values."""
        settings = PipelineSettings(
            daily_quota=5,
            voice_id="en-US-CustomVoice",
            tone="casual and fun",
            script_style="detailed_review",
        )
        assert settings.daily_quota == 5
        assert settings.voice_id == "en-US-CustomVoice"
        assert settings.tone == "casual and fun"
        assert settings.script_style == "detailed_review"

    def test_daily_quota_minimum_valid(self) -> None:
        """Test that daily_quota=1 is valid."""
        settings = PipelineSettings(daily_quota=1)
        assert settings.daily_quota == 1

    def test_daily_quota_maximum_valid(self) -> None:
        """Test that daily_quota=10 is valid."""
        settings = PipelineSettings(daily_quota=10)
        assert settings.daily_quota == 10

    def test_daily_quota_zero_invalid(self) -> None:
        """Test that daily_quota=0 raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            PipelineSettings(daily_quota=0)
        assert "daily_quota" in str(exc_info.value)

    def test_daily_quota_negative_invalid(self) -> None:
        """Test that negative daily_quota raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            PipelineSettings(daily_quota=-1)
        assert "daily_quota" in str(exc_info.value)

    def test_daily_quota_eleven_invalid(self) -> None:
        """Test that daily_quota=11 raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            PipelineSettings(daily_quota=11)
        assert "daily_quota" in str(exc_info.value)

    def test_daily_quota_too_high_invalid(self) -> None:
        """Test that daily_quota > 10 raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            PipelineSettings(daily_quota=100)
        assert "daily_quota" in str(exc_info.value)

    def test_script_style_detailed_review(self) -> None:
        """Test detailed_review script style."""
        settings = PipelineSettings(script_style="detailed_review")
        assert settings.script_style == "detailed_review"

    def test_script_style_summary(self) -> None:
        """Test summary script style."""
        settings = PipelineSettings(script_style="summary")
        assert settings.script_style == "summary"

    def test_script_style_chapter_walkthrough(self) -> None:
        """Test chapter_walkthrough script style."""
        settings = PipelineSettings(script_style="chapter_walkthrough")
        assert settings.script_style == "chapter_walkthrough"

    def test_script_style_invalid(self) -> None:
        """Test that invalid script_style raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            PipelineSettings(script_style="invalid_style")  # type: ignore[arg-type]
        assert "script_style" in str(exc_info.value)

    def test_serialization_to_dict(self) -> None:
        """Test serialization to dictionary."""
        settings = PipelineSettings()
        data = settings.model_dump()
        assert data == {
            "daily_quota": 1,
            "voice_id": "vi-VN-HoaiMyNeural",
            "tone": "engaging and informative",
            "script_style": "chapter_walkthrough",
        }

    def test_serialization_to_json(self) -> None:
        """Test serialization to JSON."""
        settings = PipelineSettings()
        json_str = settings.model_dump_json()
        assert '"daily_quota":1' in json_str
        assert '"script_style":"chapter_walkthrough"' in json_str
