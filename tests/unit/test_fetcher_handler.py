"""Tests for fetcher Lambda handler."""

from unittest.mock import MagicMock, patch

import pytest

from src.common.models import ChapterInfo, JobStatus, MangaInfo
from src.fetcher.handler import handler


@pytest.fixture
def mock_settings():
    """Create mock settings."""
    settings = MagicMock()
    settings.mangadex_base_url = "https://api.mangadex.org"
    settings.s3_bucket = "test-bucket"
    settings.dynamodb_table = "test-table"
    return settings


@pytest.fixture
def sample_trending_manga():
    """Sample trending manga data."""
    return [
        {
            "id": "manga-001",
            "type": "manga",
            "attributes": {
                "title": {"en": "Test Manga 1"},
                "contentRating": "safe",
                "tags": [],
            },
        },
        {
            "id": "manga-002",
            "type": "manga",
            "attributes": {
                "title": {"en": "Test Manga 2"},
                "contentRating": "safe",
                "tags": [],
            },
        },
    ]


@pytest.fixture
def sample_manga_info():
    """Sample MangaInfo object."""
    return MangaInfo(
        manga_id="manga-001",
        title="Test Manga 1",
        description="A test manga",
        genres=["Action", "Adventure"],
        cover_url="https://example.com/cover.jpg",
        chapters=[],
    )


@pytest.fixture
def sample_chapters():
    """Sample chapter list."""
    return [
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
    ]


@pytest.fixture
def sample_panel_manifest():
    """Sample panel manifest."""
    return {
        "job_id": "test-job-id",
        "manga_id": "manga-001",
        "manga_title": "Test Manga 1",
        "total_panels": 10,
        "chapters": [
            {
                "chapter_id": "ch-001",
                "chapter_number": "1",
                "panel_keys": ["jobs/test-job-id/panels/0000_0000.jpg"],
            }
        ],
    }


class TestHappyPath:
    """Tests for successful handler execution."""

    def test_handler_processes_manga_successfully(
        self,
        mock_settings,
        sample_trending_manga,
        sample_manga_info,
        sample_chapters,
        sample_panel_manifest,
    ):
        """Test that handler successfully processes manga."""
        with patch("src.fetcher.handler.get_settings") as mock_get_settings, \
             patch("src.fetcher.handler.DynamoDBClient") as mock_db_class, \
             patch("src.fetcher.handler.S3Client") as mock_s3_class, \
             patch("src.fetcher.handler.MangaDexClient") as mock_mangadex_class, \
             patch("src.fetcher.handler.PanelDownloader") as mock_downloader_class, \
             patch("src.fetcher.handler.uuid.uuid4") as mock_uuid:

            # Setup mocks
            mock_get_settings.return_value = mock_settings
            mock_uuid.side_effect = [
                MagicMock(__str__=lambda x: "correlation-id-123"),
                MagicMock(__str__=lambda x: "job-id-456"),
            ]

            mock_db = MagicMock()
            mock_db.is_manga_processed.return_value = False
            mock_db_class.return_value = mock_db

            mock_s3 = MagicMock()
            mock_s3_class.return_value = mock_s3

            mock_mangadex = MagicMock()
            mock_mangadex.get_trending_manga.return_value = sample_trending_manga
            mock_mangadex.is_hentai.return_value = False
            sample_manga_info.chapters = sample_chapters
            mock_mangadex.get_manga_details.return_value = sample_manga_info
            mock_mangadex.get_chapters.return_value = sample_chapters
            mock_mangadex_class.return_value = mock_mangadex

            mock_downloader = MagicMock()
            mock_downloader.download_manga_panels.return_value = sample_panel_manifest
            mock_downloader_class.return_value = mock_downloader

            # Execute handler
            result = handler({}, None)

            # Verify result
            assert result["job_id"] == "job-id-456"
            assert result["manga_id"] == "manga-001"
            assert result["manga_title"] == "Test Manga 1"
            assert result["panel_manifest_s3_key"] == "jobs/job-id-456/panel_manifest.json"

            # Verify calls
            mock_mangadex.get_trending_manga.assert_called_once_with(limit=20)
            mock_mangadex.get_manga_details.assert_called_once_with("manga-001")
            mock_mangadex.get_chapters.assert_called_once_with("manga-001")
            mock_db.create_job.assert_called_once()
            mock_db.update_job_status.assert_called_once_with(
                job_id="job-id-456",
                status=JobStatus.scripting,
                progress_pct=20,
            )
            mock_db.mark_manga_processed.assert_called_once_with(
                manga_id="manga-001",
                title="Test Manga 1",
            )
            mock_downloader.download_manga_panels.assert_called_once()

    def test_handler_skips_processed_manga(
        self,
        mock_settings,
        sample_trending_manga,
        sample_manga_info,
        sample_chapters,
        sample_panel_manifest,
    ):
        """Test that handler skips already processed manga."""
        with patch("src.fetcher.handler.get_settings") as mock_get_settings, \
             patch("src.fetcher.handler.DynamoDBClient") as mock_db_class, \
             patch("src.fetcher.handler.S3Client") as mock_s3_class, \
             patch("src.fetcher.handler.MangaDexClient") as mock_mangadex_class, \
             patch("src.fetcher.handler.PanelDownloader") as mock_downloader_class, \
             patch("src.fetcher.handler.uuid.uuid4") as mock_uuid:

            mock_get_settings.return_value = mock_settings
            mock_uuid.side_effect = [
                MagicMock(__str__=lambda x: "correlation-id-123"),
                MagicMock(__str__=lambda x: "job-id-456"),
            ]

            mock_db = MagicMock()
            # First manga is processed, second is not
            mock_db.is_manga_processed.side_effect = [True, False]
            mock_db_class.return_value = mock_db

            mock_s3 = MagicMock()
            mock_s3_class.return_value = mock_s3

            mock_mangadex = MagicMock()
            mock_mangadex.get_trending_manga.return_value = sample_trending_manga
            mock_mangadex.is_hentai.return_value = False
            sample_manga_info.manga_id = "manga-002"
            sample_manga_info.title = "Test Manga 2"
            sample_manga_info.chapters = sample_chapters
            mock_mangadex.get_manga_details.return_value = sample_manga_info
            mock_mangadex.get_chapters.return_value = sample_chapters
            mock_mangadex_class.return_value = mock_mangadex

            mock_downloader = MagicMock()
            mock_downloader.download_manga_panels.return_value = sample_panel_manifest
            mock_downloader_class.return_value = mock_downloader

            result = handler({}, None)

            # Should process second manga (manga-002)
            assert result["manga_id"] == "manga-002"
            mock_mangadex.get_manga_details.assert_called_once_with("manga-002")


