"""Unit tests for YouTube metadata generator."""

import pytest

from src.common.models import ChapterInfo, JobRecord, JobStatus, MangaInfo
from src.uploader.metadata_generator import MetadataGenerator


@pytest.fixture
def metadata_generator():
    """Metadata generator instance."""
    return MetadataGenerator()


@pytest.fixture
def sample_manga():
    """Sample manga with normal length title."""
    return MangaInfo(
        manga_id="manga-123",
        title="One Piece",
        description="Câu chuyện về hải tặc Luffy và phi hành đoàn Mũ Rơm tìm kiếm kho báu huyền thoại One Piece.",
        genres=["Phiêu lưu", "Hành động", "Fantasy"],
        cover_url="https://example.com/cover.jpg",
        chapters=[
            ChapterInfo(
                chapter_id="ch1",
                title="Chapter 1",
                chapter_number="1",
                page_urls=["page1.jpg"],
            ),
            ChapterInfo(
                chapter_id="ch2",
                title="Chapter 2",
                chapter_number="2",
                page_urls=["page2.jpg"],
            ),
        ],
    )


@pytest.fixture
def sample_job():
    """Sample job record."""
    return JobRecord(
        job_id="job-123",
        manga_id="manga-123",
        manga_title="One Piece",
        status=JobStatus.rendering,
    )


@pytest.fixture
def long_title_manga():
    """Manga with very long title that needs truncation."""
    return MangaInfo(
        manga_id="manga-456",
        title="Tôi Được Chuyển Sinh Thành Slime Và Trở Thành Vua Quỷ Mạnh Nhất Trong Thế Giới Isekai Với Năng Lực Đặc Biệt",
        description="Manga về chuyển sinh",
        genres=["Isekai", "Fantasy"],
        cover_url=None,
        chapters=[],
    )


@pytest.fixture
def special_chars_manga():
    """Manga with special characters in title."""
    return MangaInfo(
        manga_id="manga-789",
        title="Tokyo Ghoul:re - [Part 2] (Complete)",
        description="Manga kinh dị",
        genres=["Horror", "Action"],
        cover_url=None,
        chapters=[],
    )


@pytest.fixture
def vietnamese_manga():
    """Manga with Vietnamese title."""
    return MangaInfo(
        manga_id="manga-101",
        title="Võ Lâm Truyền Kỳ",
        description="Truyện võ hiệp Việt Nam với các nhân vật anh hùng",
        genres=["Võ hiệp", "Hành động"],
        cover_url=None,
        chapters=[],
    )


class TestMetadataGeneratorInitialization:
    """Tests for MetadataGenerator initialization."""

    def test_initializes_successfully(self):
        """Test successful initialization."""
        generator = MetadataGenerator()
        assert generator is not None


class TestGenerateMetadata:
    """Tests for complete metadata generation."""

    def test_generates_complete_metadata(self, metadata_generator, sample_manga, sample_job):
        """Test that all metadata fields are generated."""
        metadata = metadata_generator.generate_metadata(sample_manga, sample_job)

        # Verify all required fields are present
        assert "title" in metadata
        assert "description" in metadata
        assert "tags" in metadata
        assert "category_id" in metadata
        assert "default_language" in metadata
        assert "privacy_status" in metadata

        # Verify correct values
        assert metadata["category_id"] == "24"
        assert metadata["default_language"] == "vi"
        assert metadata["privacy_status"] == "public"

    def test_metadata_meets_youtube_constraints(
        self, metadata_generator, sample_manga, sample_job
    ):
        """Test that metadata meets YouTube constraints."""
        metadata = metadata_generator.generate_metadata(sample_manga, sample_job)

        # Title max 100 chars
        assert len(metadata["title"]) <= 100

        # Description max 5000 chars
        assert len(metadata["description"]) <= 5000

        # Tags total max 500 chars
        tags_total = ",".join(metadata["tags"])
        assert len(tags_total) <= 500


