from typing import Any
from ..discovery.manga_discovery import discovery
from ..scraper.manga_scraper import scraper
from ..ai.manga_ai import ai_processor
from ..video.manga_video_generator import video_generator
from ..uploader.video_uploader import uploader
from ..notifications.notification_service import notification_service
from ..database import (
    ChapterRepository,
    VideoRepository,
    MangaRepository,
    get_async_db
)
from ..config import get_settings
import asyncio
import os


class MangaVideoPipeline:
    """Main pipeline orchestrator for the manga video process."""

    def __init__(self):
        self.settings = get_settings()

    async def run_full_pipeline(self, manga_id: str, source: str, chapter_numbers: List[str] = None):
        """Run the complete manga video pipeline."""
        try:
            # Initialize scraper
            await scraper.start()
            
            # Step 1: Get manga info
            manga_info = await scraper.scrape_manga_info(manga_id, source)
            
            # Step 2: Process chapters
            if chapter_numbers is None:
                # For now, let's process a default chapter
                chapter_numbers = ["1"]  # In a real implementation, you'd discover available chapters
            
            for chapter_number in chapter_numbers:
                await self._process_single_chapter(manga_id, chapter_number, source, manga_info)
            
            # Send completion notification
            await notification_service.send_pipeline_status(
                f'Manga Video Pipeline for {manga_info.get("title", manga_id)}',
                'completed',
                {'manga_id': manga_id, 'total_chapters': len(chapter_numbers)}
            )
            
            print(f"Pipeline completed for manga {manga_id}")
        except Exception as e:
            print(f"Pipeline failed for manga {manga_id}: {e}")
            await notification_service.send_error_notification(
                str(e),
                f"Full pipeline execution for manga {manga_id}"
            )
        finally:
            # Close scraper
            await scraper.close()

    async def _process_single_chapter(self, manga_id: str, chapter_number: str, source: str, manga_info: dict[str, Any]):
        """Process a single manga chapter through the pipeline."""
        print(f"Processing chapter {chapter_number} of manga {manga_id}")
        
        try:
            # Step 1: Scrape chapter images
            print(f"Scraping chapter {chapter_number}...")
            image_urls = await scraper.scrape_chapter(manga_id, chapter_number, source)
            
            if not image_urls:
                raise Exception(f"No images found for chapter {chapter_number}")
            
            # Download images to temp directory
            image_paths = []
            for i, img_url in enumerate(image_urls):
                import requests
                response = requests.get(img_url)
                img_path = os.path.join(self.settings.pipeline.temp_path, f"manga_{manga_id}_chapter_{chapter_number}_img_{i}.jpg")
                with open(img_path, 'wb') as f:
                    f.write(response.content)
                image_paths.append(img_path)
            
            # Step 2: Generate summary using AI
            print(f"Generating summary for chapter {chapter_number}...")
            # In a real implementation, we would extract text from images or have access to chapter text
            chapter_text = f"Chapter {chapter_number} of {manga_info.get('title', 'Unknown Manga')}: This chapter contains exciting developments."
            summary = await ai_processor.summarize_chapters([chapter_text])
            
            # Step 3: Generate video script
            print(f"Generating video script for chapter {chapter_number}...")
            script = await ai_processor.generate_video_script(manga_info, summary)
            
            # Step 4: Generate TTS audio
            print(f"Generating TTS audio for chapter {chapter_number}...")
            audio_path = os.path.join(self.settings.pipeline.temp_path, f"manga_{manga_id}_chapter_{chapter_number}_audio.mp3")
            tts_success = await ai_processor.generate_tts(summary, audio_path)
            
            if not tts_success:
                raise Exception("Failed to generate TTS audio")
            
            # Step 5: Create video
            print(f"Creating video for chapter {chapter_number}...")
            output_path = os.path.join(self.settings.pipeline.output_path, f"manga_{manga_id}_chapter_{chapter_number}.mp4")
            video_success = video_generator.create_video(image_paths, audio_path, output_path)
            
            if not video_success:
                raise Exception("Failed to create video")
            
            # Step 6: Save video record to database
            video_record = create_video(self.db, {
                'title': f"{manga_info.get('title', 'Unknown Manga')} - Chapter {chapter_number}",
                'description': summary,
                'file_path': output_path,
                'audio_path': audio_path,
                'thumbnail_path': image_paths[0] if image_paths else None
            })
            
            # Step 7: Upload to platforms
            print(f"Uploading video for chapter {chapter_number}...")
            youtube_result = await uploader.upload_to_youtube(
                output_path,
                f"{manga_info.get('title', 'Unknown Manga')} - Chapter {chapter_number}",
                summary
            )
            
            if youtube_result.get('success'):
                video_record.uploaded_to_youtube = True
                video_record.youtube_url = youtube_result.get('url')
                self.db.commit()
            
            # Cleanup temporary files
            for img_path in image_paths:
                if os.path.exists(img_path):
                    os.remove(img_path)
            if os.path.exists(audio_path):
                os.remove(audio_path)
            
            print(f"Successfully processed chapter {chapter_number}")
        except Exception as e:
            print(f"Error processing chapter {chapter_number}: {e}")
            await notification_service.send_error_notification(
                str(e),
                f"Chapter processing for manga {manga_id}, chapter {chapter_number}"
            )
            raise e

    async def run_full_pipeline(self, manga_id: str, source: str, chapter_numbers: list[str] | None = None):
        """Run the complete manga video pipeline."""
        try:
            # Initialize scraper
            await scraper.start()

            # Get manga info
            manga_info = await scraper.scrape_manga_info(manga_id, source)

            # Process chapters
            if chapter_numbers is None:
                chapter_numbers = ["1"]  # Default to chapter 1

            for chapter_number in chapter_numbers:
                await self._process_single_chapter(manga_id, chapter_number, source, manga_info)

            # Send completion notification
            await notification_service.send_pipeline_status(
                f'Manga Video Pipeline for {manga_info.get("title", manga_id)}',
                'completed',
                {'manga_id': manga_id, 'total_chapters': len(chapter_numbers)}
            )

            print(f"Pipeline completed for manga {manga_id}")
        except Exception as e:
            print(f"Pipeline failed for manga {manga_id}: {e}")
            await notification_service.send_error_notification(
                str(e),
                f"Full pipeline execution for manga {manga_id}"
            )
        finally:
            # Close scraper
            await scraper.close()

    async def discover_and_process_trending(self):
        """Discover trending manga and process them through the pipeline."""
        print("Discovering trending manga...")
        trending_manga = await discovery.get_trending_manga()
        
        print(f"Found {len(trending_manga)} trending manga")
        
        for manga in trending_manga[:3]:  # Process first 3 for example
            manga_id = manga.get('id')
            source = manga.get('source')
            
            # Save manga to database
            db_manga = create_manga(self.db, manga)
            
            # Process the manga through the pipeline
            await self.run_full_pipeline(manga_id, source, chapter_numbers=["1"])
        
        print("Completed processing trending manga")


# Function to run the pipeline
async def run_pipeline():
    """Run the main pipeline."""
    pipeline = MangaVideoPipeline()
    await pipeline.discover_and_process_trending()


# For direct execution
if __name__ == "__main__":
    asyncio.run(run_pipeline())