class TestNoAvailableManga:
    """Tests for when no manga is available."""

    def test_all_manga_already_processed(self, mock_settings, sample_trending_manga):
        """Test that handler returns no_manga_available when all are processed."""
        with patch("src.fetcher.handler.get_settings") as mock_get_settings, \
             patch("src.fetcher.handler.DynamoDBClient") as mock_db_class, \
             patch("src.fetcher.handler.S3Client"), \
             patch("src.fetcher.handler.MangaDexClient") as mock_mangadex_class, \
             patch("src.fetcher.handler.PanelDownloader") as mock_downloader_class:

            mock_get_settings.return_value = mock_settings

            mock_db = MagicMock()
            mock_db.is_manga_processed.return_value = True  # All processed
            mock_db_class.return_value = mock_db

            mock_mangadex = MagicMock()
            mock_mangadex.get_trending_manga.return_value = sample_trending_manga
            mock_mangadex.is_hentai.return_value = False
            mock_mangadex_class.return_value = mock_mangadex

            mock_downloader = MagicMock()
            mock_downloader_class.return_value = mock_downloader

            result = handler({}, None)

            assert result == {"status": "no_manga_available"}
            mock_db.create_job.assert_not_called()
            mock_downloader.download_manga_panels.assert_not_called()

    def test_empty_trending_list(self, mock_settings):
        """Test that handler returns no_manga_available with empty trending."""
        with patch("src.fetcher.handler.get_settings") as mock_get_settings, \
             patch("src.fetcher.handler.DynamoDBClient") as mock_db_class, \
             patch("src.fetcher.handler.S3Client"), \
             patch("src.fetcher.handler.MangaDexClient") as mock_mangadex_class, \
             patch("src.fetcher.handler.PanelDownloader") as mock_downloader_class:

            mock_get_settings.return_value = mock_settings

            mock_db = MagicMock()
            mock_db_class.return_value = mock_db

            mock_mangadex = MagicMock()
            mock_mangadex.get_trending_manga.return_value = []  # Empty list
            mock_mangadex_class.return_value = mock_mangadex

            mock_downloader = MagicMock()
            mock_downloader_class.return_value = mock_downloader

            result = handler({}, None)

            assert result == {"status": "no_manga_available"}