class TestTitleGeneration:
    """Tests for title generation."""

    def test_generates_correct_title_format(self, metadata_generator, sample_manga):
        """Test title format is correct."""
        title = metadata_generator._generate_title(sample_manga.title)

        assert title.startswith("Review Manga ")
        assert title.endswith(" | Tóm Tắt Đầy Đủ")
        assert "One Piece" in title

    def test_title_under_100_chars(self, metadata_generator, sample_manga):
        """Test that title doesn't exceed 100 characters."""
        title = metadata_generator._generate_title(sample_manga.title)

        assert len(title) <= 100

    def test_truncates_long_manga_title(self, metadata_generator, long_title_manga):
        """Test that long manga titles are truncated."""
        title = metadata_generator._generate_title(long_title_manga.title)

        # Verify title is under limit
        assert len(title) <= 100

        # Verify format is preserved
        assert title.startswith("Review Manga ")
        assert title.endswith(" | Tóm Tắt Đầy Đủ")

    def test_preserves_vietnamese_characters_in_title(
        self, metadata_generator, vietnamese_manga
    ):
        """Test that Vietnamese characters are preserved in title."""
        title = metadata_generator._generate_title(vietnamese_manga.title)

        # Vietnamese characters should be preserved
        assert "Võ Lâm" in title

    def test_handles_empty_manga_title(self, metadata_generator):
        """Test handling of empty manga title."""
        title = metadata_generator._generate_title("")

        # Should still have valid format
        assert title.startswith("Review Manga ")
        assert title.endswith(" | Tóm Tắt Đầy Đủ")
        assert len(title) <= 100


class TestDescriptionGeneration:
    """Tests for description generation."""

    def test_generates_correct_description_format(
        self, metadata_generator, sample_manga
    ):
        """Test description format is correct."""
        description = metadata_generator._generate_description(sample_manga)

        lines = description.split("\n")

        # Line 1: Introduction
        assert lines[0].startswith("📖 Review và tóm tắt manga")
        assert sample_manga.title in lines[0]

        # Line 2: blank
        assert lines[1] == ""

        # Line 3: Description
        assert len(lines[2]) > 0

        # Line 4: blank
        assert lines[3] == ""

        # Line 5: Genres
        assert lines[4].startswith("Thể loại:")

        # Line 6: Chapter count
        assert lines[5].startswith("Số chương:")

        # Line 7: blank
        assert lines[6] == ""

        # Line 8: Hashtags
        assert lines[7].startswith("#manga")

    def test_description_includes_genres(self, metadata_generator, sample_manga):
        """Test that description includes genres."""
        description = metadata_generator._generate_description(sample_manga)

        for genre in sample_manga.genres:
            assert genre in description

    def test_description_includes_chapter_count(
        self, metadata_generator, sample_manga
    ):
        """Test that description includes correct chapter count."""
        description = metadata_generator._generate_description(sample_manga)

        assert f"Số chương: {len(sample_manga.chapters)}" in description

    def test_truncates_long_description(self, metadata_generator):
        """Test that long manga descriptions are truncated to 500 chars."""
        # Create manga with very long description
        long_desc = "A" * 1000
        manga = MangaInfo(
            manga_id="test",
            title="Test",
            description=long_desc,
            genres=["Test"],
            cover_url=None,
            chapters=[],
        )

        description = metadata_generator._generate_description(manga)

        # Find the description line (line 3, index 2)
        lines = description.split("\n")
        desc_line = lines[2]

        # Should be truncated to ~500 chars with "..."
        assert len(desc_line) <= 503  # 500 + "..."
        assert desc_line.endswith("...")

    def test_description_under_5000_chars(self, metadata_generator, sample_manga):
        """Test that description doesn't exceed 5000 characters."""
        description = metadata_generator._generate_description(sample_manga)

        assert len(description) <= 5000

    def test_handles_missing_description(self, metadata_generator):
        """Test handling of missing manga description."""
        manga = MangaInfo(
            manga_id="test",
            title="Test",
            description="",
            genres=["Test"],
            cover_url=None,
            chapters=[],
        )

        description = metadata_generator._generate_description(manga)

        # Should have default description
        assert "Manga hay và hấp dẫn" in description


