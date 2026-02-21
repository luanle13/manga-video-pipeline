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


class JobType(StrEnum):
    """Type of video to generate."""

    chapter_video = "chapter_video"  # Single chapter video from MangaDex
    review_video = "review_video"  # Full manga review from Vietnamese sites


class MangaSource(StrEnum):
    """Source site for manga content."""

    mangadex = "mangadex"
    truyenqq = "truyenqq"
    nettruyen = "nettruyen"
    truyentranhlh = "truyentranhlh"


class JobStatus(StrEnum):
    """Status of a pipeline job."""

    pending = "pending"
    fetching = "fetching"
    scripting = "scripting"
    tts = "tts"
    rendering = "rendering"
    awaiting_review = "awaiting_review"  # Video ready for manual review before upload
    uploading = "uploading"
    completed = "completed"
    failed = "failed"


class JobRecord(BaseModel):
    """Record of a pipeline job stored in DynamoDB."""

    job_id: str
    manga_id: str
    manga_title: str
    job_type: JobType = JobType.chapter_video  # Default to chapter video for backwards compat
    source: MangaSource = MangaSource.mangadex  # Default to MangaDex for backwards compat
    source_url: str | None = None  # Original URL for review jobs
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
    manual_review_mode: bool = Field(
        default=False,
        description="Pause after rendering for manual review before YouTube upload",
    )


# =============================================================================
# Review Video Models
# =============================================================================


class ReviewChapterInfo(BaseModel):
    """Chapter information for review video generation.

    Different from ChapterInfo which is for MangaDex-based chapter videos.
    This stores extracted text content for review summarization.
    """

    chapter_number: float  # Can be 1, 1.5, 2, etc.
    title: str | None = None
    url: str
    content_text: str = ""  # Extracted dialogue/narration text
    key_panel_url: str | None = None  # Representative panel for this chapter


class ReviewMangaInfo(BaseModel):
    """Manga information for review video generation.

    Contains all chapter content needed to generate a full manga review.
    """

    source: MangaSource
    source_url: str
    title: str
    author: str | None = None
    genres: list[str] = Field(default_factory=list)
    description: str | None = None
    cover_url: str
    total_chapters: int
    chapters: list[ReviewChapterInfo] = Field(default_factory=list)


class ReviewManifest(BaseModel):
    """Manifest for review video generation.

    Created by ReviewFetcher, consumed by ReviewScriptGenerator.
    """

    job_id: str
    manga_info: ReviewMangaInfo
    cover_s3_key: str  # S3 key for downloaded cover image
    panel_s3_keys: list[str] = Field(default_factory=list)  # S3 keys for key panels


class ReviewScriptSegment(BaseModel):
    """A segment of the review script.

    Each segment corresponds to a section of the review video
    (intro, chapter summaries, conclusion).
    """

    segment_type: Literal["intro", "chapter", "conclusion"]
    chapter_number: float | None = None  # For chapter segments
    text: str  # Vietnamese narration text
    panel_indices: list[int] = Field(default_factory=list)  # Indices into panel_s3_keys


class ReviewScriptDocument(BaseModel):
    """Complete review script document.

    Contains all segments for the review video narration.
    """

    job_id: str
    manga_title: str
    total_chapters: int
    segments: list[ReviewScriptSegment]


class SearchResult(BaseModel):
    """Search result from manga site."""

    title: str
    url: str
    cover_url: str | None = None
    source: MangaSource
    chapter_count: int | None = None
    author: str | None = None
