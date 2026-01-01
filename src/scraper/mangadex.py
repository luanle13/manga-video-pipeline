import asyncio
import httpx
from pathlib import Path
from PIL import Image
import json
from typing import Any
from .base import ChapterScraper, ScrapedChapter, ScrapedPage


class MangaDexScraper(ChapterScraper):
    """MangaDex chapter scraper implementation."""
    
    def __init__(self, max_concurrent_downloads: int = 3):
        self.client = httpx.AsyncClient(
            headers={"User-Agent": "MangaVideoPipeline/1.0"},
            timeout=30.0
        )
        self.semaphore = asyncio.Semaphore(max_concurrent_downloads)
    
    async def scrape_chapter(self, chapter_url: str) -> ScrapedChapter:
        """Scrape a chapter from MangaDex."""
        # Extract chapter ID from URL
        chapter_id = self._extract_chapter_id(chapter_url)
        if not chapter_id:
            raise ValueError(f"Could not extract chapter ID from URL: {chapter_url}")
        
        # Get chapter data from MangaDex API
        at_home_data = await self._get_at_home_data(chapter_id)
        if not at_home_data:
            raise ValueError(f"Could not get at-home data for chapter: {chapter_id}")
        
        # Create temporary directory for chapter
        temp_dir = Path("data/temp") / f"chapter_{chapter_id}"
        temp_dir.mkdir(parents=True, exist_ok=True)
        
        # Download pages concurrently
        base_url = at_home_data["baseUrl"]
        chapter_hash = at_home_data["chapter"]["hash"]
        filenames = at_home_data["chapter"]["data"]
        
        pages = []
        for i, filename in enumerate(filenames):
            page_url = f"{base_url}/data/{chapter_hash}/{filename}"
            local_path = temp_dir / f"page_{i+1:03d}.jpg"
            
            # Download image
            await self._download_image(page_url, local_path)
            
            # Get image dimensions
            width, height = self._get_image_dimensions(local_path)
            
            page = ScrapedPage(
                page_number=i + 1,
                image_path=local_path,
                original_url=page_url,
                width=width,
                height=height
            )
            pages.append(page)
        
        # Extract manga title and chapter number
        manga_title = "Unknown Manga"  # Would be extracted from a manga endpoint
        chapter_number = float(chapter_id)
        
        return ScrapedChapter(
            chapter_id=chapter_id,
            manga_title=manga_title,
            chapter_number=chapter_number,
            pages=pages,
            temp_dir=temp_dir
        )
    
    async def validate_url(self, url: str) -> bool:
        """Validate if the URL is a valid MangaDex chapter URL."""
        return "mangadex.org/chapter/" in url or "mangadex.org/c/" in url or "api.mangadex.org/chapter/" in url
    
    def _extract_chapter_id(self, url: str) -> str | None:
        """Extract chapter ID from MangaDex URL."""
        import re
        # Pattern matches various MangaDex URL formats
        patterns = [
            r'mangadex\.org/chapter/([a-f0-9-]+)',
            r'mangadex\.org/c/([a-f0-9-]+)',
            r'api\.mangadex\.org/chapter/([a-f0-9-]+)'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        
        return None
    
    async def _get_at_home_data(self, chapter_id: str) -> dict[str, Any] | None:
        """Get at-home server data for a chapter."""
        try:
            response = await self.client.get(f"https://api.mangadex.org/at-home/server/{chapter_id}")
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"Error getting at-home data for chapter {chapter_id}: {e}")
            return None
    
    async def _download_image(self, image_url: str, save_path: Path) -> None:
        """Download an image with concurrency control."""
        async with self.semaphore:  # Limit concurrent downloads
            try:
                response = await self.client.get(image_url)
                response.raise_for_status()
                
                # Save image
                save_path.parent.mkdir(parents=True, exist_ok=True)
                with open(save_path, 'wb') as f:
                    f.write(response.content)
                
                # Validate image
                await self._validate_image(save_path)
            except Exception as e:
                print(f"Error downloading image {image_url}: {e}")
                raise e
    
    async def _validate_image(self, image_path: Path) -> bool:
        """Validate an image file using PIL."""
        try:
            with Image.open(image_path) as img:
                # Verify image can be opened and has valid dimensions
                if img.width <= 0 or img.height <= 0:
                    raise ValueError(f"Invalid image dimensions: {img.width}x{img.height}")
                return True
        except Exception as e:
            print(f"Invalid image file {image_path}: {e}")
            # Remove the invalid image
            if image_path.exists():
                image_path.unlink()
            return False
    
    def _get_image_dimensions(self, image_path: Path) -> tuple[int, int]:
        """Get image dimensions using PIL."""
        try:
            with Image.open(image_path) as img:
                return img.width, img.height
        except Exception as e:
            print(f"Error getting image dimensions for {image_path}: {e}")
            return 0, 0
    
    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()