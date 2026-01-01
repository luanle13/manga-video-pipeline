import asyncio
from pathlib import Path
from typing import Any, Union
from .base import ScrapedChapter
from .mangadex import MangaDexScraper
from .webtoon import WebtoonScraper


class ScraperManager:
    """Main manager for chapter scraping across multiple sources."""
    
    def __init__(self):
        self.scrapers = {
            'mangadex': MangaDexScraper(),
            'webtoon': WebtoonScraper()
        }
    
    async def scrape_chapter(self, chapter_url: str) -> ScrapedChapter:
        """Scrape a single chapter from the given URL."""
        # Determine which scraper to use based on the URL
        scraper = await self._get_appropriate_scraper(chapter_url)
        if not scraper:
            raise ValueError(f"No appropriate scraper found for URL: {chapter_url}")
        
        return await scraper.scrape_chapter(chapter_url)
    
    async def scrape_chapters_batch(self, urls: list[str]) -> list[ScrapedChapter]:
        """Scrape multiple chapters concurrently."""
        results = []
        exceptions = []

        # Create tasks for concurrent scraping
        tasks = [self.scrape_chapter(url) for url in urls]

        try:
            # Use asyncio.gather to run all scraping tasks concurrently
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Process results and handle exceptions
            processed_results = []
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    error_msg = f"Error scraping {urls[i]}: {result}"
                    exceptions.append(result)  # Store the actual exception
                    print(error_msg)
                else:
                    processed_results.append(result)

            # If there were exceptions, raise them as an exception group
            if exceptions:
                try:
                    raise ExceptionGroup("Multiple scraping errors occurred", exceptions)
                except NameError:
                    # ExceptionGroup is not available in Python < 3.11
                    # If we have individual exceptions, we'll just raise the first one
                    # In a production environment, you might want to handle this differently
                    raise exceptions[0] if exceptions else RuntimeError("Unknown error occurred")

            return processed_results
        except Exception as e:
            print(f"Batch scraping error: {e}")
            raise e
    
    async def _get_appropriate_scraper(self, chapter_url: str):
        """Determine which scraper to use based on the URL."""
        for source, scraper in self.scrapers.items():
            if await scraper.validate_url(chapter_url):
                return scraper
        return None
    
    async def cleanup_temp(self, temp_dir: Path | None = None) -> bool:
        """Clean up temporary files created during scraping."""
        try:
            if temp_dir and temp_dir.exists():
                import shutil
                shutil.rmtree(temp_dir)
                return True
            else:
                # Clean up all temporary directories in data/temp
                base_temp = Path("data/temp")
                if base_temp.exists():
                    import shutil
                    shutil.rmtree(base_temp)
                    base_temp.mkdir(exist_ok=True)
                    return True
            return True
        except Exception as e:
            print(f"Error cleaning up temp files: {e}")
            return False
    
    async def close(self):
        """Close all scraper connections."""
        for scraper in self.scrapers.values():
            if hasattr(scraper, 'close'):
                await scraper.close()


# Global instance for convenience
scraper_manager = ScraperManager()