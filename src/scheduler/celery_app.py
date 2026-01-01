from celery import Celery
from celery.schedules import crontab
from ..config import get_settings
from ..discovery import discovery_manager
from ..ai.manga_ai import ai_processor
from ..video.manga_video_generator import video_generator
from ..uploader.video_uploader import uploader
from ..notifications.notification_service import notification_service
from ..database import init_db, get_async_db, MangaRepository, ChapterRepository, PipelineRunRepository
import asyncio
import os


# Initialize Celery
celery_app = Celery('manga_video_pipeline')
settings = get_settings()
celery_app.conf.broker_url = settings.redis.url
celery_app.conf.result_backend = settings.redis.url


# Configure periodic tasks
celery_app.conf.beat_schedule = {
    'discover-trending-manga': {
        'task': 'src.scheduler.celery_app.discover_trending_manga_task',
        'schedule': crontab(minute=0, hour='*/6'),  # Run every 6 hours
    },
}


@celery_app.task(bind=True)
def discover_trending_manga_task(self):
    """Celery task to discover trending manga."""
    try:
        # Discover trending manga
        trending_manga = asyncio.run(discovery_manager.discover_trending())

        # Send notification
        asyncio.run(notification_service.send_pipeline_status(
            'Manga Discovery',
            'completed',
            {'discovered_count': len(trending_manga)}
        ))

        return f"Discovered {len(trending_manga)} manga"

    except Exception as e:
        # Send error notification
        asyncio.run(notification_service.send_error_notification(str(e), "Manga Discovery"))
        raise e


@celery_app.task(bind=True)
def process_manga_chapter_task(self, chapter_url: str, manga_title: str, chapter_number: str):
    """Celery task to process a manga chapter: scrape, AI summarize, generate video, upload."""
    from ..scraper import scraper_manager
    from ..database import VideoRepository, get_async_db
    import tempfile

    try:
        # Update task status would go here in a full implementation

        # Step 1: Scrape chapter images using new scraper
        print(f"Scraping chapter from {chapter_url}...")
        scraped_chapter = asyncio.run(scraper_manager.scrape_chapter(chapter_url))

        if not scraped_chapter.pages:
            raise Exception(f"No pages found for chapter at {chapter_url}")

        # Extract image paths from scraped chapter
        image_paths = [str(page.image_path) for page in scraped_chapter.pages]

        # Step 2: Generate summary using AI
        print(f"Generating summary for chapter {chapter_number}...")
        # Create a basic chapter text to summarize
        chapter_text = f"Chapter {chapter_number} of {manga_title}: This chapter contains exciting developments across {len(image_paths)} pages."
        summary = asyncio.run(ai_processor.summarize_chapters([chapter_text]))

        # Step 3: Generate video script
        print(f"Generating video script for chapter {chapter_number}...")
        manga_info = {'title': manga_title}
        script = asyncio.run(ai_processor.generate_video_script(manga_info, summary))

        # Step 4: Generate TTS audio
        print(f"Generating TTS audio for chapter {chapter_number}...")
        import os
        temp_dir = "data/temp"
        os.makedirs(temp_dir, exist_ok=True)
        audio_path = os.path.join(temp_dir, f"chapter_{chapter_number}_audio.mp3")
        tts_success = asyncio.run(ai_processor.generate_tts(summary, audio_path))

        if not tts_success:
            raise Exception("Failed to generate TTS audio")

        # Step 5: Create video
        print(f"Creating video for chapter {chapter_number}...")
        output_path = os.path.join("data/output", f"chapter_{chapter_number}.mp4")
        os.makedirs("data/output", exist_ok=True)
        video_success = video_generator.create_video(image_paths, audio_path, output_path)

        if not video_success:
            raise Exception("Failed to create video")

        # Step 6: Save video record to database
        async def save_video_to_db():
            async for db in get_async_db():
                video_data = {
                    'chapter_id': 1,  # Placeholder - would need to get actual chapter ID
                    'language': 'en',
                    'title': f"{manga_title} - Chapter {chapter_number}",
                    'description': summary,
                    'script': script,
                    'file_path': output_path,
                    'is_uploaded': False
                }
                return await VideoRepository.create(db, video_data)

        video_record = asyncio.run(save_video_to_db())

        # Step 7: Upload to platforms
        print(f"Uploading video for chapter {chapter_number}...")
        upload_result = asyncio.run(uploader.upload_to_youtube(
            output_path,
            f"{manga_title} - Chapter {chapter_number}",
            summary
        ))

        # Cleanup temporary files using scraper manager
        if scraped_chapter.temp_dir:
            asyncio.run(scraper_manager.cleanup_temp(scraped_chapter.temp_dir))

        # Cleanup audio file
        if os.path.exists(audio_path):
            os.remove(audio_path)

        print(f"Successfully processed chapter {chapter_number}")
        return f"Successfully processed chapter {chapter_number} of {manga_title}"

    except Exception as e:
        # Send error notification
        asyncio.run(notification_service.send_error_notification(
            str(e),
            f"Manga Chapter Processing: {manga_title} - Chapter {chapter_number}"
        ))
        raise e


# Initialize the database when the module is imported
asyncio.run(init_db())