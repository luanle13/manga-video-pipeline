"""TruyenQQ manga scraper.

Scrapes manga content from truyenqqno.com (TruyenQQ).
"""

import re
from typing import ClassVar
from urllib.parse import quote, urljoin

from bs4 import BeautifulSoup

from src.common.models import MangaSource, ReviewChapterInfo, ReviewMangaInfo, SearchResult

from .base import BaseMangaScraper, ChapterContent


class TruyenQQScraper(BaseMangaScraper):
    """Scraper for truyenqqno.com."""

    BASE_URL: ClassVar[str] = "https://truyenqqno.com"
    SOURCE: ClassVar[MangaSource] = MangaSource.truyenqq

    async def search(self, query: str) -> list[SearchResult]:
        """Search for manga by name.

        Args:
            query: Search query (manga name)

        Returns:
            List of search results
        """
        # URL encode the query
        encoded_query = quote(query)
        search_url = f"{self.BASE_URL}/tim-kiem.html?q={encoded_query}"

        html = await self._fetch(search_url)
        soup = BeautifulSoup(html, "html.parser")

        results: list[SearchResult] = []

        # Find all manga items in search results
        # TruyenQQ uses .list_grid for search results
        manga_items = soup.select(".list_grid .book_avatar") or soup.select(
            ".list-stories .story-item"
        )

        for item in manga_items[:10]:  # Limit to 10 results
            # Extract title and URL
            link = item.find("a")
            if not link:
                continue

            title_elem = link.get("title") or link.text.strip()
            url = link.get("href", "")
            if url and not url.startswith("http"):
                url = urljoin(self.BASE_URL, url)

            # Extract cover image
            img = item.find("img")
            cover_url = img.get("src") or img.get("data-src") if img else None

            # Extract chapter count if available
            chapter_count = None
            chapter_elem = item.select_one(".chapter-count") or item.select_one(
                ".last_chapter"
            )
            if chapter_elem:
                match = re.search(r"(\d+)", chapter_elem.text)
                if match:
                    chapter_count = int(match.group(1))

            results.append(
                SearchResult(
                    title=str(title_elem),
                    url=url,
                    cover_url=cover_url,
                    source=self.SOURCE,
                    chapter_count=chapter_count,
                )
            )

        return results

    async def get_manga_info(self, url: str) -> ReviewMangaInfo:
        """Get manga information and chapter list from URL.

        Args:
            url: URL to manga page

        Returns:
            ReviewMangaInfo with chapter list
        """
        html = await self._fetch(url)
        soup = BeautifulSoup(html, "html.parser")

        # Extract title
        title_elem = soup.select_one("h1") or soup.select_one(".book_detail h1")
        title = title_elem.text.strip() if title_elem else "Unknown"

        # Extract cover image
        cover_img = soup.select_one(".book_avatar img") or soup.select_one(
            ".book_detail img"
        )
        cover_url = ""
        if cover_img:
            cover_url = cover_img.get("src") or cover_img.get("data-src") or ""

        # Extract author
        author = None
        author_elem = soup.select_one(".author a") or soup.select_one(
            'li:contains("Tác giả") a'
        )
        if author_elem:
            author = author_elem.text.strip()

        # Extract genres
        genres: list[str] = []
        genre_links = soup.select(".list01 a") or soup.select(".category a")
        for genre_link in genre_links:
            genres.append(genre_link.text.strip())

        # Extract description
        description = None
        desc_elem = soup.select_one(".story-detail-info") or soup.select_one(
            ".book_info .detail"
        )
        if desc_elem:
            description = desc_elem.text.strip()

        # Extract chapter list
        chapters: list[ReviewChapterInfo] = []
        chapter_links = soup.select(".works-chapter-item") or soup.select(
            ".list_chapter a"
        )

        # If no chapters found with those selectors, try a broader search
        if not chapter_links:
            chapter_links = soup.select("a[href*='-chap-']")

        for link in chapter_links:
            href = link.get("href", "")
            if not href:
                continue

            # Make URL absolute
            if not href.startswith("http"):
                href = urljoin(self.BASE_URL, href)

            # Extract chapter number from URL or text
            chapter_num = self._extract_chapter_number(href, link.text)
            if chapter_num is None:
                continue

            chapter_title = link.text.strip() if link.text else None

            chapters.append(
                ReviewChapterInfo(
                    chapter_number=chapter_num,
                    title=chapter_title,
                    url=href,
                    content_text="",  # Will be filled by get_chapter_content
                )
            )

        # Sort chapters by number (ascending)
        chapters.sort(key=lambda c: c.chapter_number)

        # Remove duplicates (by chapter number)
        seen_chapters: set[float] = set()
        unique_chapters: list[ReviewChapterInfo] = []
        for ch in chapters:
            if ch.chapter_number not in seen_chapters:
                seen_chapters.add(ch.chapter_number)
                unique_chapters.append(ch)

        return ReviewMangaInfo(
            source=self.SOURCE,
            source_url=url,
            title=title,
            author=author,
            genres=genres,
            description=description,
            cover_url=cover_url,
            total_chapters=len(unique_chapters),
            chapters=unique_chapters,
        )

    def _extract_chapter_number(self, url: str, text: str) -> float | None:
        """Extract chapter number from URL or text.

        Args:
            url: Chapter URL
            text: Chapter link text

        Returns:
            Chapter number as float, or None if not found
        """
        # Try to extract from URL first (more reliable)
        # Pattern: -chap-123 or -chap-123.5
        url_match = re.search(r"-chap-(\d+(?:\.\d+)?)", url)
        if url_match:
            return float(url_match.group(1))

        # Try to extract from text
        # Patterns: "Chapter 123", "Chap 123", "Chương 123"
        text_patterns = [
            r"Chapter\s*(\d+(?:\.\d+)?)",
            r"Chap\s*(\d+(?:\.\d+)?)",
            r"Chương\s*(\d+(?:\.\d+)?)",
            r"^(\d+(?:\.\d+)?)$",  # Just a number
        ]
        for pattern in text_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return float(match.group(1))

        return None

    async def get_chapter_content(self, chapter_url: str) -> ChapterContent:
        """Get content from a single chapter.

        Args:
            chapter_url: URL to chapter page

        Returns:
            ChapterContent with text and panel URLs
        """
        html = await self._fetch(chapter_url)
        soup = BeautifulSoup(html, "html.parser")

        # Extract chapter number from URL
        chapter_num = self._extract_chapter_number(chapter_url, "") or 0.0

        # Extract chapter title if available
        title = None
        title_elem = soup.select_one("h1") or soup.select_one(".chapter_title")
        if title_elem:
            title = title_elem.text.strip()

        # Extract panel images
        panel_urls: list[str] = []

        # TruyenQQ uses .chapter_content for the image container
        content_div = soup.select_one(".chapter_content") or soup.select_one(
            ".page-chapter"
        )
        if content_div:
            images = content_div.select("img")
            for img in images:
                src = img.get("src") or img.get("data-src") or img.get("data-original")
                if src:
                    panel_urls.append(src)

        # If no images found in content div, try broader search
        if not panel_urls:
            images = soup.select("img[src*='hinhhinh.com']") or soup.select(
                "img[data-src*='hinhhinh.com']"
            )
            for img in images:
                src = img.get("src") or img.get("data-src")
                if src:
                    panel_urls.append(src)

        # Note: Vietnamese manga sites typically have text embedded in images
        # We return empty content_text as there's no separate text to extract
        # The review script generator will need to describe panels or use
        # a different approach for manga without extractable text

        return ChapterContent(
            chapter_number=chapter_num,
            title=title,
            content_text="",  # Text is in images, not extractable
            panel_urls=panel_urls,
        )