class TestHentaiFiltering:
    """Tests for hentai content filtering."""

    def test_all_manga_are_hentai(self, mock_settings):
        """Test that handler returns no_manga_available when all are hentai."""
        hentai_manga = [
            {
                "id": "manga-h1",
                "type": "manga",
                "attributes": {
                    "title": {"en": "Hentai 1"},
                    "contentRating": "pornographic",
                    "tags": [],
                },
            },
            {
                "id": "manga-h2",
                "type": "manga",
                "attributes": {
                    "title": {"en": "Hentai 2"},
                    "contentRating": "pornographic",
                    "tags": [],
                },
            },
        ]

        with patch("src.fetcher.handler.get_settings") as mock_get_settings, \
             patch("src.fetcher.handler.DynamoDBClient") as mock_db_class, \
             patch("src.fetcher.handler.S3Client"), \
             patch("src.fetcher.handler.MangaDexClient") as mock_mangadex_class, \
             patch("src.fetcher.handler.PanelDownloader") as mock_downloader_class:

            mock_get_settings.return_value = mock_settings

            mock_db = MagicMock()
            mock_db_class.return_value = mock_db

            mock_mangadex = MagicMock()
            mock_mangadex.get_trending_manga.return_value = hentai_manga
            mock_mangadex.is_hentai.return_value = True  # All are hentai
            mock_mangadex_class.return_value = mock_mangadex

            mock_downloader = MagicMock()
            mock_downloader_class.return_value = mock_downloader

            result = handler({}, None)

            assert result == {"status": "no_manga_available"}
            mock_db.is_manga_processed.assert_not_called()  # Should skip before checking

    def test_hentai_skipped_non_hentai_processed(
        self,
        mock_settings,
        sample_manga_info,
        sample_chapters,
        sample_panel_manifest,
    ):
        """Test that hentai is skipped and non-hentai is processed."""
        mixed_manga = [
            {
                "id": "manga-h1",
                "type": "manga",
                "attributes": {
                    "title": {"en": "Hentai 1"},
                    "contentRating": "pornographic",
                    "tags": [],
                },
            },
            {
                "id": "manga-safe",
                "type": "manga",
                "attributes": {
                    "title": {"en": "Safe Manga"},
                    "contentRating": "safe",
                    "tags": [],
                },
            },
        ]

        with patch("src.fetcher.handler.get_settings") as mock_get_settings, \
             patch("src.fetcher.handler.DynamoDBClient") as mock_db_class, \
             patch("src.fetcher.handler.S3Client"), \
             patch("src.fetcher.handler.MangaDexClient") as mock_mangadex_class, \
             patch("src.fetcher.handler.PanelDownloader") as mock_downloader_class, \
             patch("src.fetcher.handler.uuid.uuid4") as mock_uuid:

            mock_get_settings.return_value = mock_settings
            mock_uuid.side_effect = [
                MagicMock(__str__=lambda x: "correlation-id"),
                MagicMock(__str__=lambda x: "job-id"),
            ]

            mock_db = MagicMock()
            mock_db.is_manga_processed.return_value = False
            mock_db_class.return_value = mock_db

            mock_mangadex = MagicMock()
            mock_mangadex.get_trending_manga.return_value = mixed_manga
            # First is hentai, second is not
            mock_mangadex.is_hentai.side_effect = [True, False]
            sample_manga_info.manga_id = "manga-safe"
            sample_manga_info.title = "Safe Manga"
            sample_manga_info.chapters = sample_chapters
            mock_mangadex.get_manga_details.return_value = sample_manga_info
            mock_mangadex.get_chapters.return_value = sample_chapters
            mock_mangadex_class.return_value = mock_mangadex

            mock_downloader = MagicMock()
            mock_downloader.download_manga_panels.return_value = sample_panel_manifest
            mock_downloader_class.return_value = mock_downloader

            result = handler({}, None)

            # Should process the safe manga
            assert result["manga_id"] == "manga-safe"
            mock_mangadex.get_manga_details.assert_called_once_with("manga-safe")


