from __future__ import annotations
import asyncio
from asgiref.sync import async_to_sync
from celery import shared_task
from celery.utils.log import get_task_logger
import tempfile
import os
from pathlib import Path
from typing import Any, Dict


# Import necessary modules from the project
from .. import celery_app as app
from ..db import get_db_session, PipelineRun  # Assuming a database module exists
from ..scrapers.manga_scraper import MangaScraper  # Assuming scraper exists
from ..ai.summarizer import MangaSummarizer  # Assuming summarizer exists
from ..ai.tts import TextToSpeechService  # Assuming TTS service exists
from ..video.generator import VideoGenerator  # Assuming video generator exists
from ..ai.metadata import MetadataGenerator  # Assuming metadata generator exists
from ..uploader.manager import UploadManager  # Assuming uploader manager exists
from ..notifications.telegram import TelegramNotifier  # Assuming notifier exists


logger = get_task_logger(__name__)


@shared_task(bind=True, autoretry_for=(Exception,), retry_kwargs={'max_retries': 3, 'countdown': 60})
def discover_trending_manga(self):
    """
    Discover trending manga from various sources.
    
    Returns:
        List of manga titles/URLs to process
    """
    logger.info("Starting manga discovery task")
    
    try:
        # Update pipeline run status
        session = get_db_session()
        run = session.query(PipelineRun).filter_by(task_id=self.request.id).first()
        if run:
            run.status = 'discovering'
            session.commit()
        
        # Use async function wrapped in sync
        async def _discover():
            scraper = MangaScraper()
            trending_manga = await scraper.get_trending_manga()
            return trending_manga
        
        trending = async_to_sync(_discover)()
        
        logger.info(f"Discovered {len(trending)} trending manga")
        
        # Update status
        if run:
            run.status = 'discovery_complete'
            session.commit()
        
        return trending
        
    except Exception as e:
        logger.error(f"Error in discover_trending_manga: {str(e)}")
        
        # Update status to error
        session = get_db_session()
        run = session.query(PipelineRun).filter_by(task_id=self.request.id).first()
        if run:
            run.status = 'error'
            run.error_message = str(e)
            session.commit()
        
        raise


@shared_task(bind=True, autoretry_for=(Exception,), retry_kwargs={'max_retries': 3, 'countdown': 60})
def scrape_chapter(self, manga_url: str, chapter_number: float):
    """
    Scrape a specific manga chapter.
    
    Args:
        manga_url: URL of the manga
        chapter_number: Chapter number to scrape
        
    Returns:
        Dictionary with chapter data (images, title, etc.)
    """
    logger.info(f"Starting chapter scraping task for {manga_url}, chapter {chapter_number}")
    
    try:
        # Update pipeline run status
        session = get_db_session()
        run = session.query(PipelineRun).filter_by(task_id=self.request.id).first()
        if run:
            run.status = 'scraping'
            session.commit()
        
        # Use async function wrapped in sync
        async def _scrape():
            scraper = MangaScraper()
            chapter_data = await scraper.get_chapter(manga_url, chapter_number)
            return chapter_data
        
        chapter_data = async_to_sync(_scrape)()
        
        logger.info(f"Successfully scraped chapter {chapter_number}")
        
        # Update status
        if run:
            run.status = 'scraping_complete'
            session.commit()
        
        return chapter_data
        
    except Exception as e:
        logger.error(f"Error in scrape_chapter: {str(e)}")
        
        # Update status to error
        session = get_db_session()
        run = session.query(PipelineRun).filter_by(task_id=self.request.id).first()
        if run:
            run.status = 'error'
            run.error_message = str(e)
            session.commit()
        
        raise


