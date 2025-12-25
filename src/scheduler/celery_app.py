from celery import Celery
from celery.schedules import crontab
from ..config import get_settings
from ..discovery.manga_discovery import discovery
from ..scraper.manga_scraper import scraper
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
        trending_manga = asyncio.run(discovery.get_trending_manga())

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
def process_manga_chapter_task(self, manga_id: str, chapter_number: str, source: str):
    """Celery task to process a manga chapter: scrape, AI summarize, generate video, upload."""
    try:
        # Update task status
        task_id = self.request.id
        db_gen = get_db()
        db = next(db_gen)
        
        pipeline_task = create_pipeline_task(db, {
            'task_name': f'process_chapter_{chapter_number}',
            'manga_id': manga_id,
            'status': 'running',
            'progress': 0
        })
        
        # Initialize scraper
        asyncio.run(scraper.start())
        
        # Step 1: Scrape chapter images
        update_pipeline_task_status(db, pipeline_task.id, 'running', 10)
        image_urls = asyncio.run(scraper.scrape_chapter(manga_id, chapter_number, source))
        
        if not image_urls:
            raise Exception(f"No images found for manga {manga_id} chapter {chapter_number}")
        
        # Download images
        update_pipeline_task_status(db, pipeline_task.id, 'running', 20)
        image_paths = []
        for i, img_url in enumerate(image_urls):
            import requests
            response = requests.get(img_url)
            img_path = os.path.join(settings.temp_dir, f"chapter_{chapter_number}_img_{i}.jpg")
            with open(img_path, 'wb') as f:
                f.write(response.content)
            image_paths.append(img_path)
        
        # Step 2: Get manga info for context
        update_pipeline_task_status(db, pipeline_task.id, 'running', 30)
        manga_info = asyncio.run(scraper.scrape_manga_info(manga_id, source))
        
        # Step 3: Generate summary using AI
        update_pipeline_task_status(db, pipeline_task.id, 'running', 50)
        # In a real implementation, we would extract text from images or have access to chapter text
        chapter_text = f"Chapter {chapter_number} of {manga_info.get('title', 'Unknown Manga')}: This chapter contains exciting developments."
        summary = asyncio.run(ai_processor.summarize_chapters([chapter_text]))
        
        # Step 4: Generate video script
        update_pipeline_task_status(db, pipeline_task.id, 'running', 60)
        script = asyncio.run(ai_processor.generate_video_script(manga_info, summary))
        
        # Step 5: Generate TTS audio
        update_pipeline_task_status(db, pipeline_task.id, 'running', 70)
        audio_path = os.path.join(settings.temp_dir, f"chapter_{chapter_number}_audio.mp3")
        tts_success = asyncio.run(ai_processor.generate_tts(summary, audio_path))
        
        if not tts_success:
            raise Exception("Failed to generate TTS audio")
        
        # Step 6: Create video
        update_pipeline_task_status(db, pipeline_task.id, 'running', 80)
        output_path = os.path.join(settings.output_dir, f"manga_{manga_id}_chapter_{chapter_number}.mp4")
        video_success = video_generator.create_video(image_paths, audio_path, output_path)
        
        if not video_success:
            raise Exception("Failed to create video")
        
        # Step 7: Save video to database
        update_pipeline_task_status(db, pipeline_task.id, 'running', 90)
        video_record = create_video(db, {
            'title': f"{manga_info.get('title', 'Unknown Manga')} - Chapter {chapter_number}",
            'description': summary,
            'file_path': output_path,
            'audio_path': audio_path,
            'thumbnail_path': image_paths[0] if image_paths else None
        })
        
        # Step 8: Upload to platforms
        update_pipeline_task_status(db, pipeline_task.id, 'running', 95)
        # For simplicity, just upload to YouTube in this example
        upload_result = asyncio.run(uploader.upload_to_youtube(
            output_path,
            f"{manga_info.get('title', 'Unknown Manga')} - Chapter {chapter_number}",
            summary
        ))
        
        if upload_result.get('success'):
            # Update video record with upload status
            video_record.uploaded_to_youtube = True
            video_record.youtube_url = upload_result.get('url')
            db.commit()
        
        # Cleanup temporary files
        for img_path in image_paths:
            if os.path.exists(img_path):
                os.remove(img_path)
        if os.path.exists(audio_path):
            os.remove(audio_path)
        
        # Close scraper
        asyncio.run(scraper.close())
        
        # Update final status
        update_pipeline_task_status(db, pipeline_task.id, 'completed', 100)
        db.close()
        
        # Send notification
        asyncio.run(notification_service.send_pipeline_status(
            f'Manga Chapter {chapter_number}',
            'completed',
            {'manga_id': manga_id, 'platforms_uploaded': ['YouTube']}
        ))
        
        return f"Successfully processed chapter {chapter_number} of manga {manga_id}"
    
    except Exception as e:
        # Update task status to failed
        db_gen = get_db()
        db = next(db_gen)
        update_pipeline_task_status(db, pipeline_task.id, 'failed', error_message=str(e))
        db.close()
        
        # Close scraper if it was started
        try:
            asyncio.run(scraper.close())
        except:
            pass
        
        # Send error notification
        asyncio.run(notification_service.send_error_notification(str(e), f"Manga Chapter Processing: {manga_id} - Chapter {chapter_number}"))
        raise e


# Initialize the database when the module is imported
asyncio.run(init_db())