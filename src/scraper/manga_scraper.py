import asyncio
from playwright.async_api import async_playwright
from typing import Any, List
from ..config import get_settings


class MangaScraper:
    """Scrape manga chapters from various sources."""
    
    def __init__(self):
        self.settings = get_settings()
        self.playwright = None
        self.browser = None

    async def start(self):
        """Initialize the scraper."""
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(
            headless=True  # Default to headless, can be configured as needed
        )

    async def close(self):
        """Close the scraper."""
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()

    async def scrape_chapter(self, manga_id: str, chapter_number: str, source: str) -> list[str]:
        """Scrape images from a specific chapter."""
        if source == "mangadex":
            return await self._scrape_mangadex_chapter(manga_id, chapter_number)
        else:
            print(f"Unsupported source: {source}")
            return []

    async def _scrape_mangadex_chapter(self, manga_id: str, chapter_number: str) -> list[str]:
        """Scrape a chapter from MangaDex."""
        try:
            page = await self.browser.new_page()
            
            # Get chapter ID for the specific chapter
            async with page.context.expect_response(lambda response: 
                "api.mangadex.org/at-home/server" in response.url) as response_info:
                await page.goto(f"https://mangadex.org/chapter/{manga_id}/{chapter_number}")
            
            response = await response_info.value
            data = await response.json()
            
            base_url = data["baseUrl"]
            chapter_data = data["chapter"]
            hash_val = chapter_data["hash"]
            page_filenames = chapter_data["data"]
            
            image_urls = []
            for filename in page_filenames:
                img_url = f"{base_url}/data/{hash_val}/{filename}"
                image_urls.append(img_url)
            
            await page.close()
            return image_urls
        except Exception as e:
            print(f"Error scraping chapter {chapter_number} from MangaDex: {e}")
            return []

    async def scrape_manga_info(self, manga_id: str, source: str) -> dict[str, Any]:
        """Scrape manga information."""
        if source == "mangadex":
            return await self._scrape_mangadex_manga_info(manga_id)
        else:
            print(f"Unsupported source: {source}")
            return {}

    async def _scrape_mangadex_manga_info(self, manga_id: str) -> dict[str, Any]:
        """Scrape manga info from MangaDex."""
        try:
            page = await self.browser.new_page()
            await page.goto(f"https://mangadex.org/title/{manga_id}")
            
            # Extract manga title
            title_element = await page.query_selector("h1")
            title = await title_element.text_content() if title_element else "Unknown"
            
            # Extract description
            description_element = await page.query_selector("div#description")
            description = await description_element.text_content() if description_element else ""
            
            # Extract cover image
            cover_element = await page.query_selector("img[alt='Cover']")
            cover_url = await cover_element.get_attribute("src") if cover_element else ""
            
            await page.close()
            
            return {
                "title": title.strip(),
                "description": description.strip(),
                "cover_url": cover_url
            }
        except Exception as e:
            print(f"Error scraping manga info from MangaDex: {e}")
            return {}


# Global scraper instance
scraper = MangaScraper()