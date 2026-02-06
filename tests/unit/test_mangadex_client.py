"""Tests for MangaDex API client."""

from unittest.mock import MagicMock, patch

import httpx
import pytest

from src.common.models import ChapterInfo, MangaInfo
from src.fetcher.mangadex_client import (
    MangaDexAPIError,
    MangaDexClient,
    RateLimiter,
)


@pytest.fixture
def client() -> MangaDexClient:
    """Create a MangaDex client for testing."""
    return MangaDexClient(base_url="https://api.mangadex.org", timeout=30)


@pytest.fixture
def sample_manga_data() -> dict:
    """Sample manga data from API."""
    return {
        "id": "manga-123",
        "type": "manga",
        "attributes": {
            "title": {"en": "One Piece", "ja": "ワンピース"},
            "description": {
                "en": "A pirate adventure story",
                "vi": "Câu chuyện phiêu lưu cướp biển",
            },
            "contentRating": "safe",
            "tags": [
                {
                    "type": "tag",
                    "attributes": {"name": {"en": "Action"}},
                },
                {
                    "type": "tag",
                    "attributes": {"name": {"en": "Adventure"}},
                },
            ],
        },
        "relationships": [
            {
                "type": "cover_art",
                "attributes": {"fileName": "cover.jpg"},
            }
        ],
    }


@pytest.fixture
def sample_hentai_manga_data() -> dict:
    """Sample hentai manga data from API."""
    return {
        "id": "manga-hentai",
        "type": "manga",
        "attributes": {
            "title": {"en": "Adult Manga"},
            "description": {"en": "Adult content"},
            "contentRating": "pornographic",
            "tags": [
                {
                    "type": "tag",
                    "attributes": {"name": {"en": "Hentai"}},
                }
            ],
        },
        "relationships": [],
    }


@pytest.fixture
def sample_chapter_data() -> list[dict]:
    """Sample chapter data from API."""
    return [
        {
            "id": "ch-001",
            "type": "chapter",
            "attributes": {
                "chapter": "1",
                "title": "Romance Dawn",
                "translatedLanguage": "vi",
            },
        },
        {
            "id": "ch-002",
            "type": "chapter",
            "attributes": {
                "chapter": "2",
                "title": "The Man in the Straw Hat",
                "translatedLanguage": "en",
            },
        },
        {
            "id": "ch-003",
            "type": "chapter",
            "attributes": {
                "chapter": "2",
                "title": "Chapter 2 Vietnamese",
                "translatedLanguage": "vi",
            },
        },
    ]


class TestGetTrendingManga:
    """Tests for get_trending_manga method."""

    def test_trending_manga_returns_parsed_list(self, client: MangaDexClient) -> None:
        """Test that trending manga returns parsed list."""
        mock_response = {
            "data": [
                {"id": "manga-1", "attributes": {"title": {"en": "Manga 1"}}},
                {"id": "manga-2", "attributes": {"title": {"en": "Manga 2"}}},
            ]
        }

        with patch.object(client._client, "request") as mock_request:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = mock_response
            mock_request.return_value = mock_resp

            result = client.get_trending_manga(limit=10)

        assert len(result) == 2
        assert result[0]["id"] == "manga-1"
        assert result[1]["id"] == "manga-2"

    def test_trending_manga_uses_correct_params(self, client: MangaDexClient) -> None:
        """Test that correct parameters are sent to API."""
        mock_response = {"data": []}

        with patch.object(client._client, "request") as mock_request:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = mock_response
            mock_request.return_value = mock_resp

            client.get_trending_manga(limit=15)

        mock_request.assert_called_once()
        call_kwargs = mock_request.call_args
        params = call_kwargs.kwargs.get("params") or call_kwargs[1].get("params")
        assert params["order[followedCount]"] == "desc"
        assert params["limit"] == 15
        assert params["includes[]"] == "cover_art"


class TestHentaiFilter:
    """Tests for is_hentai method."""

    def test_hentai_by_content_rating(
        self, client: MangaDexClient, sample_hentai_manga_data: dict
    ) -> None:
        """Test hentai detection by content rating."""
        assert client.is_hentai(sample_hentai_manga_data) is True

    def test_hentai_by_tag(self, client: MangaDexClient) -> None:
        """Test hentai detection by tag."""
        manga_data = {
            "attributes": {
                "contentRating": "suggestive",
                "tags": [
                    {"type": "tag", "attributes": {"name": {"en": "Hentai"}}}
                ],
            }
        }
        assert client.is_hentai(manga_data) is True

    def test_non_hentai_manga(
        self, client: MangaDexClient, sample_manga_data: dict
    ) -> None:
        """Test non-hentai manga detection."""
        assert client.is_hentai(sample_manga_data) is False

    def test_safe_content_rating(self, client: MangaDexClient) -> None:
        """Test safe content rating is not hentai."""
        manga_data = {
            "attributes": {
                "contentRating": "safe",
                "tags": [],
            }
        }
        assert client.is_hentai(manga_data) is False

    def test_case_insensitive_tag_check(self, client: MangaDexClient) -> None:
        """Test that hentai tag check is case insensitive."""
        manga_data = {
            "attributes": {
                "contentRating": "suggestive",
                "tags": [
                    {"type": "tag", "attributes": {"name": {"en": "HENTAI"}}}
                ],
            }
        }
        assert client.is_hentai(manga_data) is True


