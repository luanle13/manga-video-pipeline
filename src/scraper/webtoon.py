import asyncio
from pathlib import Path
import httpx
from typing import Any
from playwright.async_api import async_playwright
from PIL import Image
from .base import ChapterScraper, ScrapedChapter, ScrapedPage


class WebtoonScraper(ChapterScraper):
    """Webtoon.com chapter scraper implementation."""
    
    def __init__(self):
        self.playwright = None
        self.browser = None
        self.http_client = httpx.AsyncClient(
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
            timeout=30.0
        )
    
    async def scrape_chapter(self, chapter_url: str) -> ScrapedChapter:
        """Scrape a chapter from webtoons.com."""
        if not await self.validate_url(chapter_url):
            raise ValueError(f"Invalid Webtoon URL: {chapter_url}")
        
        # Initialize Playwright
        await self._init_playwright()
        
        # Extract info from URL
        chapter_id = self._extract_chapter_id(chapter_url)
        manga_title = "Unknown Webtoon"  # Would extract from page
        
        # Create temporary directory for chapter
        temp_dir = Path("data/temp") / f"webtoon_chapter_{chapter_id}"
        temp_dir.mkdir(parents=True, exist_ok=True)
        
        # Use Playwright to get the page and extract image URLs
        page = await self.browser.new_page()
        await page.goto(chapter_url)
        await page.wait_for_load_state('networkidle')
        
        # Scroll to trigger lazy loading of images
        await self._scroll_to_load_images(page)
        
        # Extract image URLs from the page
        image_urls = await self._extract_image_urls(page)
        await page.close()
        
        # Download images concurrently
        pages = []
        for i, img_url in enumerate(image_urls):
            local_path = temp_dir / f"page_{i+1:03d}.jpg"
            
            # Download image with Referer header
            await self._download_image(img_url, local_path, chapter_url)
            
            # Get image dimensions
            width, height = self._get_image_dimensions(local_path)
            
            page_obj = ScrapedPage(
                page_number=i + 1,
                image_path=local_path,
                original_url=img_url,
                width=width,
                height=height
            )
            pages.append(page_obj)
        
        chapter_number = float(chapter_id) if chapter_id.isdigit() else 1.0
        
        return ScrapedChapter(
            chapter_id=chapter_id,
            manga_title=manga_title,
            chapter_number=chapter_number,
            pages=pages,
            temp_dir=temp_dir
        )
    
    async def validate_url(self, url: str) -> bool:
        """Validate if the URL is a valid Webtoon chapter URL."""
        return "webtoons.com" in url and "/viewer/" in url
    
    def _extract_chapter_id(self, url: str) -> str:
        """Extract chapter ID from Webtoon URL."""
        import re
        # Extract chapter ID from the URL
        match = re.search(r'episodeNo=(\d+)', url)
        if match:
            return match.group(1)
        # If not found in query parameter, try to extract from URL structure
        parts = url.split('/')
        for part in parts:
            if part.isdigit():
                return part
        return "unknown"
    
    async def _init_playwright(self):
        """Initialize Playwright browser."""
        if not self.playwright:
            self.playwright = await async_playwright().start()
            self.browser = await self.playwright.chromium.launch(headless=True)
    
    async def _scroll_to_load_images(self, page):
        """Scroll the page to load lazy images."""
        # Get initial height
        last_height = await page.evaluate("document.body.scrollHeight")
        
        while True:
            # Scroll to bottom
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            
            # Wait for new content to load
            await page.wait_for_timeout(2000)
            
            # Calculate new height
            new_height = await page.evaluate("document.body.scrollHeight")
            
            if new_height == last_height:
                break
            
            last_height = new_height
    
    async def _extract_image_urls(self, page) -> list[str]:
        """Extract image URLs from the page."""
        # Look for image elements in Webtoon pages
        image_elements = await page.query_selector_all('div#_imageList img')
        image_urls = []
        
        for img in image_elements:
            src = await img.get_attribute('src')
            if src:
                # Handle relative URLs
                if src.startswith('//'):
                    src = 'https:' + src
                elif src.startswith('/'):
                    src = 'https://www.webtoons.com' + src
                image_urls.append(src)
        
        # If the above selector doesn't work, try alternative selectors
        if not image_urls:
            image_elements = await page.query_selector_all('img[data-url]')
            for img in image_elements:
                src = await img.get_attribute('data-url')
                if src:
                    if src.startswith('//'):
                        src = 'https:' + src
                    elif src.startswith('/'):
                        src = 'https://www.webtoons.com' + src
                    image_urls.append(src)
        
        return image_urls
    
    async def _download_image(self, image_url: str, save_path: Path, referer_url: str) -> None:
        """Download an image with referer header."""
        try:
            response = await self.http_client.get(
                image_url,
                headers={"Referer": referer_url}
            )
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
        """Close Playwright browser and HTTP client."""
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()
        await self.http_client.aclose()