"""Tests for panel image downloader."""

from unittest.mock import MagicMock, patch

import httpx
import pytest

from src.common.models import ChapterInfo, MangaInfo
from src.fetcher.panel_downloader import (
    ImageDownloadError,
    PanelDownloader,
)


@pytest.fixture
def mock_mangadex_client() -> MagicMock:
    """Create a mock MangaDex client."""
    return MagicMock()


@pytest.fixture
def mock_s3_client() -> MagicMock:
    """Create a mock S3 client."""
    return MagicMock()


@pytest.fixture
def downloader(
    mock_mangadex_client: MagicMock,
    mock_s3_client: MagicMock,
) -> PanelDownloader:
    """Create a panel downloader for testing."""
    return PanelDownloader(
        mangadex_client=mock_mangadex_client,
        s3_client=mock_s3_client,
    )


@pytest.fixture
def sample_manga() -> MangaInfo:
    """Create sample manga info for testing."""
    return MangaInfo(
        manga_id="manga-123",
        title="Test Manga",
        description="A test manga",
        genres=["Action"],
        cover_url="https://example.com/cover.jpg",
        chapters=[
            ChapterInfo(
                chapter_id="ch-001",
                title="Chapter 1",
                chapter_number="1",
                page_urls=[],
            ),
            ChapterInfo(
                chapter_id="ch-002",
                title="Chapter 2",
                chapter_number="2",
                page_urls=[],
            ),
        ],
    )


@pytest.fixture
def sample_image_bytes() -> bytes:
    """Create sample JPEG image bytes."""
    # JPEG magic bytes + minimal data
    return b"\xff\xd8\xff\xe0\x00\x10JFIF" + b"\x00" * 100


@pytest.fixture
def sample_png_bytes() -> bytes:
    """Create sample PNG image bytes."""
    # PNG magic bytes + minimal data
    return b"\x89PNG\r\n\x1a\n" + b"\x00" * 100


