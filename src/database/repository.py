from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, and_
from sqlalchemy.orm import selectinload
from typing import Any
from .models import Manga, Chapter, Video, VideoUpload, PipelineRun
from datetime import datetime, date
from typing import Self  # Use Self for return type annotations where applicable


class MangaRepository:
    """Repository for Manga operations."""
    
    @classmethod
    async def create(cls, db: AsyncSession, manga_data: dict[str, Any]) -> Manga:
        """Create a new Manga."""
        manga = Manga(**manga_data)
        db.add(manga)
        await db.commit()
        await db.refresh(manga)
        return manga

    @classmethod
    async def get_by_id(cls, db: AsyncSession, manga_id: int) -> Manga | None:
        """Get manga by ID."""
        stmt = select(Manga).where(Manga.id == manga_id)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    @classmethod
    async def get_by_source_id(cls, db: AsyncSession, source_id: str) -> Manga | None:
        """Get manga by source ID."""
        stmt = select(Manga).where(Manga.source_id == source_id)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    @classmethod
    async def update(cls, db: AsyncSession, manga_id: int, manga_data: dict[str, Any]) -> Manga | None:
        """Update manga."""
        stmt = update(Manga).where(Manga.id == manga_id).values(**manga_data).returning(Manga)
        result = await db.execute(stmt)
        manga = result.scalar_one_or_none()
        if manga:
            await db.commit()
            await db.refresh(manga)
        return manga

    @classmethod
    async def delete(cls, db: AsyncSession, manga_id: int) -> bool:
        """Delete manga by ID."""
        stmt = delete(Manga).where(Manga.id == manga_id)
        await db.execute(stmt)
        await db.commit()
        return True


