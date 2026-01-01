from .base import ScrapedPage, ScrapedChapter, ChapterScraper
from .mangadex import MangaDexScraper
from .webtoon import WebtoonScraper
from .manager import ScraperManager, scraper_manager

__all__ = [
    "ScrapedPage",
    "ScrapedChapter",
    "ChapterScraper",
    "MangaDexScraper",
    "WebtoonScraper",
    "ScraperManager",
    "scraper_manager"
]