@shared_task(bind=True, autoretry_for=(Exception,), retry_kwargs={'max_retries': 3, 'countdown': 60})
def generate_summary(self, chapter_data: dict, manga_title: str, chapter_number: float, language: str):
    """
    Generate a summary for the chapter.

    Args:
        chapter_data: Dictionary containing chapter data (images, etc.) from scrape_chapter
        manga_title: Title of the manga
        chapter_number: Chapter number
        language: Language code ('en' or 'vn')

    Returns:
        Summary text
    """
    logger.info(f"Starting summary generation for {manga_title} chapter {chapter_number}")

    try:
        # Update pipeline run status
        session = get_db_session()
        run = session.query(PipelineRun).filter_by(task_id=self.request.id).first()
        if run:
            run.status = 'summarizing'
            session.commit()

        # Extract images from chapter_data
        images = chapter_data.get('images', [])

        # Use async function wrapped in sync
        async def _generate():
            summarizer = MangaSummarizer()
            summary = await summarizer.summarize_chapter(
                images=[Path(img) for img in images],
                manga_title=manga_title,
                chapter_number=chapter_number,
                language=language
            )
            return summary

        summary = async_to_sync(_generate)()

        logger.info(f"Successfully generated summary for chapter {chapter_number}")

        # Update status
        if run:
            run.status = 'summary_complete'
            session.commit()

        return {
            'script': summary.script,
            'word_count': summary.word_count,
            'estimated_duration': summary.estimated_duration,
            'images': images  # Return images for next step
        }

    except Exception as e:
        logger.error(f"Error in generate_summary: {str(e)}")

        # Update status to error
        session = get_db_session()
        run = session.query(PipelineRun).filter_by(task_id=self.request.id).first()
        if run:
            run.status = 'error'
            run.error_message = str(e)
            session.commit()

        raise


@shared_task(bind=True, autoretry_for=(Exception,), retry_kwargs={'max_retries': 3, 'countdown': 60})
def generate_audio(self, summary_data: dict, output_path: str, language: str, voice: str = "alloy"):
    """
    Generate audio from text.

    Args:
        summary_data: Dictionary containing summary data (script, etc.) from generate_summary
        output_path: Path to save the audio file
        language: Language code ('en' or 'vn')
        voice: Voice for TTS

    Returns:
        Path to generated audio file
    """
    logger.info(f"Starting audio generation for summary script of length {len(summary_data.get('script', ''))}")

    try:
        # Update pipeline run status
        session = get_db_session()
        run = session.query(PipelineRun).filter_by(task_id=self.request.id).first()
        if run:
            run.status = 'generating_audio'
            session.commit()

        # Extract text from summary_data
        text = summary_data.get('script', '')

        # Use async function wrapped in sync
        async def _generate():
            tts_service = TextToSpeechService()
            audio_result = await tts_service.generate_audio(
                text=text,
                output_path=Path(output_path),
                language=language,
                voice=voice
            )
            return audio_result

        audio_result = async_to_sync(_generate)()

        logger.info(f"Successfully generated audio to {output_path}")

        # Update status
        if run:
            run.status = 'audio_complete'
            session.commit()

        # Return data for next step
        return {
            'audio_path': str(audio_result.audio_path),
            'images': summary_data.get('images', [])  # Pass images through
        }

    except Exception as e:
        logger.error(f"Error in generate_audio: {str(e)}")

        # Update status to error
        session = get_db_session()
        run = session.query(PipelineRun).filter_by(task_id=self.request.id).first()
        if run:
            run.status = 'error'
            run.error_message = str(e)
            session.commit()

        raise


@shared_task(bind=True, autoretry_for=(Exception,), retry_kwargs={'max_retries': 3, 'countdown': 60})
def generate_video(self, audio_data: dict, output_path: str):
    """
    Generate a video from images and audio.

    Args:
        audio_data: Dictionary containing audio data (audio_path, images, etc.) from generate_audio
        output_path: Path to save the video

    Returns:
        Path to generated video file
    """
    logger.info(f"Starting video generation with audio {audio_data.get('audio_path')} and {len(audio_data.get('images', []))} images")

    try:
        # Update pipeline run status
        session = get_db_session()
        run = session.query(PipelineRun).filter_by(task_id=self.request.id).first()
        if run:
            run.status = 'generating_video'
            session.commit()

        # Extract data from audio_data
        images = audio_data.get('images', [])
        audio_path = audio_data.get('audio_path', '')

        # Use async function wrapped in sync
        async def _generate():
            video_generator = VideoGenerator()
            video_result = await video_generator.generate_video(
                images=[Path(img) for img in images],
                audio_path=Path(audio_path),
                output_path=Path(output_path)
            )
            return video_result

        video_result = async_to_sync(_generate)()

        logger.info(f"Successfully generated video to {output_path}")

        # Update status
        if run:
            run.status = 'video_complete'
            session.commit()

        # Return data for next step
        return {
            'video_path': str(video_result.video_path),
            'images': images, # Pass through for metadata generation
            'audio_path': audio_path
        }

    except Exception as e:
        logger.error(f"Error in generate_video: {str(e)}")

        # Update status to error
        session = get_db_session()
        run = session.query(PipelineRun).filter_by(task_id=self.request.id).first()
        if run:
            run.status = 'error'
            run.error_message = str(e)
            session.commit()

        raise


