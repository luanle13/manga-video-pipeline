"""Pydantic data models for manga-video-pipeline."""

from datetime import UTC, datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field


def utcnow() -> datetime:
    """Return current UTC datetime."""
    return datetime.now(UTC)


class ChapterInfo(BaseModel):
    """Information about a manga chapter."""

    chapter_id: str
    title: str
    chapter_number: str | None
    page_urls: list[str]


class MangaInfo(BaseModel):
    """Information about a manga series."""

    manga_id: str
    title: str
    description: str
    genres: list[str]
    cover_url: str | None
    chapters: list[ChapterInfo]


class JobStatus(StrEnum):
    """Status of a pipeline job."""

    pending = "pending"
    fetching = "fetching"
    scripting = "scripting"
    tts = "tts"
    rendering = "rendering"
    uploading = "uploading"
    completed = "completed"
    failed = "failed"


class JobRecord(BaseModel):
    """Record of a pipeline job stored in DynamoDB."""

    job_id: str
    manga_id: str
    manga_title: str
    status: JobStatus = JobStatus.pending
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)
    youtube_url: str | None = None
    error_message: str | None = None
    progress_pct: int = 0


class ScriptSegment(BaseModel):
    """A segment of the generated script."""

    chapter: str
    text: str
    panel_start: int
    panel_end: int


class ScriptDocument(BaseModel):
    """Complete script document for a job."""

    job_id: str
    manga_title: str
    segments: list[ScriptSegment]


class AudioSegment(BaseModel):
    """Information about a generated audio segment."""

    index: int
    s3_key: str
    duration_seconds: float
    chapter: str
    panel_start: int
    panel_end: int


class AudioManifest(BaseModel):
    """Manifest of all audio segments for a job."""

    job_id: str
    segments: list[AudioSegment]
    total_duration_seconds: float


class PipelineSettings(BaseModel):
    """User-configurable pipeline settings."""

    daily_quota: int = Field(ge=1, le=10, default=1)
    voice_id: str = "vi-VN-HoaiMyNeural"
    tone: str = "engaging and informative"
    script_style: Literal["detailed_review", "summary", "chapter_walkthrough"] = (
        "chapter_walkthrough"
    )
