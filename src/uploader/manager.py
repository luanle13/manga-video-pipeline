from __future__ import annotations
import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List

from .base import BaseUploader, Platform, UploadResult
from .youtube import YouTubeUploader
from .tiktok import TikTokUploader
from .facebook import FacebookUploader


@dataclass(slots=True)
class UploadManagerConfig:
    """Configuration for UploadManager."""
    youtube_credentials: Dict[str, str] | None = None
    tiktok_credentials: Dict[str, str] | None = None
    facebook_credentials: Dict[str, str] | None = None


class UploadManager:
    """Manages uploads to multiple platforms concurrently."""
    
    def __init__(self, config: UploadManagerConfig):
        """
        Initialize the upload manager.
        
        Args:
            config: Configuration containing credentials for all platforms
        """
        self.config = config
        self.uploaders: Dict[Platform, BaseUploader | None] = {
            Platform.YOUTUBE: None,
            Platform.TIKTOK: None,
            Platform.FACEBOOK: None,
        }
        
        # Initialize uploaders if credentials are provided
        if config.youtube_credentials:
            self.uploaders[Platform.YOUTUBE] = YouTubeUploader(config.youtube_credentials)
        
        if config.tiktok_credentials:
            self.uploaders[Platform.TIKTOK] = TikTokUploader(config.tiktok_credentials)
        
        if config.facebook_credentials:
            self.uploaders[Platform.FACEBOOK] = FacebookUploader(config.facebook_credentials)
    
    async def upload_to_all_platforms(
        self,
        video_path: Path,
        title: str,
        description: str,
        tags: List[str],
        hashtags: List[str],
        languages: Dict[Platform, str] | None = None
    ) -> List[UploadResult]:
        """
        Upload a video to all available platforms concurrently.
        
        Args:
            video_path: Path to the video file to upload
            title: Title of the video
            description: Description of the video
            tags: List of tags for the video
            hashtags: List of hashtags for the video
            languages: Dictionary mapping platforms to language codes (e.g., "en", "vn")
            
        Returns:
            List of UploadResult objects for each platform
        """
        if languages is None:
            languages = {}
        
        # Filter out platforms without uploaders (no credentials)
        available_uploaders = {
            platform: uploader 
            for platform, uploader in self.uploaders.items() 
            if uploader is not None
        }
        
        if not available_uploaders:
            raise ValueError("No uploaders available - please provide at least one set of credentials")
        
        results: List[UploadResult] = []
        
        # Run uploads concurrently using TaskGroup
        async with asyncio.TaskGroup() as tg:
            tasks = []
            
            for platform, uploader in available_uploaders.items():
                task = tg.create_task(
                    uploader.upload(
                        video_path=video_path,
                        title=title,
                        description=description,
                        tags=tags,
                        hashtags=hashtags
                    ),
                    name=f"upload_to_{platform.value}"
                )
                tasks.append(task)
            
            # Collect results as tasks complete
            for task in tasks:
                result = await task
                results.append(result)
        
        # Save results to database (this would be implemented based on your database solution)
        await self._save_results_to_db(results)
        
        return results
    
    async def retry_failed_uploads(
        self,
        failed_results: List[UploadResult],
        max_retries: int = 3
    ) -> List[UploadResult]:
        """
        Retry failed uploads.
        
        Args:
            failed_results: List of UploadResult objects with failed status
            max_retries: Maximum number of retry attempts
            
        Returns:
            List of UploadResult objects for the retry attempts
        """
        retry_results: List[UploadResult] = []
        
        for result in failed_results:
            if result.status != "failed":
                continue
                
            original_uploader = self.uploaders.get(result.platform)
            if not original_uploader:
                continue
            
            for attempt in range(max_retries):
                try:
                    retry_result = await original_uploader.upload(
                        video_path=result.video_path,
                        title=f"Retry {attempt + 1}: {result.details.get('title', '')}" if result.details else "Retry",
                        description=result.details.get('description', '') if result.details else "",
                        tags=result.details.get('tags', []) if result.details else [],
                        hashtags=result.details.get('hashtags', []) if result.details else []
                    )
                    
                    retry_results.append(retry_result)
                    
                    if retry_result.status == "completed":
                        break
                        
                except Exception as e:
                    # If this is the last attempt, add a failed result
                    if attempt == max_retries - 1:
                        retry_results.append(
                            UploadResult(
                                platform=result.platform,
                                video_path=result.video_path,
                                upload_id=None,
                                status="failed",
                                error_message=f"Failed after {max_retries} retries: {str(e)}"
                            )
                        )
        
        # Save retry results to database
        await self._save_results_to_db(retry_results)
        
        return retry_results
    
    async def _save_results_to_db(self, results: List[UploadResult]) -> None:
        """
        Save upload results to database.
        
        Args:
            results: List of UploadResult objects to save
        """
        # This implementation would depend on your database solution
        # For now, this is a placeholder that could connect to your existing database
        # (e.g., SQLite, PostgreSQL, etc.) to store the upload results
        print(f"Saving {len(results)} results to database")
        
        # Example implementation if using a database:
        # This would require importing your database module and implementing
        # the actual database operations
        for result in results:
            print(f"Platform: {result.platform}, Status: {result.status}, Video: {result.video_path}")