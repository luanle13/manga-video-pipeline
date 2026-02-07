"""YouTube video metadata generator for Vietnamese manga content."""

import re

from src.common.logging_config import setup_logger
from src.common.models import JobRecord, MangaInfo

logger = setup_logger(__name__)


class MetadataGenerator:
    """Generator for YouTube video metadata in Vietnamese."""

    # YouTube constraints
    MAX_TITLE_LENGTH = 100
    MAX_DESCRIPTION_LENGTH = 5000
    MAX_TAGS_TOTAL_LENGTH = 500

    def __init__(self) -> None:
        """Initialize the metadata generator."""
        logger.info("MetadataGenerator initialized")

    def generate_metadata(self, manga: MangaInfo, job: JobRecord) -> dict:
        """
        Generate YouTube video metadata for a manga video.

        Args:
            manga: Manga information.
            job: Job record with manga_title.

        Returns:
            Dictionary with YouTube video metadata:
            - title: Video title (max 100 chars)
            - description: Video description (max 5000 chars)
            - tags: List of tags (total ≤500 chars)
            - category_id: YouTube category ID (24 = Entertainment)
            - default_language: Language code (vi = Vietnamese)
            - privacy_status: Privacy setting (public)
        """
        logger.info(
            "Generating YouTube metadata",
            extra={
                "manga_id": manga.manga_id,
                "manga_title": manga.title,
            },
        )

        # Generate title
        title = self._generate_title(manga.title)

        # Generate description
        description = self._generate_description(manga)

        # Generate tags
        tags = self._generate_tags(manga)

        metadata = {
            "title": title,
            "description": description,
            "tags": tags,
            "category_id": "24",  # Entertainment
            "default_language": "vi",  # Vietnamese
            "privacy_status": "public",
        }

        logger.info(
            "YouTube metadata generated",
            extra={
                "title_length": len(title),
                "description_length": len(description),
                "tags_count": len(tags),
                "tags_total_length": len(",".join(tags)),
            },
        )

        return metadata

    def _generate_title(self, manga_title: str) -> str:
        """
        Generate YouTube video title.

        Format: "Review Manga {title} | Tóm Tắt Đầy Đủ"

        Args:
            manga_title: Manga title.

        Returns:
            Formatted title (max 100 chars).
        """
        # Title template
        prefix = "Review Manga "
        suffix = " | Tóm Tắt Đầy Đủ"

        # Calculate available space for manga title
        available_space = self.MAX_TITLE_LENGTH - len(prefix) - len(suffix)

        # Truncate manga title if needed
        if len(manga_title) > available_space:
            manga_title_truncated = manga_title[:available_space].rstrip()
            logger.info(
                "Manga title truncated for video title",
                extra={
                    "original_length": len(manga_title),
                    "truncated_length": len(manga_title_truncated),
                },
            )
        else:
            manga_title_truncated = manga_title

        title = f"{prefix}{manga_title_truncated}{suffix}"

        # Ensure we don't exceed max length (safety check)
        if len(title) > self.MAX_TITLE_LENGTH:
            title = title[:self.MAX_TITLE_LENGTH].rstrip()

        return title

    def _generate_description(self, manga: MangaInfo) -> str:
        """
        Generate YouTube video description.

        Format:
        - Line 1: "📖 Review và tóm tắt manga {title}"
        - Line 2: blank
        - Line 3: manga description (truncated to 500 chars)
        - Line 4: blank
        - Line 5: "Thể loại: {genres joined by comma}"
        - Line 6: "Số chương: {chapter_count}"
        - Line 7: blank
        - Line 8: "#manga #review #tomtat #{sanitized_title}"

        Args:
            manga: Manga information.

        Returns:
            Formatted description (max 5000 chars).
        """
        lines = []

        # Line 1: Introduction
        lines.append(f"📖 Review và tóm tắt manga {manga.title}")

        # Line 2: blank
        lines.append("")

        # Line 3: Description (truncated to 500 chars)
        description = manga.description.strip() if manga.description else ""
        if not description:
            description = "Manga hay và hấp dẫn"
        if len(description) > 500:
            description = description[:497] + "..."
        lines.append(description)

        # Line 4: blank
        lines.append("")

        # Line 5: Genres
        genres_str = ", ".join(manga.genres) if manga.genres else "Không rõ"
        lines.append(f"Thể loại: {genres_str}")

        # Line 6: Chapter count
        chapter_count = len(manga.chapters)
        lines.append(f"Số chương: {chapter_count}")

        # Line 7: blank
        lines.append("")

        # Line 8: Hashtags
        sanitized_title = self._sanitize_tag(manga.title)
        hashtags = f"#manga #review #tomtat #{sanitized_title}"
        lines.append(hashtags)

        # Join lines
        description_text = "\n".join(lines)

        # Ensure we don't exceed max length
        if len(description_text) > self.MAX_DESCRIPTION_LENGTH:
            description_text = description_text[:self.MAX_DESCRIPTION_LENGTH].rstrip()
            logger.warning(
                "Description truncated to fit YouTube limit",
                extra={"length": len(description_text)},
            )

        return description_text

    def _generate_tags(self, manga: MangaInfo) -> list[str]:
        """
        Generate YouTube video tags.

        Tags include:
        - Manga title
        - Each genre
        - Standard tags: "review manga", "tóm tắt manga", "manga hay", "đọc manga"

        All tags are sanitized (remove special chars, lowercase).
        Total tag string must be ≤500 chars.

        Args:
            manga: Manga information.

        Returns:
            List of sanitized tags (total ≤500 chars when joined).
        """
        tags = []

        # Add manga title tag
        title_tag = self._sanitize_tag(manga.title)
        if title_tag:
            tags.append(title_tag)

        # Add genre tags
        for genre in manga.genres:
            genre_tag = self._sanitize_tag(genre)
            if genre_tag:
                tags.append(genre_tag)

        # Add standard tags
        standard_tags = [
            "review manga",
            "tóm tắt manga",
            "manga hay",
            "đọc manga",
        ]
        tags.extend(standard_tags)

        # Remove duplicates while preserving order
        seen = set()
        unique_tags = []
        for tag in tags:
            if tag not in seen:
                seen.add(tag)
                unique_tags.append(tag)

        # Ensure total length is within limit
        tags_filtered = self._filter_tags_by_length(unique_tags)

        logger.debug(
            "Tags generated",
            extra={
                "total_tags": len(tags_filtered),
                "total_length": len(",".join(tags_filtered)),
            },
        )

        return tags_filtered

    def _sanitize_tag(self, text: str) -> str:
        """
        Sanitize text for use as a YouTube tag.

        Removes special characters but preserves Vietnamese characters,
        spaces, and basic alphanumeric characters. Converts to lowercase
        and trims whitespace.

        Args:
            text: Text to sanitize.

        Returns:
            Sanitized tag string.
        """
        # Remove special characters except Vietnamese characters, spaces, and alphanumeric
        # Keep: a-z, A-Z, 0-9, spaces, Vietnamese characters
        # Vietnamese character ranges: À-ỹ (U+00C0 to U+1EF9)
        sanitized = re.sub(r"[^\w\sÀ-ỹ]", "", text, flags=re.UNICODE)

        # Convert to lowercase
        sanitized = sanitized.lower()

        # Remove extra whitespace and trim
        sanitized = " ".join(sanitized.split())

        return sanitized

    def _filter_tags_by_length(self, tags: list[str]) -> list[str]:
        """
        Filter tags to ensure total length doesn't exceed limit.

        Keeps tags in order until adding the next tag would exceed
        the MAX_TAGS_TOTAL_LENGTH limit.

        Args:
            tags: List of tags to filter.

        Returns:
            Filtered list of tags within length limit.
        """
        filtered = []
        total_length = 0

        for tag in tags:
            # Calculate length if we add this tag
            # Add 1 for comma separator (except for first tag)
            tag_length = len(tag)
            separator_length = 1 if filtered else 0
            new_total = total_length + separator_length + tag_length

            # Check if adding this tag would exceed limit
            if new_total > self.MAX_TAGS_TOTAL_LENGTH:
                logger.info(
                    "Tag limit reached, truncating tag list",
                    extra={
                        "tags_kept": len(filtered),
                        "tags_dropped": len(tags) - len(filtered),
                        "total_length": total_length,
                    },
                )
                break

            # Add tag
            filtered.append(tag)
            total_length = new_total

        return filtered
