from __future__ import annotations
from celery import chain, group, chord
from celery.result import AsyncResult
from ..celery_app import app
from . import tasks
from ..db import get_db_session, PipelineRun
import logging
from datetime import datetime
from typing import List, Dict, Any
import tempfile
import os


logger = logging.getLogger(__name__)


class PipelineWorkflow:
    """Manages the manga video pipeline workflow using Celery."""
    
    def __init__(self):
        self.session = get_db_session()
    
    def process_chapter(
        self,
        manga_title: str,
        manga_url: str,
        chapter_number: float,
        language: str = "en",
        voice: str = "alloy"
    ) -> AsyncResult:
        """
        Process a single manga chapter through the full pipeline.
        
        Args:
            manga_title: Title of the manga
            manga_url: URL of the manga
            chapter_number: Chapter number to process
            language: Language code ('en' or 'vn')
            voice: Voice for TTS
            
        Returns:
            Celery AsyncResult of the chained tasks
        """
        logger.info(f"Starting pipeline for chapter {chapter_number} of {manga_title}")
        
        # Create a pipeline run record in the database
        run = PipelineRun(
            manga_title=manga_title,
            chapter_number=chapter_number,
            language=language,
            status='started',
            started_at=datetime.utcnow()
        )
        self.session.add(run)
        self.session.commit()
        
        # Create a temporary directory for this chapter
        temp_dir = f"/tmp/manga_video_pipeline/{manga_title}_ch{chapter_number}_{int(datetime.utcnow().timestamp())}"
        os.makedirs(temp_dir, exist_ok=True)
        
        temp_audio_path = f"{temp_dir}/audio.mp3"
        temp_video_path = f"{temp_dir}/video.mp4"
        temp_paths = [temp_audio_path, temp_video_path]
        
        # Create the task chain for processing a single chapter
        # Each task passes its result to the next one
        task_chain = (
            # Step 1: Scrape the chapter images
            tasks.scrape_chapter.si(manga_url, chapter_number) |
            
            # Step 2: Generate summary using the scraped images
            tasks.generate_summary.si(manga_title, chapter_number, language) |
            
            # Step 3: Generate audio from the summary
            tasks.generate_audio.si(temp_audio_path, language, voice) |
            
            # Step 4: Generate video from images and audio 
            tasks.generate_video.si(temp_video_path) |
            
            # Step 5: Generate metadata for the video
            tasks.generate_metadata.si(manga_title, chapter_number, language) |
            
            # Step 6: Upload the video to platforms
            tasks.upload_to_platform.si(language) |
            
            # Step 7: Send notification
            tasks.send_notification.si("Chapter processed successfully", "info") |
            
            # Step 8: Clean up temporary files
            tasks.cleanup_temp_files.si(temp_paths)
        )
        
        # Add callback for error handling
        result = task_chain.apply_async(
            link_error=tasks.send_notification.s(
                f"Pipeline failed for {manga_title} chapter {chapter_number}",
                "error"
            )
        )
        
        # Update the run with the task ID
        run.task_id = result.task_id
        self.session.commit()
        
        logger.info(f"Started pipeline chain for {manga_title} chapter {chapter_number}, task ID: {result.task_id}")
        return result
    
    def process_daily_batch(self, manga_list: List[Dict[str, Any]]) -> List[AsyncResult]:
        """
        Process multiple manga chapters in parallel.
        
        Args:
            manga_list: List of manga dictionaries with title, url, chapters, etc.
            
        Returns:
            List of Celery AsyncResults for each chapter processed
        """
        logger.info(f"Starting daily batch processing for {len(manga_list)} manga")
        
        results = []
        
        # Create a pipeline run record for the batch
        batch_run = PipelineRun(
            manga_title="BATCH_PROCESS",
            chapter_number=0.0,
            language="batch",
            status='batch_started',
            started_at=datetime.utcnow()
        )
        self.session.add(batch_run)
        self.session.commit()
        
        for manga_info in manga_list:
            manga_title = manga_info.get('title', '')
            manga_url = manga_info.get('url', '')
            chapters = manga_info.get('chapters', [])
            language = manga_info.get('language', 'en')
            voice = manga_info.get('voice', 'alloy')
            
            for chapter_number in chapters:
                result = self.process_chapter(
                    manga_title=manga_title,
                    manga_url=manga_url,
                    chapter_number=chapter_number,
                    language=language,
                    voice=voice
                )
                results.append(result)
        
        # Update batch status
        batch_run.status = 'batch_processing'
        self.session.commit()
        
        logger.info(f"Started {len(results)} pipeline tasks for batch processing")
        return results


# For use outside workflow class
def start_single_chapter_pipeline(
    manga_title: str,
    manga_url: str,
    chapter_number: float,
    language: str = "en",
    voice: str = "alloy"
) -> AsyncResult:
    """
    Start a single chapter pipeline outside of the workflow class.
    
    Args:
        manga_title: Title of the manga
        manga_url: URL of the manga
        chapter_number: Chapter number to process
        language: Language code ('en' or 'vn')
        voice: Voice for TTS
        
    Returns:
        Celery AsyncResult of the chained tasks
    """
    workflow = PipelineWorkflow()
    return workflow.process_chapter(
        manga_title=manga_title,
        manga_url=manga_url,
        chapter_number=chapter_number,
        language=language,
        voice=voice
    )


def start_daily_batch_pipeline(manga_list: List[Dict[str, Any]]) -> List[AsyncResult]:
    """
    Start a daily batch pipeline outside of the workflow class.
    
    Args:
        manga_list: List of manga dictionaries with title, url, chapters, etc.
        
    Returns:
        List of Celery AsyncResults for each chapter processed
    """
    workflow = PipelineWorkflow()
    return workflow.process_daily_batch(manga_list)