class TestTagsGeneration:
    """Tests for tags generation."""

    def test_generates_tags_list(self, metadata_generator, sample_manga):
        """Test that tags are generated as a list."""
        tags = metadata_generator._generate_tags(sample_manga)

        assert isinstance(tags, list)
        assert len(tags) > 0

    def test_includes_manga_title_tag(self, metadata_generator, sample_manga):
        """Test that manga title is included in tags."""
        tags = metadata_generator._generate_tags(sample_manga)

        # Title should be sanitized and included
        sanitized_title = metadata_generator._sanitize_tag(sample_manga.title)
        assert sanitized_title in tags

    def test_includes_genre_tags(self, metadata_generator, sample_manga):
        """Test that genres are included in tags."""
        tags = metadata_generator._generate_tags(sample_manga)

        for genre in sample_manga.genres:
            sanitized_genre = metadata_generator._sanitize_tag(genre)
            assert sanitized_genre in tags

    def test_includes_standard_tags(self, metadata_generator, sample_manga):
        """Test that standard tags are included."""
        tags = metadata_generator._generate_tags(sample_manga)

        standard_tags = [
            "review manga",
            "tóm tắt manga",
            "manga hay",
            "đọc manga",
        ]

        for tag in standard_tags:
            assert tag in tags

    def test_tags_total_under_500_chars(self, metadata_generator, sample_manga):
        """Test that total tag length doesn't exceed 500 characters."""
        tags = metadata_generator._generate_tags(sample_manga)

        # Join with commas as YouTube does
        tags_string = ",".join(tags)
        assert len(tags_string) <= 500

    def test_removes_duplicate_tags(self, metadata_generator):
        """Test that duplicate tags are removed."""
        manga = MangaInfo(
            manga_id="test",
            title="manga",
            description="test",
            genres=["manga", "manga"],  # Duplicate genre
            cover_url=None,
            chapters=[],
        )

        tags = metadata_generator._generate_tags(manga)

        # Check for duplicates
        assert len(tags) == len(set(tags))


class TestTagSanitization:
    """Tests for tag sanitization."""

    def test_sanitizes_special_characters(self, metadata_generator):
        """Test that special characters are removed."""
        tag = metadata_generator._sanitize_tag("Tokyo Ghoul:re - [Part 2]")

        # Special characters should be removed
        assert ":" not in tag
        assert "[" not in tag
        assert "]" not in tag
        assert "-" not in tag

    def test_converts_to_lowercase(self, metadata_generator):
        """Test that tags are converted to lowercase."""
        tag = metadata_generator._sanitize_tag("One Piece")

        assert tag == "one piece"

    def test_preserves_vietnamese_characters(self, metadata_generator):
        """Test that Vietnamese characters are preserved."""
        tag = metadata_generator._sanitize_tag("Võ Lâm Truyền Kỳ")

        # Vietnamese characters should be preserved
        assert "võ" in tag
        assert "lâm" in tag
        assert "truyền" in tag
        assert "kỳ" in tag

    def test_preserves_spaces(self, metadata_generator):
        """Test that spaces are preserved."""
        tag = metadata_generator._sanitize_tag("one piece")

        assert " " in tag
        assert tag == "one piece"

    def test_removes_extra_whitespace(self, metadata_generator):
        """Test that extra whitespace is removed."""
        tag = metadata_generator._sanitize_tag("  one   piece  ")

        assert tag == "one piece"

    def test_handles_empty_string(self, metadata_generator):
        """Test handling of empty string."""
        tag = metadata_generator._sanitize_tag("")

        assert tag == ""