class TestChapterPagination:
    """Tests for chapter pagination."""

    def test_chapter_pagination_works(
        self, client: MangaDexClient, sample_chapter_data: list[dict]
    ) -> None:
        """Test that chapter pagination works with 2 pages."""
        page1_response = {
            "data": sample_chapter_data[:2],
            "total": 3,
        }
        page2_response = {
            "data": sample_chapter_data[2:],
            "total": 3,
        }

        call_count = 0

        def mock_request(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            if call_count == 1:
                mock_resp.json.return_value = page1_response
            else:
                mock_resp.json.return_value = page2_response
            return mock_resp

        with patch.object(client._client, "request", side_effect=mock_request):
            # Override pagination size for testing
            with patch(
                "src.fetcher.mangadex_client.CHAPTERS_PER_PAGE", 2
            ):
                result = client.get_chapters("manga-123")

        # Should have 2 unique chapters (ch 1 and ch 2, with vi preferred for ch 2)
        assert len(result) == 2
        assert all(isinstance(ch, ChapterInfo) for ch in result)

    def test_vietnamese_chapters_preferred(
        self, client: MangaDexClient, sample_chapter_data: list[dict]
    ) -> None:
        """Test that Vietnamese chapters are preferred over English."""
        response = {
            "data": sample_chapter_data,
            "total": 3,
        }

        with patch.object(client._client, "request") as mock_request:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = response
            mock_request.return_value = mock_resp

            result = client.get_chapters("manga-123")

        # Chapter 2 should be the Vietnamese version
        ch2 = next((ch for ch in result if ch.chapter_number == "2"), None)
        assert ch2 is not None
        assert ch2.chapter_id == "ch-003"  # Vietnamese version


class TestPageUrlConstruction:
    """Tests for page URL construction."""

    def test_page_url_construction_is_correct(self, client: MangaDexClient) -> None:
        """Test that page URLs are correctly constructed."""
        response = {
            "baseUrl": "https://uploads.mangadex.org",
            "chapter": {
                "hash": "abc123hash",
                "data": ["page1.jpg", "page2.jpg", "page3.jpg"],
            },
        }

        with patch.object(client._client, "request") as mock_request:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = response
            mock_request.return_value = mock_resp

            result = client.get_chapter_pages("ch-001")

        assert len(result) == 3
        assert result[0] == "https://uploads.mangadex.org/data/abc123hash/page1.jpg"
        assert result[1] == "https://uploads.mangadex.org/data/abc123hash/page2.jpg"
        assert result[2] == "https://uploads.mangadex.org/data/abc123hash/page3.jpg"

    def test_empty_pages_returns_empty_list(self, client: MangaDexClient) -> None:
        """Test that empty pages returns empty list."""
        response = {
            "baseUrl": "https://uploads.mangadex.org",
            "chapter": {
                "hash": "abc123",
                "data": [],
            },
        }

        with patch.object(client._client, "request") as mock_request:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = response
            mock_request.return_value = mock_resp

            result = client.get_chapter_pages("ch-001")

        assert result == []


class TestRetryLogic:
    """Tests for retry on errors."""

    def test_retry_on_429_response(self, client: MangaDexClient) -> None:
        """Test that 429 responses trigger retry."""
        call_count = 0

        def mock_request(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            mock_resp = MagicMock()
            if call_count < 3:
                mock_resp.status_code = 429
            else:
                mock_resp.status_code = 200
                mock_resp.json.return_value = {"data": []}
            return mock_resp

        with patch.object(client._client, "request", side_effect=mock_request):
            with patch("src.fetcher.mangadex_client.time.sleep"):
                result = client.get_trending_manga()

        assert call_count == 3
        assert result == []

    def test_retry_on_500_response(self, client: MangaDexClient) -> None:
        """Test that 500 responses trigger retry."""
        call_count = 0

        def mock_request(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            mock_resp = MagicMock()
            if call_count < 2:
                mock_resp.status_code = 500
            else:
                mock_resp.status_code = 200
                mock_resp.json.return_value = {"data": []}
            return mock_resp

        with patch.object(client._client, "request", side_effect=mock_request):
            with patch("src.fetcher.mangadex_client.time.sleep"):
                result = client.get_trending_manga()

        assert call_count == 2
        assert result == []

    def test_max_retries_exceeded_raises_error(self, client: MangaDexClient) -> None:
        """Test that max retries exceeded raises error."""
        with patch.object(client._client, "request") as mock_request:
            mock_resp = MagicMock()
            mock_resp.status_code = 500
            mock_request.return_value = mock_resp

            with patch("src.fetcher.mangadex_client.time.sleep"):
                with pytest.raises(MangaDexAPIError) as exc_info:
                    client.get_trending_manga()

        assert exc_info.value.status_code == 500


class TestTimeoutHandling:
    """Tests for timeout handling."""

    def test_timeout_triggers_retry(self, client: MangaDexClient) -> None:
        """Test that timeout triggers retry."""
        call_count = 0

        def mock_request(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise httpx.TimeoutException("timeout")
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = {"data": []}
            return mock_resp

        with patch.object(client._client, "request", side_effect=mock_request):
            with patch("src.fetcher.mangadex_client.time.sleep"):
                result = client.get_trending_manga()

        assert call_count == 3
        assert result == []

    def test_timeout_after_all_retries_raises(self, client: MangaDexClient) -> None:
        """Test that timeout after all retries raises exception."""
        with patch.object(client._client, "request") as mock_request:
            mock_request.side_effect = httpx.TimeoutException("timeout")

            with patch("src.fetcher.mangadex_client.time.sleep"):
                with pytest.raises(httpx.TimeoutException):
                    client.get_trending_manga()


class TestMangaDetails:
    """Tests for get_manga_details method."""

    def test_parse_manga_details(
        self, client: MangaDexClient, sample_manga_data: dict
    ) -> None:
        """Test parsing manga details."""
        response = {"data": sample_manga_data}

        with patch.object(client._client, "request") as mock_request:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = response
            mock_request.return_value = mock_resp

            result = client.get_manga_details("manga-123")

        assert isinstance(result, MangaInfo)
        assert result.manga_id == "manga-123"
        assert result.title == "One Piece"
        # Vietnamese description preferred
        assert result.description == "Câu chuyện phiêu lưu cướp biển"
        assert "Action" in result.genres
        assert "Adventure" in result.genres
        assert result.cover_url == (
            "https://uploads.mangadex.org/covers/manga-123/cover.jpg"
        )

    def test_parse_manga_fallback_title(self, client: MangaDexClient) -> None:
        """Test fallback to ja-ro title when English not available."""
        manga_data = {
            "id": "manga-jp",
            "attributes": {
                "title": {"ja-ro": "Wan Piisu"},
                "description": {},
                "tags": [],
            },
            "relationships": [],
        }
        response = {"data": manga_data}

        with patch.object(client._client, "request") as mock_request:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = response
            mock_request.return_value = mock_resp

            result = client.get_manga_details("manga-jp")

        assert result.title == "Wan Piisu"


class TestRateLimiter:
    """Tests for rate limiter."""

    def test_rate_limiter_waits(self) -> None:
        """Test that rate limiter waits between calls."""
        limiter = RateLimiter(min_interval=0.1)

        with patch("src.fetcher.mangadex_client.time.sleep") as mock_sleep:
            with patch("src.fetcher.mangadex_client.time.time") as mock_time:
                # First call at t=0
                mock_time.return_value = 0
                limiter.wait()

                # Second call at t=0.05 (should wait)
                mock_time.return_value = 0.05
                limiter._last_request_time = 0
                limiter.wait()

                # Should have slept for 0.05 seconds
                mock_sleep.assert_called()

    def test_rate_limiter_no_wait_if_enough_time(self) -> None:
        """Test that rate limiter doesn't wait if enough time has passed."""
        limiter = RateLimiter(min_interval=0.1)
        limiter._last_request_time = 0

        with patch("src.fetcher.mangadex_client.time.sleep") as mock_sleep:
            with patch("src.fetcher.mangadex_client.time.time") as mock_time:
                # Call at t=0.2 (after min_interval)
                mock_time.return_value = 0.2
                limiter.wait()

                mock_sleep.assert_not_called()


class TestClientLifecycle:
    """Tests for client lifecycle management."""

    def test_context_manager(self) -> None:
        """Test client works as context manager."""
        with MangaDexClient(base_url="https://api.mangadex.org") as client:
            assert client._client is not None

    def test_close_method(self) -> None:
        """Test close method closes HTTP client."""
        client = MangaDexClient(base_url="https://api.mangadex.org")
        with patch.object(client._client, "close") as mock_close:
            client.close()
            mock_close.assert_called_once()
