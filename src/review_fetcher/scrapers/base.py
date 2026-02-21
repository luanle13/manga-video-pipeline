"""Abstract base class for manga scrapers."""

import asyncio
import random
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import ClassVar

import httpx
from pydantic import BaseModel

from src.common.models import MangaSource, ReviewChapterInfo, ReviewMangaInfo, SearchResult


class ChapterContent(BaseModel):
    """Content extracted from a manga chapter."""

    chapter_number: float
    title: str | None = None
    content_text: str  # Extracted dialogue/text
    panel_urls: list[str]  # URLs of panels in the chapter


@dataclass
class ScraperConfig:
    """Configuration for scraper behavior."""

    # Rate limiting
    min_delay_seconds: float = 1.0
    max_delay_seconds: float = 2.0

    # Retry settings
    max_retries: int = 3
    retry_delay_seconds: float = 5.0

    # Timeouts
    connect_timeout: float = 10.0
    read_timeout: float = 30.0

    # Batch settings (for chapter fetching)
    batch_size: int = 5  # Fetch 5 chapters concurrently


class BaseMangaScraper(ABC):
    """Abstract base class for manga site scrapers.

    Provides common functionality for rate limiting, retries, and HTTP requests.
    Subclasses implement site-specific scraping logic.
    """

    # Class-level constants to be overridden by subclasses
    BASE_URL: ClassVar[str] = ""
    SOURCE: ClassVar[MangaSource] = MangaSource.mangadex

    # Common user agents to rotate
    USER_AGENTS: ClassVar[list[str]] = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
    ]

    def __init__(self, config: ScraperConfig | None = None) -> None:
        """Initialize scraper with configuration."""
        self.config = config or ScraperConfig()
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> "BaseMangaScraper":
        """Async context manager entry."""
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(
                connect=self.config.connect_timeout,
                read=self.config.read_timeout,
                write=self.config.read_timeout,
                pool=self.config.read_timeout,
            ),
            follow_redirects=True,
            headers=self._get_headers(),
        )
        return self

    async def __aexit__(self, *args) -> None:
        """Async context manager exit."""
        if self._client:
            await self._client.aclose()
            self._client = None

    def _get_headers(self) -> dict[str, str]:
        """Get HTTP headers with random user agent."""
        return {
            "User-Agent": random.choice(self.USER_AGENTS),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
        }

    async def _rate_limit(self) -> None:
        """Apply rate limiting delay."""
        delay = random.uniform(
            self.config.min_delay_seconds,
            self.config.max_delay_seconds,
        )
        await asyncio.sleep(delay)

    async def _fetch(self, url: str, retry_count: int = 0) -> str:
        """Fetch URL with rate limiting and retries.

        Args:
            url: URL to fetch
            retry_count: Current retry attempt

        Returns:
            Response HTML content

        Raises:
            httpx.HTTPError: If request fails after all retries
        """
        if not self._client:
            raise RuntimeError("Scraper must be used as async context manager")

        await self._rate_limit()

        try:
            response = await self._client.get(url)
            response.raise_for_status()
            return response.text
        except httpx.HTTPError as e:
            if retry_count < self.config.max_retries:
                await asyncio.sleep(self.config.retry_delay_seconds)
                # Rotate user agent on retry
                self._client.headers["User-Agent"] = random.choice(self.USER_AGENTS)
                return await self._fetch(url, retry_count + 1)
            raise e

    async def _fetch_bytes(self, url: str, retry_count: int = 0) -> bytes:
        """Fetch URL and return raw bytes (for images).

        Args:
            url: URL to fetch
            retry_count: Current retry attempt

        Returns:
            Response bytes

        Raises:
            httpx.HTTPError: If request fails after all retries
        """
        if not self._client:
            raise RuntimeError("Scraper must be used as async context manager")

        await self._rate_limit()

        try:
            response = await self._client.get(url)
            response.raise_for_status()
            return response.content
        except httpx.HTTPError as e:
            if retry_count < self.config.max_retries:
                await asyncio.sleep(self.config.retry_delay_seconds)
                self._client.headers["User-Agent"] = random.choice(self.USER_AGENTS)
                return await self._fetch_bytes(url, retry_count + 1)
            raise e

    @abstractmethod
    async def search(self, query: str) -> list[SearchResult]:
        """Search for manga by name.

        Args:
            query: Search query (manga name)

        Returns:
            List of search results
        """
        ...

    @abstractmethod
    async def get_manga_info(self, url: str) -> ReviewMangaInfo:
        """Get manga information and chapter list from URL.

        Args:
            url: URL to manga page

        Returns:
            ReviewMangaInfo with chapter list (content_text will be empty)
        """
        ...

    @abstractmethod
    async def get_chapter_content(self, chapter_url: str) -> ChapterContent:
        """Get content from a single chapter.

        Args:
            chapter_url: URL to chapter page

        Returns:
            ChapterContent with text and panel URLs
        """
        ...

    async def get_all_chapter_content(
        self,
        manga_info: ReviewMangaInfo,
        max_chapters: int | None = None,
    ) -> ReviewMangaInfo:
        """Fetch content for all chapters in manga_info.

        Fetches chapters in batches to avoid overloading the server.

        Args:
            manga_info: Manga info with chapter list
            max_chapters: Optional limit on chapters to fetch

        Returns:
            Updated ReviewMangaInfo with chapter content filled in
        """
        chapters = manga_info.chapters
        if max_chapters:
            chapters = chapters[:max_chapters]

        updated_chapters: list[ReviewChapterInfo] = []

        # Process in batches
        for i in range(0, len(chapters), self.config.batch_size):
            batch = chapters[i : i + self.config.batch_size]

            # Fetch batch concurrently
            tasks = [self.get_chapter_content(ch.url) for ch in batch]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            for chapter, result in zip(batch, results, strict=True):
                if isinstance(result, Exception):
                    # Keep chapter but with empty content on error
                    updated_chapters.append(chapter)
                else:
                    # Update chapter with fetched content
                    updated_chapter = ReviewChapterInfo(
                        chapter_number=chapter.chapter_number,
                        title=result.title or chapter.title,
                        url=chapter.url,
                        content_text=result.content_text,
                        key_panel_url=result.panel_urls[0] if result.panel_urls else None,
                    )
                    updated_chapters.append(updated_chapter)

        # Return updated manga info
        return ReviewMangaInfo(
            source=manga_info.source,
            source_url=manga_info.source_url,
            title=manga_info.title,
            author=manga_info.author,
            genres=manga_info.genres,
            description=manga_info.description,
            cover_url=manga_info.cover_url,
            total_chapters=manga_info.total_chapters,
            chapters=updated_chapters,
        )