class TestDownloadMangaPanels:
    """Tests for download_manga_panels method."""

    def test_downloads_and_uploads_panels_with_correct_keys(
        self,
        downloader: PanelDownloader,
        mock_mangadex_client: MagicMock,
        mock_s3_client: MagicMock,
        sample_manga: MangaInfo,
        sample_image_bytes: bytes,
    ) -> None:
        """Test that panels are downloaded and uploaded with correct S3 keys."""
        # Mock chapter pages
        mock_mangadex_client.get_chapter_pages.side_effect = [
            ["https://cdn.example.com/ch1/page1.jpg", "https://cdn.example.com/ch1/page2.jpg"],
            ["https://cdn.example.com/ch2/page1.png"],
        ]

        # Mock image downloads
        with patch.object(
            downloader._http_client, "get"
        ) as mock_get:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.headers = {"content-type": "image/jpeg"}
            mock_response.content = sample_image_bytes
            mock_get.return_value = mock_response

            with patch("src.fetcher.panel_downloader.time.sleep"):
                downloader.download_manga_panels(sample_manga, "job-123")

        # Verify S3 upload calls
        upload_calls = mock_s3_client.upload_bytes.call_args_list
        assert len(upload_calls) == 3

        # Check keys are zero-padded and ordered
        expected_keys = [
            "jobs/job-123/panels/0000_0000.jpg",
            "jobs/job-123/panels/0000_0001.jpg",
            "jobs/job-123/panels/0001_0000.png",
        ]
        actual_keys = [c[0][1] for c in upload_calls]
        assert actual_keys == expected_keys

        # Verify manifest was uploaded
        mock_s3_client.upload_json.assert_called_once()
        manifest_call = mock_s3_client.upload_json.call_args
        assert manifest_call[0][1] == "jobs/job-123/panel_manifest.json"

    def test_manifest_structure_is_correct(
        self,
        downloader: PanelDownloader,
        mock_mangadex_client: MagicMock,
        mock_s3_client: MagicMock,
        sample_manga: MangaInfo,
        sample_image_bytes: bytes,
    ) -> None:
        """Test that manifest has correct structure."""
        mock_mangadex_client.get_chapter_pages.side_effect = [
            ["https://cdn.example.com/page1.jpg"],
            ["https://cdn.example.com/page2.jpg", "https://cdn.example.com/page3.jpg"],
        ]

        with patch.object(downloader._http_client, "get") as mock_get:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.headers = {"content-type": "image/jpeg"}
            mock_response.content = sample_image_bytes
            mock_get.return_value = mock_response

            with patch("src.fetcher.panel_downloader.time.sleep"):
                result = downloader.download_manga_panels(sample_manga, "job-456")

        # Verify manifest structure
        assert result["job_id"] == "job-456"
        assert result["manga_id"] == "manga-123"
        assert result["manga_title"] == "Test Manga"
        assert result["total_panels"] == 3
        assert len(result["chapters"]) == 2

        # Verify chapter structure
        ch1 = result["chapters"][0]
        assert ch1["chapter_id"] == "ch-001"
        assert ch1["title"] == "Chapter 1"
        assert ch1["chapter_number"] == "1"
        assert len(ch1["panel_keys"]) == 1

        ch2 = result["chapters"][1]
        assert ch2["chapter_id"] == "ch-002"
        assert len(ch2["panel_keys"]) == 2

    def test_failed_image_is_skipped_with_warning(
        self,
        downloader: PanelDownloader,
        mock_mangadex_client: MagicMock,
        mock_s3_client: MagicMock,
        sample_manga: MangaInfo,
        sample_image_bytes: bytes,
    ) -> None:
        """Test that failed images are skipped and don't crash pipeline."""
        mock_mangadex_client.get_chapter_pages.side_effect = [
            [
                "https://cdn.example.com/page1.jpg",
                "https://cdn.example.com/page2.jpg",  # This will fail
                "https://cdn.example.com/page3.jpg",
            ],
            [],  # Empty chapter
        ]

        def mock_get_side_effect(url):
            mock_response = MagicMock()

            # page2.jpg always fails (simulates persistent failure)
            if "page2.jpg" in url:
                mock_response.status_code = 404
                return mock_response

            mock_response.status_code = 200
            mock_response.headers = {"content-type": "image/jpeg"}
            mock_response.content = sample_image_bytes
            return mock_response

        with patch.object(
            downloader._http_client, "get", side_effect=mock_get_side_effect
        ):
            with patch("src.fetcher.panel_downloader.time.sleep"):
                result = downloader.download_manga_panels(sample_manga, "job-789")

        # Should have 2 panels (page 1 and 3, skipping failed page 2)
        assert result["total_panels"] == 2
        assert len(result["chapters"]) == 1
        assert len(result["chapters"][0]["panel_keys"]) == 2

    def test_chapter_page_numbering_is_zero_padded_and_ordered(
        self,
        downloader: PanelDownloader,
        mock_mangadex_client: MagicMock,
        mock_s3_client: MagicMock,
        sample_image_bytes: bytes,
    ) -> None:
        """Test that chapter and page indices are zero-padded correctly."""
        # Create manga with many chapters
        chapters = [
            ChapterInfo(
                chapter_id=f"ch-{i:03d}",
                title=f"Chapter {i}",
                chapter_number=str(i),
                page_urls=[],
            )
            for i in range(15)
        ]
        manga = MangaInfo(
            manga_id="manga-big",
            title="Big Manga",
            description="",
            genres=[],
            cover_url=None,
            chapters=chapters,
        )

        # Each chapter has 1 page
        mock_mangadex_client.get_chapter_pages.return_value = [
            "https://cdn.example.com/page.jpg"
        ]

        with patch.object(downloader._http_client, "get") as mock_get:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.headers = {"content-type": "image/jpeg"}
            mock_response.content = sample_image_bytes
            mock_get.return_value = mock_response

            with patch("src.fetcher.panel_downloader.time.sleep"):
                downloader.download_manga_panels(manga, "job-big")

        # Verify zero-padding
        upload_calls = mock_s3_client.upload_bytes.call_args_list
        keys = [c[0][1] for c in upload_calls]

        assert "jobs/job-big/panels/0000_0000.jpg" in keys
        assert "jobs/job-big/panels/0009_0000.jpg" in keys
        assert "jobs/job-big/panels/0014_0000.jpg" in keys

    def test_empty_manga_chapters(
        self,
        downloader: PanelDownloader,
        mock_mangadex_client: MagicMock,
        mock_s3_client: MagicMock,
    ) -> None:
        """Test handling manga with no chapters."""
        manga = MangaInfo(
            manga_id="manga-empty",
            title="Empty Manga",
            description="",
            genres=[],
            cover_url=None,
            chapters=[],
        )

        with patch("src.fetcher.panel_downloader.time.sleep"):
            result = downloader.download_manga_panels(manga, "job-empty")

        assert result["total_panels"] == 0
        assert result["chapters"] == []
        mock_s3_client.upload_json.assert_called_once()


