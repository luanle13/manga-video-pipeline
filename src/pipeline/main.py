from typing import Any
from ..discovery import discovery_manager
from ..scraper import scraper_manager
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
            # In the new system, we need a chapter URL to scrape
            # For MangaDex, we construct a typical URL
            if source == 'mangadex':
                chapter_url = f"https://mangadex.org/chapter/{manga_id}/{chapter_number}"
            elif source == 'webtoon':
                chapter_url = f"https://www.webtoons.com/en/{manga_id}/episode?episodeNo={chapter_number}"
            else:
                raise ValueError(f"Unsupported source: {source}")

            # Step 1: Scrape chapter images using new scraper
            print(f"Scraping chapter {chapter_number} from {chapter_url}...")
            scraped_chapter = await scraper_manager.scrape_chapter(chapter_url)

            if not scraped_chapter.pages:
                raise Exception(f"No pages found for chapter {chapter_number}")

            # Extract image paths from scraped chapter
            image_paths = [page.image_path for page in scraped_chapter.pages]

            # Step 2: Generate summary using AI
            print(f"Generating summary for chapter {chapter_number}...")
            # Create a basic chapter text to summarize
            chapter_text = f"Chapter {chapter_number} of {manga_info.get('title', 'Unknown Manga')}: This chapter contains exciting developments across {len(image_paths)} pages."
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

            # Step 6: Save video record to database using async operations
            async for db in get_async_db():
                video_data = {
                    'chapter_id': 1,  # Placeholder - would need to get actual chapter ID
                    'language': 'en',
                    'title': f"{manga_info.get('title', 'Unknown Manga')} - Chapter {chapter_number}",
                    'description': summary,
                    'script': script,
                    'file_path': output_path,
                    'is_uploaded': False
                }
                video_record = await VideoRepository.create(db, video_data)

            # Step 7: Upload to platforms
            print(f"Uploading video for chapter {chapter_number}...")
            youtube_result = await uploader.upload_to_youtube(
                output_path,
                f"{manga_info.get('title', 'Unknown Manga')} - Chapter {chapter_number}",
                summary
            )

            # Cleanup temporary files using scraper manager
            if scraped_chapter.temp_dir:
                await scraper_manager.cleanup_temp(scraped_chapter.temp_dir)

            # Cleanup audio file
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
            # Create basic manga info since we no longer get it from scraper
            manga_info = {'title': f"Manga {manga_id}"}

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
            # Close scraper manager
            await scraper_manager.close()

    async def discover_and_process_trending(self):
        """Discover trending manga and process them through the pipeline."""
        print("Discovering trending manga...")
        trending_manga = await discovery_manager.discover_trending()
        
        print(f"Found {len(trending_manga)} trending manga")
        
        for manga in trending_manga[:3]:  # Process first 3 for example
            manga_id = manga.source_id
            source = manga.source

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