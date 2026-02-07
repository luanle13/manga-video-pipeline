"""Panel image downloader for fetching chapter pages and storing in S3."""

import time
from typing import Any

import httpx

from src.common.logging_config import setup_logger
from src.common.models import MangaInfo
from src.common.storage import S3Client
from src.fetcher.mangadex_client import MangaDexClient

logger = setup_logger(__name__)

# Rate limiting for image downloads (respect MangaDex at-home server)
IMAGE_DOWNLOAD_INTERVAL = 0.5  # 500ms between image downloads
MAX_IMAGE_RETRIES = 3
RETRY_BASE_DELAY = 1  # seconds

# Valid image content types
VALID_IMAGE_TYPES = {
    "image/jpeg",
    "image/jpg",
    "image/png",
    "image/gif",
    "image/webp",
}


class ImageDownloadError(Exception):
    """Raised when image download fails."""

    pass


class PanelDownloader:
    """Downloads manga panel images and stores them in S3."""

    def __init__(
        self,
        mangadex_client: MangaDexClient,
        s3_client: S3Client,
    ) -> None:
        """
        Initialize the panel downloader.

        Args:
            mangadex_client: Client for MangaDex API.
            s3_client: Client for S3 operations.
        """
        self._mangadex = mangadex_client
        self._s3 = s3_client
        self._http_client = httpx.Client(timeout=30)
        self._last_download_time: float = 0

        logger.info("Panel downloader initialized")

    def close(self) -> None:
        """Close the HTTP client."""
        self._http_client.close()

    def __enter__(self) -> "PanelDownloader":
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()

    def _wait_for_rate_limit(self) -> None:
        """Wait if necessary to respect rate limit."""
        now = time.time()
        elapsed = now - self._last_download_time
        if elapsed < IMAGE_DOWNLOAD_INTERVAL:
            sleep_time = IMAGE_DOWNLOAD_INTERVAL - elapsed
            time.sleep(sleep_time)
        self._last_download_time = time.time()

    def download_single_image(self, url: str) -> bytes:
        """
        Download a single image with retry logic.

        Args:
            url: URL of the image to download.

        Returns:
            Image bytes.

        Raises:
            ImageDownloadError: If download fails after all retries.
        """
        for attempt in range(MAX_IMAGE_RETRIES):
            self._wait_for_rate_limit()

            try:
                logger.debug(
                    "Downloading image",
                    extra={"url": url, "attempt": attempt + 1},
                )

                response = self._http_client.get(url)

                if response.status_code != 200:
                    if attempt < MAX_IMAGE_RETRIES - 1:
                        delay = RETRY_BASE_DELAY * (2**attempt)
                        logger.warning(
                            "Image download failed, retrying",
                            extra={
                                "url": url,
                                "status_code": response.status_code,
                                "attempt": attempt + 1,
                                "delay": delay,
                            },
                        )
                        time.sleep(delay)
                        continue
                    raise ImageDownloadError(
                        f"Failed to download image: {response.status_code}"
                    )

                # Validate content type
                content_type = response.headers.get("content-type", "").lower()
                # Handle content types with charset or other parameters
                content_type_base = content_type.split(";")[0].strip()

                if content_type_base not in VALID_IMAGE_TYPES:
                    # Some servers don't set proper content-type, check magic bytes
                    data = response.content
                    if not self._is_valid_image_bytes(data):
                        raise ImageDownloadError(
                            f"Invalid content type: {content_type}"
                        )
                    return data

                return response.content

            except httpx.TimeoutException as e:
                if attempt < MAX_IMAGE_RETRIES - 1:
                    delay = RETRY_BASE_DELAY * (2**attempt)
                    logger.warning(
                        "Image download timeout, retrying",
                        extra={"url": url, "attempt": attempt + 1, "delay": delay},
                    )
                    time.sleep(delay)
                    continue
                raise ImageDownloadError(f"Timeout downloading image: {url}") from e

            except httpx.RequestError as e:
                if attempt < MAX_IMAGE_RETRIES - 1:
                    delay = RETRY_BASE_DELAY * (2**attempt)
                    logger.warning(
                        "Image download error, retrying",
                        extra={
                            "url": url,
                            "error": str(e),
                            "attempt": attempt + 1,
                            "delay": delay,
                        },
                    )
                    time.sleep(delay)
                    continue
                raise ImageDownloadError(f"Error downloading image: {e}") from e

        raise ImageDownloadError(f"Max retries exceeded for image: {url}")

    def _is_valid_image_bytes(self, data: bytes) -> bool:
        """Check if bytes represent a valid image by checking magic bytes."""
        if len(data) < 8:
            return False

        # JPEG
        if data[:2] == b"\xff\xd8":
            return True
        # PNG
        if data[:8] == b"\x89PNG\r\n\x1a\n":
            return True
        # GIF
        if data[:6] in (b"GIF87a", b"GIF89a"):
            return True
        # WebP
        if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
            return True

        return False

    def download_manga_panels(
        self,
        manga: MangaInfo,
        job_id: str,
    ) -> dict:
        """
        Download all panels for a manga and store in S3.

        Args:
            manga: Manga info with chapters.
            job_id: Job ID for S3 path organization.

        Returns:
            Panel manifest with job_id, total_panels, and chapters info.
        """
        logger.info(
            "Starting panel download",
            extra={
                "job_id": job_id,
                "manga_id": manga.manga_id,
                "chapter_count": len(manga.chapters),
            },
        )

        manifest: dict[str, Any] = {
            "job_id": job_id,
            "manga_id": manga.manga_id,
            "manga_title": manga.title,
            "total_panels": 0,
            "chapters": [],
        }

        total_chapters = len(manga.chapters)

        for chapter_idx, chapter in enumerate(manga.chapters):
            logger.info(
                f"Downloading chapter {chapter_idx + 1}/{total_chapters}",
                extra={
                    "job_id": job_id,
                    "chapter_id": chapter.chapter_id,
                    "chapter_number": chapter.chapter_number,
                },
            )

            # Fetch page URLs for this chapter
            try:
                page_urls = self._mangadex.get_chapter_pages(chapter.chapter_id)
            except Exception as e:
                logger.error(
                    "Failed to get chapter pages, skipping chapter",
                    extra={
                        "chapter_id": chapter.chapter_id,
                        "error": str(e),
                    },
                )
                continue

            chapter_manifest: dict[str, Any] = {
                "chapter_id": chapter.chapter_id,
                "chapter_number": chapter.chapter_number,
                "title": chapter.title,
                "panel_keys": [],
            }

            total_pages = len(page_urls)

            for page_idx, page_url in enumerate(page_urls):
                logger.info(
                    f"Downloading chapter {chapter_idx + 1}/{total_chapters}, "
                    f"page {page_idx + 1}/{total_pages}",
                    extra={
                        "job_id": job_id,
                        "chapter_idx": chapter_idx,
                        "page_idx": page_idx,
                    },
                )

                try:
                    # Download image
                    image_data = self.download_single_image(page_url)

                    # Determine file extension from URL or default to jpg
                    extension = self._get_extension_from_url(page_url)

                    # Generate S3 key with zero-padded indices
                    s3_key = (
                        f"jobs/{job_id}/panels/"
                        f"{chapter_idx:04d}_{page_idx:04d}.{extension}"
                    )

                    # Upload to S3
                    content_type = self._get_content_type(extension)
                    self._s3.upload_bytes(image_data, s3_key, content_type=content_type)

                    chapter_manifest["panel_keys"].append(s3_key)
                    manifest["total_panels"] += 1

                except ImageDownloadError as e:
                    logger.warning(
                        "Failed to download page, skipping",
                        extra={
                            "job_id": job_id,
                            "chapter_id": chapter.chapter_id,
                            "page_idx": page_idx,
                            "error": str(e),
                        },
                    )
                    continue

                except Exception as e:
                    logger.warning(
                        "Unexpected error downloading page, skipping",
                        extra={
                            "job_id": job_id,
                            "chapter_id": chapter.chapter_id,
                            "page_idx": page_idx,
                            "error": str(e),
                        },
                    )
                    continue

            # Only add chapter to manifest if it has panels
            if chapter_manifest["panel_keys"]:
                manifest["chapters"].append(chapter_manifest)

        # Store manifest in S3
        manifest_key = f"jobs/{job_id}/panel_manifest.json"
        self._s3.upload_json(manifest, manifest_key)

        logger.info(
            "Panel download complete",
            extra={
                "job_id": job_id,
                "total_panels": manifest["total_panels"],
                "chapters_downloaded": len(manifest["chapters"]),
            },
        )

        return manifest

    def _get_extension_from_url(self, url: str) -> str:
        """Extract file extension from URL, defaulting to jpg."""
        # Get the filename part
        path = url.split("?")[0]  # Remove query params
        filename = path.split("/")[-1]

        if "." in filename:
            ext = filename.rsplit(".", 1)[-1].lower()
            if ext in ("jpg", "jpeg", "png", "gif", "webp"):
                return ext if ext != "jpeg" else "jpg"

        return "jpg"

    def _get_content_type(self, extension: str) -> str:
        """Get content type from file extension."""
        content_types = {
            "jpg": "image/jpeg",
            "jpeg": "image/jpeg",
            "png": "image/png",
            "gif": "image/gif",
            "webp": "image/webp",
        }
        return content_types.get(extension, "image/jpeg")