class TestTagFiltering:
    """Tests for tag filtering by length."""

    def test_filters_tags_exceeding_limit(self, metadata_generator):
        """Test that tags exceeding limit are filtered."""
        # Create tags that would exceed 500 char limit
        long_tags = ["a" * 100 for _ in range(10)]  # 1000 chars total

        filtered = metadata_generator._filter_tags_by_length(long_tags)

        # Should filter to stay under 500 chars
        total_length = len(",".join(filtered))
        assert total_length <= 500

    def test_keeps_tags_within_limit(self, metadata_generator):
        """Test that tags within limit are kept."""
        short_tags = ["tag1", "tag2", "tag3", "tag4"]

        filtered = metadata_generator._filter_tags_by_length(short_tags)

        # All should be kept (well under 500 chars)
        assert len(filtered) == len(short_tags)

    def test_preserves_tag_order(self, metadata_generator):
        """Test that tag order is preserved."""
        tags = ["first", "second", "third", "fourth"]

        filtered = metadata_generator._filter_tags_by_length(tags)

        # Order should be preserved
        assert filtered == tags


class TestEdgeCases:
    """Tests for edge cases."""

    def test_handles_manga_with_no_genres(self, metadata_generator):
        """Test handling of manga with no genres."""
        manga = MangaInfo(
            manga_id="test",
            title="Test",
            description="test",
            genres=[],
            cover_url=None,
            chapters=[],
        )

        description = metadata_generator._generate_description(manga)

        # Should have default genre text
        assert "Thể loại: Không rõ" in description

    def test_handles_manga_with_no_chapters(self, metadata_generator):
        """Test handling of manga with no chapters."""
        manga = MangaInfo(
            manga_id="test",
            title="Test",
            description="test",
            genres=["Test"],
            cover_url=None,
            chapters=[],
        )

        description = metadata_generator._generate_description(manga)

        # Should show 0 chapters
        assert "Số chương: 0" in description

    def test_handles_manga_with_many_genres(self, metadata_generator):
        """Test handling of manga with many genres."""
        manga = MangaInfo(
            manga_id="test",
            title="Test",
            description="test",
            genres=["Genre1", "Genre2", "Genre3", "Genre4", "Genre5"],
            cover_url=None,
            chapters=[],
        )

        tags = metadata_generator._generate_tags(manga)

        # Should include all genres (if within limit)
        for genre in manga.genres:
            sanitized_genre = metadata_generator._sanitize_tag(genre)
            # Check if present or filtered due to length
            if sanitized_genre not in tags:
                # If filtered, total should be at limit
                assert len(",".join(tags)) <= 500


class TestVietnameseContent:
    """Tests for Vietnamese content handling."""

    def test_preserves_vietnamese_in_title(
        self, metadata_generator, vietnamese_manga, sample_job
    ):
        """Test that Vietnamese characters are preserved in title."""
        metadata = metadata_generator.generate_metadata(vietnamese_manga, sample_job)

        # Vietnamese characters should be preserved
        assert "Võ Lâm" in metadata["title"]

    def test_preserves_vietnamese_in_description(
        self, metadata_generator, vietnamese_manga
    ):
        """Test that Vietnamese characters are preserved in description."""
        description = metadata_generator._generate_description(vietnamese_manga)

        # Vietnamese characters should be preserved
        assert "Võ Lâm" in description
        assert "Võ hiệp" in description

    def test_preserves_vietnamese_in_tags(
        self, metadata_generator, vietnamese_manga
    ):
        """Test that Vietnamese characters are preserved in tags."""
        tags = metadata_generator._generate_tags(vietnamese_manga)

        # Should have Vietnamese tags
        vietnamese_tags = [tag for tag in tags if any(char in tag for char in "áàảãạăắằẳẵặâấầẩẫậéèẻẽẹêếềểễệíìỉĩịóòỏõọôốồổỗộơớờởỡợúùủũụưứừửữựýỳỷỹỵđ")]
        assert len(vietnamese_tags) > 0