class TestNoChapters:
    """Tests for manga with no chapters."""

    def test_returns_no_chapters_available(
        self, mock_settings, sample_trending_manga, sample_manga_info
    ):
        """Test that handler returns no_chapters_available when manga has no chapters."""
        with patch("src.fetcher.handler.get_settings") as mock_get_settings, \
             patch("src.fetcher.handler.DynamoDBClient") as mock_db_class, \
             patch("src.fetcher.handler.S3Client"), \
             patch("src.fetcher.handler.MangaDexClient") as mock_mangadex_class, \
             patch("src.fetcher.handler.PanelDownloader") as mock_downloader_class:

            mock_get_settings.return_value = mock_settings

            mock_db = MagicMock()
            mock_db.is_manga_processed.return_value = False
            mock_db_class.return_value = mock_db

            mock_mangadex = MagicMock()
            mock_mangadex.get_trending_manga.return_value = sample_trending_manga
            mock_mangadex.is_hentai.return_value = False
            sample_manga_info.chapters = []
            mock_mangadex.get_manga_details.return_value = sample_manga_info
            mock_mangadex.get_chapters.return_value = []  # No chapters
            mock_mangadex_class.return_value = mock_mangadex

            mock_downloader = MagicMock()
            mock_downloader_class.return_value = mock_downloader

            result = handler({}, None)

            assert result == {"status": "no_chapters_available", "manga_id": "manga-001"}
            mock_db.create_job.assert_not_called()


class TestErrorHandling:
    """Tests for error handling."""

    def test_mangadex_api_error_before_job_creation(self, mock_settings):
        """Test that API error before job creation doesn't update job status."""
        with patch("src.fetcher.handler.get_settings") as mock_get_settings, \
             patch("src.fetcher.handler.DynamoDBClient") as mock_db_class, \
             patch("src.fetcher.handler.S3Client"), \
             patch("src.fetcher.handler.MangaDexClient") as mock_mangadex_class, \
             patch("src.fetcher.handler.PanelDownloader") as mock_downloader_class:

            mock_get_settings.return_value = mock_settings

            mock_db = MagicMock()
            mock_db_class.return_value = mock_db

            mock_mangadex = MagicMock()
            mock_mangadex.get_trending_manga.side_effect = Exception("API Error")
            mock_mangadex_class.return_value = mock_mangadex

            mock_downloader = MagicMock()
            mock_downloader_class.return_value = mock_downloader

            with pytest.raises(Exception, match="API Error"):
                handler({}, None)

            # Job was never created, so update_job_status shouldn't be called
            mock_db.update_job_status.assert_not_called()

    def test_error_after_job_creation_marks_job_failed(
        self, mock_settings, sample_trending_manga, sample_manga_info, sample_chapters
    ):
        """Test that error after job creation marks job as failed."""
        with patch("src.fetcher.handler.get_settings") as mock_get_settings, \
             patch("src.fetcher.handler.DynamoDBClient") as mock_db_class, \
             patch("src.fetcher.handler.S3Client"), \
             patch("src.fetcher.handler.MangaDexClient") as mock_mangadex_class, \
             patch("src.fetcher.handler.PanelDownloader") as mock_downloader_class, \
             patch("src.fetcher.handler.uuid.uuid4") as mock_uuid:

            mock_get_settings.return_value = mock_settings
            mock_uuid.side_effect = [
                MagicMock(__str__=lambda x: "correlation-id"),
                MagicMock(__str__=lambda x: "job-id-123"),
            ]

            mock_db = MagicMock()
            mock_db.is_manga_processed.return_value = False
            mock_db_class.return_value = mock_db

            mock_mangadex = MagicMock()
            mock_mangadex.get_trending_manga.return_value = sample_trending_manga
            mock_mangadex.is_hentai.return_value = False
            sample_manga_info.chapters = sample_chapters
            mock_mangadex.get_manga_details.return_value = sample_manga_info
            mock_mangadex.get_chapters.return_value = sample_chapters
            mock_mangadex_class.return_value = mock_mangadex

            mock_downloader = MagicMock()
            mock_downloader.download_manga_panels.side_effect = Exception("Download failed")
            mock_downloader_class.return_value = mock_downloader

            with pytest.raises(Exception, match="Download failed"):
                handler({}, None)

            # Job was created, so status should be updated to failed
            mock_db.update_job_status.assert_called_with(
                job_id="job-id-123",
                status=JobStatus.failed,
                error_message="Download failed",
            )

    def test_error_updating_failed_status_is_logged(
        self, mock_settings, sample_trending_manga, sample_manga_info, sample_chapters
    ):
        """Test that error updating failed status doesn't raise additional exception."""
        with patch("src.fetcher.handler.get_settings") as mock_get_settings, \
             patch("src.fetcher.handler.DynamoDBClient") as mock_db_class, \
             patch("src.fetcher.handler.S3Client"), \
             patch("src.fetcher.handler.MangaDexClient") as mock_mangadex_class, \
             patch("src.fetcher.handler.PanelDownloader") as mock_downloader_class, \
             patch("src.fetcher.handler.uuid.uuid4") as mock_uuid:

            mock_get_settings.return_value = mock_settings
            mock_uuid.side_effect = [
                MagicMock(__str__=lambda x: "correlation-id"),
                MagicMock(__str__=lambda x: "job-id-123"),
            ]

            mock_db = MagicMock()
            mock_db.is_manga_processed.return_value = False
            mock_db.update_job_status.side_effect = Exception("DB error")
            mock_db_class.return_value = mock_db

            mock_mangadex = MagicMock()
            mock_mangadex.get_trending_manga.return_value = sample_trending_manga
            mock_mangadex.is_hentai.return_value = False
            sample_manga_info.chapters = sample_chapters
            mock_mangadex.get_manga_details.return_value = sample_manga_info
            mock_mangadex.get_chapters.return_value = sample_chapters
            mock_mangadex_class.return_value = mock_mangadex

            mock_downloader = MagicMock()
            mock_downloader.download_manga_panels.side_effect = Exception("Download failed")
            mock_downloader_class.return_value = mock_downloader

            # Should raise the original error, not the DB error
            with pytest.raises(Exception, match="Download failed"):
                handler({}, None)


