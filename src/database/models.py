from sqlalchemy import Column, Integer, String, DateTime, Text, Float, Boolean, ForeignKey, JSON
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from datetime import datetime
from typing import TYPE_CHECKING, List, Dict, Optional
if TYPE_CHECKING:
    from typing import Self  # Use Self for return type annotations where applicable
else:
    from typing_extensions import Self


class Base(DeclarativeBase):
    """Base class for all models."""
    pass


class Manga(Base):
    __tablename__ = "manga"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    source: Mapped[str] = mapped_column(String, index=True)
    source_id: Mapped[str] = mapped_column(String, unique=True, index=True)
    title: Mapped[str] = mapped_column(String)
    cover_url: Mapped[str | None] = mapped_column(String)
    trending_rank: Mapped[int | None] = mapped_column(Integer)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationship to chapters
    chapters: Mapped[List["Chapter"]] = relationship("Chapter", back_populates="manga")

    def to_dict(self) -> dict[str, str | int | float | bool | datetime | None]:
        """Convert model to dictionary."""
        return {
            'id': self.id,
            'source': self.source,
            'source_id': self.source_id,
            'title': self.title,
            'cover_url': self.cover_url,
            'trending_rank': self.trending_rank,
            'is_active': self.is_active,
            'last_checked_at': self.last_checked_at,
            'created_at': self.created_at,
            'updated_at': self.updated_at
        }


class Chapter(Base):
    __tablename__ = "chapters"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    manga_id: Mapped[int] = mapped_column(Integer, ForeignKey("manga.id"), index=True)
    chapter_number: Mapped[float] = mapped_column(Float)
    title: Mapped[str] = mapped_column(String)
    source_url: Mapped[str | None] = mapped_column(String)
    page_count: Mapped[int | None] = mapped_column(Integer)
    is_processed: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationship to manga
    manga: Mapped["Manga"] = relationship("Manga", back_populates="chapters")
    # Relationship to videos
    videos: Mapped[List["Video"]] = relationship("Video", back_populates="chapter")
    # Relationship to pipeline runs
    pipeline_runs: Mapped[List["PipelineRun"]] = relationship("PipelineRun", back_populates="chapter")

    def to_dict(self) -> dict[str, str | int | float | bool | datetime | None]:
        """Convert model to dictionary."""
        return {
            'id': self.id,
            'manga_id': self.manga_id,
            'chapter_number': self.chapter_number,
            'title': self.title,
            'source_url': self.source_url,
            'page_count': self.page_count,
            'is_processed': self.is_processed,
            'created_at': self.created_at,
            'updated_at': self.updated_at
        }


class Video(Base):
    __tablename__ = "videos"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    chapter_id: Mapped[int] = mapped_column(Integer, ForeignKey("chapters.id"), index=True)
    language: Mapped[str] = mapped_column(String, index=True)
    title: Mapped[str] = mapped_column(String)
    description: Mapped[str] = mapped_column(Text)
    tags: Mapped[dict[str, str] | None] = mapped_column(JSON)
    script: Mapped[str | None] = mapped_column(Text)
    file_path: Mapped[str] = mapped_column(String)
    duration_seconds: Mapped[int | None] = mapped_column(Integer)
    is_uploaded: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationship to chapter
    chapter: Mapped["Chapter"] = relationship("Chapter", back_populates="videos")
    # Relationship to video uploads
    uploads: Mapped[List["VideoUpload"]] = relationship("VideoUpload", back_populates="video")

    def to_dict(self) -> dict[str, str | int | float | bool | datetime | dict | None]:
        """Convert model to dictionary."""
        return {
            'id': self.id,
            'chapter_id': self.chapter_id,
            'language': self.language,
            'title': self.title,
            'description': self.description,
            'tags': self.tags,
            'script': self.script,
            'file_path': self.file_path,
            'duration_seconds': self.duration_seconds,
            'is_uploaded': self.is_uploaded,
            'created_at': self.created_at,
            'updated_at': self.updated_at
        }


class VideoUpload(Base):
    __tablename__ = "video_uploads"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    video_id: Mapped[int] = mapped_column(Integer, ForeignKey("videos.id"), index=True)
    platform: Mapped[str] = mapped_column(String, index=True)
    account_language: Mapped[str] = mapped_column(String, index=True)
    platform_video_id: Mapped[str | None] = mapped_column(String)
    platform_url: Mapped[str | None] = mapped_column(String)
    status: Mapped[str] = mapped_column(String, index=True, default="pending")  # pending, uploading, completed, failed
    error_message: Mapped[str | None] = mapped_column(Text)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationship to video
    video: Mapped["Video"] = relationship("Video", back_populates="uploads")

    def to_dict(self) -> dict[str, str | int | float | bool | datetime | None]:
        """Convert model to directory."""
        return {
            'id': self.id,
            'video_id': self.video_id,
            'platform': self.platform,
            'account_language': self.account_language,
            'platform_video_id': self.platform_video_id,
            'platform_url': self.platform_url,
            'status': self.status,
            'error_message': self.error_message,
            'retry_count': self.retry_count,
            'created_at': self.created_at,
            'updated_at': self.updated_at
        }


class PipelineRun(Base):
    __tablename__ = "pipeline_runs"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    chapter_id: Mapped[int] = mapped_column(Integer, ForeignKey("chapters.id"), index=True)
    status: Mapped[str] = mapped_column(String, index=True, default="pending")  # pending, running, completed, failed
    current_stage: Mapped[str | None] = mapped_column(String)
    progress_percent: Mapped[int] = mapped_column(Integer, default=0)  # 0-100
    error_message: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None] = mapped_column(DateTime)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationship to chapter
    chapter: Mapped["Chapter"] = relationship("Chapter", back_populates="pipeline_runs")

    def to_dict(self) -> dict[str, str | int | float | bool | datetime | None]:
        """Convert model to dictionary."""
        return {
            'id': self.id,
            'chapter_id': self.chapter_id,
            'status': self.status,
            'current_stage': self.current_stage,
            'progress_percent': self.progress_percent,
            'error_message': self.error_message,
            'started_at': self.started_at,
            'completed_at': self.completed_at,
            'created_at': self.created_at,
            'updated_at': self.updated_at
        }


# For backward compatibility and easy access
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from ..config import get_settings

settings = get_settings()
DATABASE_URL = settings.database.url  # Use the new config structure

# Async engine and session setup
async_engine = create_async_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False}  # Needed for SQLite
)

AsyncSessionLocal = async_sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=async_engine,
    expire_on_commit=False
)


async def init_db():
    """Initialize the database with tables."""
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_async_db():
    """Get an async database session."""
    async with AsyncSessionLocal() as session:
        yield session