@shared_task(bind=True, autoretry_for=(Exception,), retry_kwargs={'max_retries': 3, 'countdown': 60})
def generate_metadata(self, video_data: dict, manga_title: str, chapter_number: float, language: str):
    """
    Generate metadata for the video.

    Args:
        video_data: Dictionary containing video data (video_path, script, etc.) from previous steps
        manga_title: Title of the manga
        chapter_number: Chapter number
        language: Language code ('en' or 'vn')

    Returns:
        Dictionary with title, description, tags, hashtags
    """
    logger.info(f"Starting metadata generation for {manga_title} chapter {chapter_number}")

    try:
        # Update pipeline run status
        session = get_db_session()
        run = session.query(PipelineRun).filter_by(task_id=self.request.id).first()
        if run:
            run.status = 'generating_metadata'
            session.commit()

        # Extract summary and other data from video_data
        summary = video_data.get('summary', manga_title + " chapter " + str(chapter_number))  # Use as fallback

        # Use async function wrapped in sync
        async def _generate():
            metadata_generator = MetadataGenerator()
            metadata = await metadata_generator.generate_metadata(
                manga_title=manga_title,
                chapter_number=chapter_number,
                summary=summary,
                language=language
            )
            return metadata

        metadata = async_to_sync(_generate)()

        logger.info(f"Successfully generated metadata for chapter {chapter_number}")

        # Update status
        if run:
            run.status = 'metadata_complete'
            session.commit()

        # Return data for next step
        return {
            'title': metadata.title,
            'description': metadata.description,
            'tags': metadata.tags,
            'hashtags': metadata.hashtags,
            'video_path': video_data.get('video_path', ''),
        }

    except Exception as e:
        logger.error(f"Error in generate_metadata: {str(e)}")

        # Update status to error
        session = get_db_session()
        run = session.query(PipelineRun).filter_by(task_id=self.request.id).first()
        if run:
            run.status = 'error'
            run.error_message = str(e)
            session.commit()

        raise


@shared_task(bind=True, autoretry_for=(Exception,), retry_kwargs={'max_retries': 3, 'countdown': 60})
def upload_to_platform(self, metadata_data: dict, language: str):
    """
    Upload video to all platforms.

    Args:
        metadata_data: Dictionary containing video data (video_path, title, description, etc.) from generate_metadata
        language: Language code ('en' or 'vn')

    Returns:
        Upload results for each platform
    """
    logger.info(f"Starting upload for {metadata_data.get('title', 'Unknown')}")

    try:
        # Update pipeline run status
        session = get_db_session()
        run = session.query(PipelineRun).filter_by(task_id=self.request.id).first()
        if run:
            run.status = 'uploading'
            session.commit()

        # Extract data from metadata_data
        video_path = metadata_data.get('video_path', '')
        title = metadata_data.get('title', 'Manga Video')
        description = metadata_data.get('description', 'Manga chapter video')
        tags = metadata_data.get('tags', [])
        hashtags = metadata_data.get('hashtags', [])

        # Use async function wrapped in sync
        async def _upload():
            from ..uploader.manager import UploadManagerConfig
            from ..uploader import youtube, tiktok, facebook

            config = UploadManagerConfig(
                youtube_credentials={},  # Load from environment or credential manager
                tiktok_credentials={},
                facebook_credentials={}
            )
            upload_manager = UploadManager(config)

            upload_results = await upload_manager.upload_to_all_platforms(
                video_path=Path(video_path),
                title=title,
                description=description,
                tags=tags,
                hashtags=hashtags,
                languages={platform: language for platform in ['youtube', 'tiktok', 'facebook']}  # Simplified
            )

            return upload_results

        upload_results = async_to_sync(_upload)()

        logger.info(f"Successfully uploaded video to platforms")

        # Update status
        if run:
            run.status = 'upload_complete'
            session.commit()

        # Convert results to serializable format
        results = []
        for result in upload_results:
            results.append({
                'platform': str(result.platform),
                'upload_id': result.upload_id,
                'status': str(result.status),
                'details': result.details,
                'error_message': result.error_message
            })

        return results

    except Exception as e:
        logger.error(f"Error in upload_to_platform: {str(e)}")

        # Update status to error
        session = get_db_session()
        run = session.query(PipelineRun).filter_by(task_id=self.request.id).first()
        if run:
            run.status = 'error'
            run.error_message = str(e)
            session.commit()

        raise