class ChapterRepository:
    """Repository for Chapter operations."""
    
    @classmethod
    async def create(cls, db: AsyncSession, chapter_data: dict[str, Any]) -> Chapter:
        """Create a new Chapter."""
        chapter = Chapter(**chapter_data)
        db.add(chapter)
        await db.commit()
        await db.refresh(chapter)
        return chapter

    @classmethod
    async def get_by_id(cls, db: AsyncSession, chapter_id: int) -> Chapter | None:
        """Get chapter by ID."""
        stmt = select(Chapter).where(Chapter.id == chapter_id)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    @classmethod
    async def get_by_manga_and_number(cls, db: AsyncSession, manga_id: int, chapter_number: float) -> Chapter | None:
        """Get chapter by manga ID and chapter number."""
        stmt = select(Chapter).where(
            and_(Chapter.manga_id == manga_id, Chapter.chapter_number == chapter_number)
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    @classmethod
    async def get_unprocessed_chapters(cls, db: AsyncSession) -> list[Chapter]:
        """Get all unprocessed chapters."""
        stmt = select(Chapter).where(Chapter.is_processed == False)  # noqa: E712
        result = await db.execute(stmt)
        return result.scalars().all()

    @classmethod
    async def update(cls, db: AsyncSession, chapter_id: int, chapter_data: dict[str, Any]) -> Chapter | None:
        """Update chapter."""
        stmt = update(Chapter).where(Chapter.id == chapter_id).values(**chapter_data).returning(Chapter)
        result = await db.execute(stmt)
        chapter = result.scalar_one_or_none()
        if chapter:
            await db.commit()
            await db.refresh(chapter)
        return chapter

    @classmethod
    async def delete(cls, db: AsyncSession, chapter_id: int) -> bool:
        """Delete chapter by ID."""
        stmt = delete(Chapter).where(Chapter.id == chapter_id)
        await db.execute(stmt)
        await db.commit()
        return True


class VideoRepository:
    """Repository for Video operations."""
    
    @classmethod
    async def create(cls, db: AsyncSession, video_data: dict[str, Any]) -> Video:
        """Create a new Video."""
        video = Video(**video_data)
        db.add(video)
        await db.commit()
        await db.refresh(video)
        return video

    @classmethod
    async def get_by_id(cls, db: AsyncSession, video_id: int) -> Video | None:
        """Get video by ID."""
        stmt = select(Video).where(Video.id == video_id)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    @classmethod
    async def get_by_chapter_id(cls, db: AsyncSession, chapter_id: int) -> list[Video]:
        """Get all videos for a chapter."""
        stmt = select(Video).where(Video.chapter_id == chapter_id)
        result = await db.execute(stmt)
        return result.scalars().all()

    @classmethod
    async def get_by_language(cls, db: AsyncSession, language: str) -> list[Video]:
        """Get all videos for a specific language."""
        stmt = select(Video).where(Video.language == language)
        result = await db.execute(stmt)
        return result.scalars().all()

    @classmethod
    async def update(cls, db: AsyncSession, video_id: int, video_data: dict[str, Any]) -> Video | None:
        """Update video."""
        stmt = update(Video).where(Video.id == video_id).values(**video_data).returning(Video)
        result = await db.execute(stmt)
        video = result.scalar_one_or_none()
        if video:
            await db.commit()
            await db.refresh(video)
        return video

    @classmethod
    async def delete(cls, db: AsyncSession, video_id: int) -> bool:
        """Delete video by ID."""
        stmt = delete(Video).where(Video.id == video_id)
        await db.execute(stmt)
        await db.commit()
        return True


class VideoUploadRepository:
    """Repository for VideoUpload operations."""
    
    @classmethod
    async def create(cls, db: AsyncSession, upload_data: dict[str, Any]) -> VideoUpload:
        """Create a new VideoUpload."""
        upload = VideoUpload(**upload_data)
        db.add(upload)
        await db.commit()
        await db.refresh(upload)
        return upload

    @classmethod
    async def get_by_id(cls, db: AsyncSession, upload_id: int) -> VideoUpload | None:
        """Get video upload by ID."""
        stmt = select(VideoUpload).where(VideoUpload.id == upload_id)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    @classmethod
    async def get_by_video_and_platform(cls, db: AsyncSession, video_id: int, platform: str) -> VideoUpload | None:
        """Get video upload by video ID and platform."""
        stmt = select(VideoUpload).where(
            and_(VideoUpload.video_id == video_id, VideoUpload.platform == platform)
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    @classmethod
    async def get_failed_uploads(cls, db: AsyncSession) -> list[VideoUpload]:
        """Get all failed video uploads."""
        stmt = select(VideoUpload).where(VideoUpload.status == "failed")
        result = await db.execute(stmt)
        return result.scalars().all()

    @classmethod
    async def get_by_platform(cls, db: AsyncSession, platform: str) -> list[VideoUpload]:
        """Get all video uploads for a specific platform."""
        stmt = select(VideoUpload).where(VideoUpload.platform == platform)
        result = await db.execute(stmt)
        return result.scalars().all()

    @classmethod
    async def update(cls, db: AsyncSession, upload_id: int, upload_data: dict[str, Any]) -> VideoUpload | None:
        """Update video upload."""
        stmt = update(VideoUpload).where(VideoUpload.id == upload_id).values(**upload_data).returning(VideoUpload)
        result = await db.execute(stmt)
        upload = result.scalar_one_or_none()
        if upload:
            await db.commit()
            await db.refresh(upload)
        return upload

    @classmethod  
    async def increment_retry_count(cls, db: AsyncSession, upload_id: int) -> VideoUpload | None:
        """Increment retry count for a video upload."""
        stmt = update(VideoUpload).where(VideoUpload.id == upload_id).values(
            retry_count=VideoUpload.retry_count + 1
        ).returning(VideoUpload)
        result = await db.execute(stmt)
        upload = result.scalar_one_or_none()
        if upload:
            await db.commit()
            await db.refresh(upload)
        return upload

    @classmethod
    async def delete(cls, db: AsyncSession, upload_id: int) -> bool:
        """Delete video upload by ID."""
        stmt = delete(VideoUpload).where(VideoUpload.id == upload_id)
        await db.execute(stmt)
        await db.commit()
        return True


class PipelineRunRepository:
    """Repository for PipelineRun operations."""
    
    @classmethod
    async def create(cls, db: AsyncSession, run_data: dict[str, Any]) -> PipelineRun:
        """Create a new PipelineRun."""
        run = PipelineRun(**run_data)
        db.add(run)
        await db.commit()
        await db.refresh(run)
        return run

    @classmethod
    async def get_by_id(cls, db: AsyncSession, run_id: int) -> PipelineRun | None:
        """Get pipeline run by ID."""
        stmt = select(PipelineRun).where(PipelineRun.id == run_id)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    @classmethod
    async def get_by_chapter_id(cls, db: AsyncSession, chapter_id: int) -> list[PipelineRun]:
        """Get all pipeline runs for a chapter."""
        stmt = select(PipelineRun).where(PipelineRun.chapter_id == chapter_id)
        result = await db.execute(stmt)
        return result.scalars().all()

    @classmethod
    async def update(cls, db: AsyncSession, run_id: int, run_data: dict[str, Any]) -> PipelineRun | None:
        """Update pipeline run."""
        stmt = update(PipelineRun).where(PipelineRun.id == run_id).values(**run_data).returning(PipelineRun)
        result = await db.execute(stmt)
        run = result.scalar_one_or_none()
        if run:
            await db.commit()
            await db.refresh(run)
        return run

    @classmethod
    async def delete(cls, db: AsyncSession, run_id: int) -> bool:
        """Delete pipeline run by ID."""
        stmt = delete(PipelineRun).where(PipelineRun.id == run_id)
        await db.execute(stmt)
        await db.commit()
        return True


class DatabaseRepository:
    """Main repository class with convenience methods."""
    
    @classmethod
    async def get_daily_stats(cls, db: AsyncSession, target_date: date | None = None) -> dict[str, int]:
        """Get daily statistics for manga pipeline."""
        if target_date is None:
            target_date = datetime.now().date()
        
        start_date = datetime.combine(target_date, datetime.min.time())
        end_date = datetime.combine(target_date, datetime.max.time())
        
        # Count new manga discovered today
        manga_stmt = select(Manga).where(
            and_(Manga.created_at >= start_date, Manga.created_at <= end_date)
        )
        manga_result = await db.execute(manga_stmt)
        new_manga_count = len(manga_result.scalars().all())
        
        # Count new chapters processed today
        chapter_stmt = select(Chapter).where(
            and_(Chapter.created_at >= start_date, Chapter.created_at <= end_date)
        )
        chapter_result = await db.execute(chapter_stmt)
        new_chapters_count = len(chapter_result.scalars().all())
        
        # Count new videos created today
        video_stmt = select(Video).where(
            and_(Video.created_at >= start_date, Video.created_at <= end_date)
        )
        video_result = await db.execute(video_stmt)
        new_videos_count = len(video_result.scalars().all())
        
        # Count new video uploads today
        upload_stmt = select(VideoUpload).where(
            and_(VideoUpload.created_at >= start_date, VideoUpload.created_at <= end_date)
        )
        upload_result = await db.execute(upload_stmt)
        new_uploads_count = len(upload_result.scalars().all())
        
        return {
            "new_manga": new_manga_count,
            "new_chapters": new_chapters_count,
            "new_videos": new_videos_count,
            "new_uploads": new_uploads_count
        }

    @classmethod
    async def get_unprocessed_chapters(cls, db: AsyncSession) -> list[Chapter]:
        """Get all unprocessed chapters."""
        return await ChapterRepository.get_unprocessed_chapters(db)

    @classmethod
    async def get_failed_uploads(cls, db: AsyncSession) -> list[VideoUpload]:
        """Get all failed video uploads."""
        return await VideoUploadRepository.get_failed_uploads(db)

    @classmethod
    async def get_chapters_ready_for_processing(cls, db: AsyncSession) -> list[Chapter]:
        """Get chapters that are ready for processing (not processed and have no running pipeline runs)."""
        from sqlalchemy import not_
        
        # Find chapters that are not processed and have no running pipeline runs
        stmt = select(Chapter).where(
            and_(
                Chapter.is_processed == False,
                not_(
                    select(PipelineRun).where(
                        and_(
                            PipelineRun.chapter_id == Chapter.id,
                            PipelineRun.status.in_(["pending", "running"])
                        )
                    ).exists()
                )
            )
        )
        result = await db.execute(stmt)
        return result.scalars().all()