from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class ScrapedPage:
    """Data class for a scraped manga page."""
    page_number: int
    image_path: Path
    original_url: str
    width: int | None = None
    height: int | None = None


@dataclass(slots=True)
class ScrapedChapter:
    """Data class for a scraped manga chapter."""
    chapter_id: str
    manga_title: str
    chapter_number: float
    pages: list[ScrapedPage]
    temp_dir: Path | None = None


class ChapterScraper(ABC):
    """Abstract base class for chapter scrapers."""
    
    @abstractmethod
    async def scrape_chapter(self, chapter_url: str) -> ScrapedChapter:
        """Scrape a chapter from the given URL."""
        pass
    
    @abstractmethod
    async def validate_url(self, url: str) -> bool:
        """Validate if the given URL is valid for this scraper."""
        pass