@shared_task(bind=True, autoretry_for=(Exception,), retry_kwargs={'max_retries': 3, 'countdown': 60})
def cleanup_temp_files(self, temp_paths: list[str]):
    """
    Clean up temporary files created during processing.
    
    Args:
        temp_paths: List of paths to temporary files to clean up
        
    Returns:
        True if cleanup was successful
    """
    logger.info(f"Starting cleanup of {len(temp_paths)} temporary files")
    
    try:
        # Update pipeline run status
        session = get_db_session()
        run = session.query(PipelineRun).filter_by(task_id=self.request.id).first()
        if run:
            run.status = 'cleaning_up'
            session.commit()
        
        # Actually clean up the files
        cleaned_count = 0
        for temp_path in temp_paths:
            try:
                path_obj = Path(temp_path)
                if path_obj.exists():
                    path_obj.unlink()
                    cleaned_count += 1
            except Exception as e:
                logger.warning(f"Could not clean up {temp_path}: {str(e)}")
        
        logger.info(f"Successfully cleaned up {cleaned_count} temporary files")
        
        # Update status
        if run:
            run.status = 'cleanup_complete'
            session.commit()
        
        return {"files_cleaned": cleaned_count, "total_attempted": len(temp_paths)}
        
    except Exception as e:
        logger.error(f"Error in cleanup_temp_files: {str(e)}")
        
        # Update status to error
        session = get_db_session()
        run = session.query(PipelineRun).filter_by(task_id=self.request.id).first()
        if run:
            run.status = 'error'
            run.error_message = str(e)
            session.commit()
        
        raise


@shared_task(bind=True, autoretry_for=(Exception,), retry_kwargs={'max_retries': 3, 'countdown': 60})
def send_notification(self, message: str, notification_type: str = "info"):
    """
    Send a notification through available channels.
    
    Args:
        message: Message to send
        notification_type: Type of notification ('info', 'warning', 'error')
        
    Returns:
        True if notification was sent successfully
    """
    logger.info(f"Sending {notification_type} notification: {message[:50]}...")
    
    try:
        # Update pipeline run status
        session = get_db_session()
        run = session.query(PipelineRun).filter_by(task_id=self.request.id).first()
        if run:
            run.status = 'sending_notification'
            session.commit()
        
        # Use async function wrapped in sync
        async def _send():
            # Get bot credentials from environment or a credential manager
            bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
            chat_id = os.getenv("TELEGRAM_CHAT_ID")
            
            if bot_token and chat_id:
                notifier = TelegramNotifier(bot_token, chat_id)
                
                # Format message based on notification type
                if notification_type == "error":
                    formatted_message = f"🚨 ERROR: {message}"
                elif notification_type == "warning":
                    formatted_message = f"⚠️ WARNING: {message}"
                else:
                    formatted_message = f"ℹ️ INFO: {message}"
                
                # For now, just send a simple message
                # In a real implementation, we would have different methods for different event types
                await notifier._send_message(formatted_message)
            
            return True
        
        success = async_to_sync(_send)()
        
        logger.info(f"Successfully sent {notification_type} notification")
        
        # Update status
        if run:
            run.status = 'notification_sent'
            session.commit()
        
        return success
        
    except Exception as e:
        logger.error(f"Error in send_notification: {str(e)}")
        
        # Update status to error
        session = get_db_session()
        run = session.query(PipelineRun).filter_by(task_id=self.request.id).first()
        if run:
            run.status = 'error'
            run.error_message = str(e)
            session.commit()
        
        raise