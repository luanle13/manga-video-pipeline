import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from src.database.models import Manga, Chapter, Video, VideoUpload, PipelineRun, Base
from src.database.repository import (
    MangaRepository,
    ChapterRepository,
    VideoRepository,
    VideoUploadRepository,
    PipelineRunRepository,
    DatabaseRepository
)


async def test_database():
    """Test the new async database structure."""
    # Create a test database engine
    engine = create_async_engine("sqlite+aiosqlite:///./test_manga_pipeline.db")
    
    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    # Create async session
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as session:
        # Test creating a manga
        manga_data = {
            'source': 'mangadex',
            'source_id': 'test-123',
            'title': 'Test Manga',
            'cover_url': 'https://example.com/cover.jpg',
            'trending_rank': 1,
            'is_active': True
        }
        manga = await MangaRepository.create(session, manga_data)
        print(f"Created manga: {manga.title}")
        
        # Test creating a chapter
        chapter_data = {
            'manga_id': manga.id,
            'chapter_number': 1.0,
            'title': 'Chapter 1',
            'source_url': 'https://mangadex.org/chapter/test-123/1',
            'page_count': 20,
            'is_processed': False
        }
        chapter = await ChapterRepository.create(session, chapter_data)
        print(f"Created chapter: {chapter.title}")
        
        # Test creating a video
        video_data = {
            'chapter_id': chapter.id,
            'language': 'en',
            'title': 'Test Video',
            'description': 'A test video for the chapter',
            'tags': {'genre': 'action', 'theme': 'adventure'},
            'script': 'This is a test script',
            'file_path': '/data/test_video.mp4',
            'duration_seconds': 300,
            'is_uploaded': False
        }
        video = await VideoRepository.create(session, video_data)
        print(f"Created video: {video.title}")
        
        # Test creating a video upload
        upload_data = {
            'video_id': video.id,
            'platform': 'youtube',
            'account_language': 'en',
            'status': 'pending'
        }
        upload = await VideoUploadRepository.create(session, upload_data)
        print(f"Created upload: {upload.platform}")
        
        # Test creating a pipeline run
        run_data = {
            'chapter_id': chapter.id,
            'status': 'running',
            'current_stage': 'processing',
            'progress_percent': 50
        }
        run = await PipelineRunRepository.create(session, run_data)
        print(f"Created pipeline run: {run.status}")
        
        # Test repository methods
        unprocessed_chapters = await DatabaseRepository.get_unprocessed_chapters(session)
        print(f"Unprocessed chapters: {len(unprocessed_chapters)}")
        
        failed_uploads = await DatabaseRepository.get_failed_uploads(session)
        print(f"Failed uploads: {len(failed_uploads)}")
        
        # Test daily stats
        daily_stats = await DatabaseRepository.get_daily_stats(session)
        print(f"Daily stats: {daily_stats}")
        
        print("All tests completed successfully!")


if __name__ == "__main__":
    asyncio.run(test_database())