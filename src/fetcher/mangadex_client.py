"""MangaDex API client for fetching trending manga and chapter data."""

import time
from typing import Any

import httpx

from src.common.logging_config import setup_logger
from src.common.models import ChapterInfo, MangaInfo

logger = setup_logger(__name__)

# Rate limiting: 5 requests per second
RATE_LIMIT_INTERVAL = 0.2  # 200ms between requests
MAX_RETRIES = 3
RETRY_BASE_DELAY = 2  # seconds
CHAPTERS_PER_PAGE = 500


class MangaDexAPIError(Exception):
    """Raised when MangaDex API returns an error."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class RateLimiter:
    """Simple rate limiter for API calls."""

    def __init__(self, min_interval: float = RATE_LIMIT_INTERVAL) -> None:
        self._min_interval = min_interval
        self._last_request_time: float = 0

    def wait(self) -> None:
        """Wait if necessary to respect rate limit."""
        now = time.time()
        elapsed = now - self._last_request_time
        if elapsed < self._min_interval:
            sleep_time = self._min_interval - elapsed
            time.sleep(sleep_time)
        self._last_request_time = time.time()


class MangaDexClient:
    """Client for MangaDex API."""

    def __init__(self, base_url: str, timeout: int = 30) -> None:
        """
        Initialize the MangaDex client.

        Args:
            base_url: Base URL for MangaDex API.
            timeout: Request timeout in seconds.
        """
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._rate_limiter = RateLimiter()
        self._client = httpx.Client(timeout=timeout)

        logger.info(
            "MangaDex client initialized",
            extra={"base_url": self._base_url, "timeout": timeout},
        )

    def close(self) -> None:
        """Close the HTTP client."""
        self._client.close()

    def __enter__(self) -> "MangaDexClient":
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()

    def _request(
        self,
        method: str,
        endpoint: str,
        params: dict | None = None,
    ) -> dict:
        """
        Make an HTTP request with retry logic.

        Args:
            method: HTTP method.
            endpoint: API endpoint.
            params: Query parameters.

        Returns:
            JSON response as dict.

        Raises:
            MangaDexAPIError: On API errors.
            httpx.TimeoutException: On timeout.
        """
        url = f"{self._base_url}{endpoint}"

        for attempt in range(MAX_RETRIES):
            self._rate_limiter.wait()

            try:
                logger.debug(
                    "Making API request",
                    extra={"method": method, "url": url, "attempt": attempt + 1},
                )

                response = self._client.request(method, url, params=params)

                logger.info(
                    "API response received",
                    extra={"url": url, "status_code": response.status_code},
                )

                if response.status_code == 200:
                    return response.json()

                if response.status_code in (429, 500, 502, 503, 504):
                    # Retry on rate limit or server errors
                    if attempt < MAX_RETRIES - 1:
                        delay = RETRY_BASE_DELAY * (2**attempt)
                        logger.warning(
                            "Retrying after error",
                            extra={
                                "status_code": response.status_code,
                                "attempt": attempt + 1,
                                "delay": delay,
                            },
                        )
                        time.sleep(delay)
                        continue

                # Non-retryable error or max retries reached
                raise MangaDexAPIError(
                    f"API request failed: {response.status_code}",
                    status_code=response.status_code,
                )

            except httpx.TimeoutException:
                if attempt < MAX_RETRIES - 1:
                    delay = RETRY_BASE_DELAY * (2**attempt)
                    logger.warning(
                        "Request timeout, retrying",
                        extra={"url": url, "attempt": attempt + 1, "delay": delay},
                    )
                    time.sleep(delay)
                    continue
                logger.error("Request timeout after all retries", extra={"url": url})
                raise

        # Should not reach here, but just in case
        raise MangaDexAPIError("Max retries exceeded")

    def get_trending_manga(self, limit: int = 20) -> list[dict]:
        """
        Get trending manga sorted by followed count.

        Args:
            limit: Maximum number of manga to return.

        Returns:
            List of raw manga data from API response.
        """
        logger.info("Fetching trending manga", extra={"limit": limit})

        params = {
            "order[followedCount]": "desc",
            "limit": limit,
            "includes[]": "cover_art",
        }

        response = self._request("GET", "/manga", params=params)
        manga_list = response.get("data", [])

        logger.info("Trending manga fetched", extra={"count": len(manga_list)})
        return manga_list

    def get_manga_details(self, manga_id: str) -> MangaInfo:
        """
        Get detailed manga information.

        Args:
            manga_id: MangaDex manga ID.

        Returns:
            Parsed MangaInfo object.
        """
        logger.info("Fetching manga details", extra={"manga_id": manga_id})

        params = {"includes[]": "cover_art"}
        response = self._request("GET", f"/manga/{manga_id}", params=params)
        manga_data = response.get("data", {})

        return self._parse_manga_info(manga_data)

    def _parse_manga_info(self, manga_data: dict) -> MangaInfo:
        """Parse raw manga data into MangaInfo model."""
        attributes = manga_data.get("attributes", {})
        relationships = manga_data.get("relationships", [])

        # Parse title (prefer English, fallback to first available)
        titles = attributes.get("title", {})
        title = titles.get("en") or titles.get("ja-ro") or next(iter(titles.values()), "")

        # Parse description (prefer Vietnamese, fallback English)
        descriptions = attributes.get("description", {})
        description = descriptions.get("vi") or descriptions.get("en") or ""

        # Parse genres from tags
        tags = attributes.get("tags", [])
        genres = [
            tag.get("attributes", {}).get("name", {}).get("en", "")
            for tag in tags
            if tag.get("type") == "tag"
        ]
        genres = [g for g in genres if g]  # Filter empty strings

        # Parse cover art URL
        cover_url = None
        for rel in relationships:
            if rel.get("type") == "cover_art":
                cover_filename = rel.get("attributes", {}).get("fileName")
                if cover_filename:
                    cover_url = (
                        f"https://uploads.mangadex.org/covers/"
                        f"{manga_data.get('id')}/{cover_filename}"
                    )
                break

        return MangaInfo(
            manga_id=manga_data.get("id", ""),
            title=title,
            description=description,
            genres=genres,
            cover_url=cover_url,
            chapters=[],  # Chapters fetched separately
        )

    def get_chapters(
        self, manga_id: str, languages: list[str] | None = None
    ) -> list[ChapterInfo]:
        """
        Get all chapters for a manga with pagination.

        Args:
            manga_id: MangaDex manga ID.
            languages: Preferred languages (default: ["vi", "en"]).

        Returns:
            List of ChapterInfo objects.
        """
        if languages is None:
            languages = ["vi", "en"]

        logger.info(
            "Fetching chapters",
            extra={"manga_id": manga_id, "languages": languages},
        )

        all_chapters: list[dict] = []
        offset = 0

        while True:
            params: dict[str, Any] = {
                "translatedLanguage[]": languages,
                "order[chapter]": "asc",
                "limit": CHAPTERS_PER_PAGE,
                "offset": offset,
            }

            response = self._request("GET", f"/manga/{manga_id}/feed", params=params)
            chapters = response.get("data", [])
            total = response.get("total", 0)

            all_chapters.extend(chapters)

            logger.debug(
                "Fetched chapter page",
                extra={
                    "manga_id": manga_id,
                    "offset": offset,
                    "fetched": len(chapters),
                    "total": total,
                },
            )

            offset += CHAPTERS_PER_PAGE
            if offset >= total or not chapters:
                break

        # Prefer Vietnamese chapters, group by chapter number
        chapter_map: dict[str | None, dict] = {}
        for ch in all_chapters:
            ch_num = ch.get("attributes", {}).get("chapter")
            ch_lang = ch.get("attributes", {}).get("translatedLanguage")

            # Prefer Vietnamese over English
            if ch_num not in chapter_map:
                chapter_map[ch_num] = ch
            elif ch_lang == "vi" and chapter_map[ch_num].get("attributes", {}).get(
                "translatedLanguage"
            ) != "vi":
                chapter_map[ch_num] = ch

        # Parse into ChapterInfo objects
        parsed_chapters = []
        for ch_data in chapter_map.values():
            attrs = ch_data.get("attributes", {})
            parsed_chapters.append(
                ChapterInfo(
                    chapter_id=ch_data.get("id", ""),
                    title=attrs.get("title") or f"Chapter {attrs.get('chapter', '?')}",
                    chapter_number=attrs.get("chapter"),
                    page_urls=[],  # Fetched separately via get_chapter_pages
                )
            )

        # Sort by chapter number
        parsed_chapters.sort(
            key=lambda c: (
                float(c.chapter_number) if c.chapter_number else float("inf")
            )
        )

        logger.info(
            "Chapters fetched",
            extra={"manga_id": manga_id, "count": len(parsed_chapters)},
        )
        return parsed_chapters

    def get_chapter_pages(self, chapter_id: str) -> list[str]:
        """
        Get page URLs for a chapter.

        Args:
            chapter_id: MangaDex chapter ID.

        Returns:
            List of full page image URLs.
        """
        logger.info("Fetching chapter pages", extra={"chapter_id": chapter_id})

        response = self._request("GET", f"/at-home/server/{chapter_id}")

        base_url = response.get("baseUrl", "")
        chapter_data = response.get("chapter", {})
        chapter_hash = chapter_data.get("hash", "")
        data_filenames = chapter_data.get("data", [])

        # Build full URLs
        page_urls = [
            f"{base_url}/data/{chapter_hash}/{filename}" for filename in data_filenames
        ]

        logger.info(
            "Chapter pages fetched",
            extra={"chapter_id": chapter_id, "page_count": len(page_urls)},
        )
        return page_urls

    def is_hentai(self, manga_data: dict) -> bool:
        """
        Check if manga is hentai/adult content.

        Args:
            manga_data: Raw manga data dict from API.

        Returns:
            True if manga is hentai, False otherwise.
        """
        attributes = manga_data.get("attributes", {})

        # Check content rating
        content_rating = attributes.get("contentRating", "")
        if content_rating == "pornographic":
            return True

        # Check tags for "Hentai" tag
        tags = attributes.get("tags", [])
        for tag in tags:
            tag_name = tag.get("attributes", {}).get("name", {}).get("en", "").lower()
            if tag_name == "hentai":
                return True

        return False