class TestClientCleanup:
    """Tests for client cleanup in finally block."""

    def test_clients_closed_on_success(
        self,
        mock_settings,
        sample_trending_manga,
        sample_manga_info,
        sample_chapters,
        sample_panel_manifest,
    ):
        """Test that clients are closed after successful execution."""
        with patch("src.fetcher.handler.get_settings") as mock_get_settings, \
             patch("src.fetcher.handler.DynamoDBClient") as mock_db_class, \
             patch("src.fetcher.handler.S3Client"), \
             patch("src.fetcher.handler.MangaDexClient") as mock_mangadex_class, \
             patch("src.fetcher.handler.PanelDownloader") as mock_downloader_class, \
             patch("src.fetcher.handler.uuid.uuid4") as mock_uuid:

            mock_get_settings.return_value = mock_settings
            mock_uuid.side_effect = [
                MagicMock(__str__=lambda x: "correlation-id"),
                MagicMock(__str__=lambda x: "job-id"),
            ]

            mock_db = MagicMock()
            mock_db.is_manga_processed.return_value = False
            mock_db_class.return_value = mock_db

            mock_mangadex = MagicMock()
            mock_mangadex.get_trending_manga.return_value = sample_trending_manga
            mock_mangadex.is_hentai.return_value = False
            sample_manga_info.chapters = sample_chapters
            mock_mangadex.get_manga_details.return_value = sample_manga_info
            mock_mangadex.get_chapters.return_value = sample_chapters
            mock_mangadex_class.return_value = mock_mangadex

            mock_downloader = MagicMock()
            mock_downloader.download_manga_panels.return_value = sample_panel_manifest
            mock_downloader_class.return_value = mock_downloader

            handler({}, None)

            mock_mangadex.close.assert_called_once()
            mock_downloader.close.assert_called_once()

    def test_clients_closed_on_error(self, mock_settings):
        """Test that clients are closed even when error occurs."""
        with patch("src.fetcher.handler.get_settings") as mock_get_settings, \
             patch("src.fetcher.handler.DynamoDBClient") as mock_db_class, \
             patch("src.fetcher.handler.S3Client"), \
             patch("src.fetcher.handler.MangaDexClient") as mock_mangadex_class, \
             patch("src.fetcher.handler.PanelDownloader") as mock_downloader_class:

            mock_get_settings.return_value = mock_settings

            mock_db = MagicMock()
            mock_db_class.return_value = mock_db

            mock_mangadex = MagicMock()
            mock_mangadex.get_trending_manga.side_effect = Exception("API Error")
            mock_mangadex_class.return_value = mock_mangadex

            mock_downloader = MagicMock()
            mock_downloader_class.return_value = mock_downloader

            with pytest.raises(Exception, match="API Error"):
                handler({}, None)

            # Clients should still be closed
            mock_mangadex.close.assert_called_once()
            mock_downloader.close.assert_called_once()