class TestDownloadSingleImage:
    """Tests for download_single_image method."""

    def test_successful_image_download(
        self,
        downloader: PanelDownloader,
        sample_image_bytes: bytes,
    ) -> None:
        """Test successful image download."""
        with patch.object(downloader._http_client, "get") as mock_get:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.headers = {"content-type": "image/jpeg"}
            mock_response.content = sample_image_bytes
            mock_get.return_value = mock_response

            with patch("src.fetcher.panel_downloader.time.sleep"):
                result = downloader.download_single_image("https://example.com/image.jpg")

        assert result == sample_image_bytes

    def test_retry_on_failure(
        self,
        downloader: PanelDownloader,
        sample_image_bytes: bytes,
    ) -> None:
        """Test that download retries on failure."""
        call_count = 0

        def mock_get_side_effect(url):
            nonlocal call_count
            call_count += 1
            mock_response = MagicMock()

            if call_count < 3:
                mock_response.status_code = 500
                return mock_response

            mock_response.status_code = 200
            mock_response.headers = {"content-type": "image/jpeg"}
            mock_response.content = sample_image_bytes
            return mock_response

        with patch.object(
            downloader._http_client, "get", side_effect=mock_get_side_effect
        ):
            with patch("src.fetcher.panel_downloader.time.sleep"):
                result = downloader.download_single_image("https://example.com/image.jpg")

        assert call_count == 3
        assert result == sample_image_bytes

    def test_max_retries_exceeded_raises_error(
        self,
        downloader: PanelDownloader,
    ) -> None:
        """Test that max retries exceeded raises ImageDownloadError."""
        with patch.object(downloader._http_client, "get") as mock_get:
            mock_response = MagicMock()
            mock_response.status_code = 500
            mock_get.return_value = mock_response

            with patch("src.fetcher.panel_downloader.time.sleep"):
                with pytest.raises(ImageDownloadError) as exc_info:
                    downloader.download_single_image("https://example.com/image.jpg")

        assert "Failed to download image" in str(exc_info.value)

    def test_validates_content_type(
        self,
        downloader: PanelDownloader,
        sample_image_bytes: bytes,
    ) -> None:
        """Test that content type is validated."""
        with patch.object(downloader._http_client, "get") as mock_get:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.headers = {"content-type": "text/html"}
            mock_response.content = b"<html>Not an image</html>"
            mock_get.return_value = mock_response

            with patch("src.fetcher.panel_downloader.time.sleep"):
                with pytest.raises(ImageDownloadError) as exc_info:
                    downloader.download_single_image("https://example.com/image.jpg")

        assert "Invalid content type" in str(exc_info.value)

    def test_accepts_valid_image_without_content_type(
        self,
        downloader: PanelDownloader,
        sample_png_bytes: bytes,
    ) -> None:
        """Test that valid image bytes are accepted even without proper content-type."""
        with patch.object(downloader._http_client, "get") as mock_get:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.headers = {"content-type": "application/octet-stream"}
            mock_response.content = sample_png_bytes
            mock_get.return_value = mock_response

            with patch("src.fetcher.panel_downloader.time.sleep"):
                result = downloader.download_single_image("https://example.com/image.png")

        assert result == sample_png_bytes

    def test_timeout_handling(
        self,
        downloader: PanelDownloader,
    ) -> None:
        """Test that timeouts are handled with retry."""
        with patch.object(downloader._http_client, "get") as mock_get:
            mock_get.side_effect = httpx.TimeoutException("timeout")

            with patch("src.fetcher.panel_downloader.time.sleep"):
                with pytest.raises(ImageDownloadError) as exc_info:
                    downloader.download_single_image("https://example.com/image.jpg")

        assert "Timeout" in str(exc_info.value)


class TestImageValidation:
    """Tests for image byte validation."""

    def test_validates_jpeg_magic_bytes(
        self,
        downloader: PanelDownloader,
    ) -> None:
        """Test JPEG magic bytes validation."""
        jpeg_bytes = b"\xff\xd8\xff\xe0" + b"\x00" * 100
        assert downloader._is_valid_image_bytes(jpeg_bytes) is True

    def test_validates_png_magic_bytes(
        self,
        downloader: PanelDownloader,
    ) -> None:
        """Test PNG magic bytes validation."""
        png_bytes = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
        assert downloader._is_valid_image_bytes(png_bytes) is True

    def test_validates_gif_magic_bytes(
        self,
        downloader: PanelDownloader,
    ) -> None:
        """Test GIF magic bytes validation."""
        gif87_bytes = b"GIF87a" + b"\x00" * 100
        gif89_bytes = b"GIF89a" + b"\x00" * 100
        assert downloader._is_valid_image_bytes(gif87_bytes) is True
        assert downloader._is_valid_image_bytes(gif89_bytes) is True

    def test_validates_webp_magic_bytes(
        self,
        downloader: PanelDownloader,
    ) -> None:
        """Test WebP magic bytes validation."""
        webp_bytes = b"RIFF\x00\x00\x00\x00WEBP" + b"\x00" * 100
        assert downloader._is_valid_image_bytes(webp_bytes) is True

    def test_rejects_invalid_bytes(
        self,
        downloader: PanelDownloader,
    ) -> None:
        """Test rejection of invalid image bytes."""
        invalid_bytes = b"<html>Not an image</html>"
        assert downloader._is_valid_image_bytes(invalid_bytes) is False

    def test_rejects_too_short_bytes(
        self,
        downloader: PanelDownloader,
    ) -> None:
        """Test rejection of bytes too short to be an image."""
        assert downloader._is_valid_image_bytes(b"") is False
        assert downloader._is_valid_image_bytes(b"\xff\xd8") is False


class TestFileExtension:
    """Tests for file extension extraction."""

    def test_extracts_jpg_extension(
        self,
        downloader: PanelDownloader,
    ) -> None:
        """Test extraction of jpg extension."""
        assert downloader._get_extension_from_url(
            "https://example.com/page.jpg"
        ) == "jpg"

    def test_extracts_png_extension(
        self,
        downloader: PanelDownloader,
    ) -> None:
        """Test extraction of png extension."""
        assert downloader._get_extension_from_url(
            "https://example.com/page.png"
        ) == "png"

    def test_normalizes_jpeg_to_jpg(
        self,
        downloader: PanelDownloader,
    ) -> None:
        """Test that jpeg is normalized to jpg."""
        assert downloader._get_extension_from_url(
            "https://example.com/page.jpeg"
        ) == "jpg"

    def test_handles_query_params(
        self,
        downloader: PanelDownloader,
    ) -> None:
        """Test handling URLs with query parameters."""
        assert downloader._get_extension_from_url(
            "https://example.com/page.png?token=abc123"
        ) == "png"

    def test_defaults_to_jpg(
        self,
        downloader: PanelDownloader,
    ) -> None:
        """Test default to jpg when extension unknown."""
        assert downloader._get_extension_from_url(
            "https://example.com/page"
        ) == "jpg"


class TestClientLifecycle:
    """Tests for client lifecycle management."""

    def test_context_manager(
        self,
        mock_mangadex_client: MagicMock,
        mock_s3_client: MagicMock,
    ) -> None:
        """Test downloader works as context manager."""
        with PanelDownloader(mock_mangadex_client, mock_s3_client) as downloader:
            assert downloader._http_client is not None

    def test_close_method(
        self,
        downloader: PanelDownloader,
    ) -> None:
        """Test close method closes HTTP client."""
        with patch.object(downloader._http_client, "close") as mock_close:
            downloader.close()
            mock_close.assert_called_once()
