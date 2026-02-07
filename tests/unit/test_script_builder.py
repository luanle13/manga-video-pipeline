"""Tests for script builder."""

from unittest.mock import MagicMock, patch

import pytest

from src.common.models import (
    ChapterInfo,
    MangaInfo,
    PipelineSettings,
    ScriptDocument,
)
from src.scriptgen.deepinfra_client import DeepInfraAPIError, DeepInfraClient
from src.scriptgen.script_builder import PLACEHOLDER_TEXT, ScriptBuilder


@pytest.fixture
def mock_deepinfra_client() -> MagicMock:
    """Create a mock DeepInfra client."""
    client = MagicMock(spec=DeepInfraClient)
    return client


@pytest.fixture
def script_builder(mock_deepinfra_client: MagicMock) -> ScriptBuilder:
    """Create a ScriptBuilder with mock client."""
    return ScriptBuilder(mock_deepinfra_client)


@pytest.fixture
def sample_manga() -> MangaInfo:
    """Sample manga information."""
    return MangaInfo(
        manga_id="manga-123",
        title="One Piece",
        description="A pirate adventure story about finding treasure",
        genres=["Action", "Adventure", "Comedy"],
        cover_url="https://example.com/cover.jpg",
        chapters=[
            ChapterInfo(
                chapter_id="ch-001",
                title="Romance Dawn",
                chapter_number="1",
                page_urls=[
                    "https://example.com/page1.jpg",
                    "https://example.com/page2.jpg",
                    "https://example.com/page3.jpg",
                ],
            ),
            ChapterInfo(
                chapter_id="ch-002",
                title="The Man in the Straw Hat",
                chapter_number="2",
                page_urls=[
                    "https://example.com/page4.jpg",
                    "https://example.com/page5.jpg",
                ],
            ),
            ChapterInfo(
                chapter_id="ch-003",
                title="Enter Zoro",
                chapter_number="3",
                page_urls=[
                    "https://example.com/page6.jpg",
                    "https://example.com/page7.jpg",
                    "https://example.com/page8.jpg",
                    "https://example.com/page9.jpg",
                ],
            ),
        ],
    )


@pytest.fixture
def sample_panel_manifest() -> dict:
    """Sample panel manifest."""
    return {
        "job_id": "job-456",
        "manga_id": "manga-123",
        "manga_title": "One Piece",
        "total_panels": 9,
        "chapters": [
            {
                "chapter_id": "ch-001",
                "chapter_number": "1",
                "panel_keys": [
                    "jobs/job-456/panels/0000_0000.jpg",
                    "jobs/job-456/panels/0000_0001.jpg",
                    "jobs/job-456/panels/0000_0002.jpg",
                ],
            },
            {
                "chapter_id": "ch-002",
                "chapter_number": "2",
                "panel_keys": [
                    "jobs/job-456/panels/0001_0000.jpg",
                    "jobs/job-456/panels/0001_0001.jpg",
                ],
            },
            {
                "chapter_id": "ch-003",
                "chapter_number": "3",
                "panel_keys": [
                    "jobs/job-456/panels/0002_0000.jpg",
                    "jobs/job-456/panels/0002_0001.jpg",
                    "jobs/job-456/panels/0002_0002.jpg",
                    "jobs/job-456/panels/0002_0003.jpg",
                ],
            },
        ],
    }


@pytest.fixture
def sample_settings() -> PipelineSettings:
    """Sample pipeline settings."""
    return PipelineSettings(
        tone="exciting and dramatic",
        script_style="chapter_walkthrough",
    )


class TestBuildChapterPrompt:
    """Tests for build_chapter_prompt method."""

    def test_prompt_includes_tone_and_style(
        self, script_builder: ScriptBuilder, sample_manga: MangaInfo
    ) -> None:
        """Test that prompts include tone and style."""
        chapter = sample_manga.chapters[0]
        system_prompt, user_prompt = script_builder.build_chapter_prompt(
            manga=sample_manga,
            chapter=chapter,
            chapter_idx=0,
            total_chapters=3,
            tone="exciting",
            style="energetic",
        )

        # System prompt should include tone and style
        assert "exciting" in system_prompt
        assert "energetic" in system_prompt
        assert "Vietnamese" in system_prompt

        # User prompt should also reference tone and style
        assert "exciting" in user_prompt
        assert "energetic" in user_prompt

    def test_prompt_includes_manga_context(
        self, script_builder: ScriptBuilder, sample_manga: MangaInfo
    ) -> None:
        """Test that prompts include manga context."""
        chapter = sample_manga.chapters[0]
        system_prompt, user_prompt = script_builder.build_chapter_prompt(
            manga=sample_manga,
            chapter=chapter,
            chapter_idx=0,
            total_chapters=3,
            tone="dramatic",
            style="formal",
        )

        # User prompt should include manga details
        assert "One Piece" in user_prompt
        assert "Action" in user_prompt
        assert "Adventure" in user_prompt
        assert "Comedy" in user_prompt
        assert "pirate adventure story" in user_prompt

    def test_prompt_includes_chapter_details(
        self, script_builder: ScriptBuilder, sample_manga: MangaInfo
    ) -> None:
        """Test that prompts include chapter details."""
        chapter = sample_manga.chapters[0]
        system_prompt, user_prompt = script_builder.build_chapter_prompt(
            manga=sample_manga,
            chapter=chapter,
            chapter_idx=0,
            total_chapters=3,
            tone="engaging",
            style="casual",
        )

        # User prompt should include chapter details
        assert "1" in user_prompt  # chapter number
        assert "Romance Dawn" in user_prompt  # chapter title
        assert "3" in user_prompt  # page count

    def test_prompt_includes_chapter_position(
        self, script_builder: ScriptBuilder, sample_manga: MangaInfo
    ) -> None:
        """Test that prompts include chapter position."""
        chapter = sample_manga.chapters[1]
        system_prompt, user_prompt = script_builder.build_chapter_prompt(
            manga=sample_manga,
            chapter=chapter,
            chapter_idx=1,
            total_chapters=3,
            tone="informative",
            style="detailed",
        )

        # User prompt should indicate position
        assert "chapter 2 of 3" in user_prompt

    def test_prompt_handles_missing_chapter_number(
        self, script_builder: ScriptBuilder, sample_manga: MangaInfo
    ) -> None:
        """Test that prompts handle missing chapter number."""
        chapter = ChapterInfo(
            chapter_id="ch-999",
            title="Special Chapter",
            chapter_number=None,
            page_urls=["page1.jpg"],
        )

        system_prompt, user_prompt = script_builder.build_chapter_prompt(
            manga=sample_manga,
            chapter=chapter,
            chapter_idx=0,
            total_chapters=1,
            tone="casual",
            style="summary",
        )

        # Should handle None chapter number gracefully
        assert "?" in user_prompt or "Chapter:" in user_prompt


class TestGenerateFullScript:
    """Tests for generate_full_script method."""

    def test_generates_script_for_all_chapters(
        self,
        script_builder: ScriptBuilder,
        mock_deepinfra_client: MagicMock,
        sample_manga: MangaInfo,
        sample_panel_manifest: dict,
        sample_settings: PipelineSettings,
    ) -> None:
        """Test that script is generated for all chapters."""
        mock_deepinfra_client.generate_text.return_value = (
            "Đây là một chương tuyệt vời."
        )

        result = script_builder.generate_full_script(
            manga=sample_manga,
            panel_manifest=sample_panel_manifest,
            settings=sample_settings,
        )

        # Should have segments for all chapters
        assert len(result.segments) == 3
        assert isinstance(result, ScriptDocument)
        assert result.job_id == "job-456"
        assert result.manga_title == "One Piece"

        # Verify generate_text was called for each chapter
        assert mock_deepinfra_client.generate_text.call_count == 3

    def test_panel_ranges_calculated_correctly(
        self,
        script_builder: ScriptBuilder,
        mock_deepinfra_client: MagicMock,
        sample_manga: MangaInfo,
        sample_panel_manifest: dict,
        sample_settings: PipelineSettings,
    ) -> None:
        """Test that panel ranges are calculated correctly."""
        mock_deepinfra_client.generate_text.return_value = "Script text"

        result = script_builder.generate_full_script(
            manga=sample_manga,
            panel_manifest=sample_panel_manifest,
            settings=sample_settings,
        )

        # Chapter 1: panels 0-2 (3 panels)
        assert result.segments[0].panel_start == 0
        assert result.segments[0].panel_end == 2

        # Chapter 2: panels 3-4 (2 panels)
        assert result.segments[1].panel_start == 3
        assert result.segments[1].panel_end == 4

        # Chapter 3: panels 5-8 (4 panels)
        assert result.segments[2].panel_start == 5
        assert result.segments[2].panel_end == 8

    def test_segment_order_matches_chapter_order(
        self,
        script_builder: ScriptBuilder,
        mock_deepinfra_client: MagicMock,
        sample_manga: MangaInfo,
        sample_panel_manifest: dict,
        sample_settings: PipelineSettings,
    ) -> None:
        """Test that segment order matches chapter order."""
        # Return different text for each chapter
        mock_deepinfra_client.generate_text.side_effect = [
            "Chapter 1 script",
            "Chapter 2 script",
            "Chapter 3 script",
        ]

        result = script_builder.generate_full_script(
            manga=sample_manga,
            panel_manifest=sample_panel_manifest,
            settings=sample_settings,
        )

        # Verify order
        assert result.segments[0].chapter == "1"
        assert result.segments[0].text == "Chapter 1 script"

        assert result.segments[1].chapter == "2"
        assert result.segments[1].text == "Chapter 2 script"

        assert result.segments[2].chapter == "3"
        assert result.segments[2].text == "Chapter 3 script"

    def test_failed_chapter_gets_placeholder(
        self,
        script_builder: ScriptBuilder,
        mock_deepinfra_client: MagicMock,
        sample_manga: MangaInfo,
        sample_panel_manifest: dict,
        sample_settings: PipelineSettings,
    ) -> None:
        """Test that failed chapter generation uses placeholder."""
        # First chapter succeeds, second fails, third succeeds
        mock_deepinfra_client.generate_text.side_effect = [
            "Chapter 1 script",
            DeepInfraAPIError("API Error", status_code=500),
            "Chapter 3 script",
        ]

        result = script_builder.generate_full_script(
            manga=sample_manga,
            panel_manifest=sample_panel_manifest,
            settings=sample_settings,
        )

        # Verify all chapters have segments
        assert len(result.segments) == 3

        # First and third should have real scripts
        assert result.segments[0].text == "Chapter 1 script"
        assert result.segments[2].text == "Chapter 3 script"

        # Second should have placeholder
        assert result.segments[1].text == PLACEHOLDER_TEXT

    def test_exception_during_generation_gets_placeholder(
        self,
        script_builder: ScriptBuilder,
        mock_deepinfra_client: MagicMock,
        sample_manga: MangaInfo,
        sample_panel_manifest: dict,
        sample_settings: PipelineSettings,
    ) -> None:
        """Test that generic exceptions also use placeholder."""
        # Simulate unexpected error
        mock_deepinfra_client.generate_text.side_effect = RuntimeError("Unexpected")

        result = script_builder.generate_full_script(
            manga=sample_manga,
            panel_manifest=sample_panel_manifest,
            settings=sample_settings,
        )

        # All chapters should have placeholder
        assert len(result.segments) == 3
        assert all(seg.text == PLACEHOLDER_TEXT for seg in result.segments)

    def test_passes_correct_prompts_to_client(
        self,
        script_builder: ScriptBuilder,
        mock_deepinfra_client: MagicMock,
        sample_manga: MangaInfo,
        sample_panel_manifest: dict,
        sample_settings: PipelineSettings,
    ) -> None:
        """Test that correct prompts are passed to LLM client."""
        mock_deepinfra_client.generate_text.return_value = "Script"

        script_builder.generate_full_script(
            manga=sample_manga,
            panel_manifest=sample_panel_manifest,
            settings=sample_settings,
        )

        # Check first call
        first_call = mock_deepinfra_client.generate_text.call_args_list[0]
        system_prompt = first_call.kwargs["system_prompt"]
        user_prompt = first_call.kwargs["user_prompt"]

        # System prompt should have tone and style
        assert sample_settings.tone in system_prompt
        assert sample_settings.script_style in system_prompt

        # User prompt should have manga and chapter context
        assert sample_manga.title in user_prompt
        assert "Romance Dawn" in user_prompt

    def test_handles_empty_chapter_list(
        self,
        script_builder: ScriptBuilder,
        mock_deepinfra_client: MagicMock,
        sample_panel_manifest: dict,
        sample_settings: PipelineSettings,
    ) -> None:
        """Test handling of manga with no chapters."""
        empty_manga = MangaInfo(
            manga_id="empty",
            title="Empty Manga",
            description="No chapters",
            genres=[],
            cover_url=None,
            chapters=[],
        )

        result = script_builder.generate_full_script(
            manga=empty_manga,
            panel_manifest=sample_panel_manifest,
            settings=sample_settings,
        )

        # Should return empty segments
        assert len(result.segments) == 0
        assert result.manga_title == "Empty Manga"


class TestEstimateDurationMinutes:
    """Tests for estimate_duration_minutes method."""

    def test_calculates_duration_correctly(
        self, script_builder: ScriptBuilder
    ) -> None:
        """Test that duration is calculated correctly."""
        # Create script with known word count
        # 250 words at 250 words/min = 1 minute
        words = " ".join(["word"] * 250)
        script = ScriptDocument(
            job_id="test-job",
            manga_title="Test Manga",
            segments=[
                {
                    "chapter": "1",
                    "text": words,
                    "panel_start": 0,
                    "panel_end": 5,
                }
            ],
        )

        duration = script_builder.estimate_duration_minutes(script)

        # Should be approximately 1 minute
        assert 0.9 <= duration <= 1.1

    def test_handles_multiple_segments(self, script_builder: ScriptBuilder) -> None:
        """Test duration calculation across multiple segments."""
        # 125 words per segment * 4 segments = 500 words
        # 500 words / 250 words/min = 2 minutes
        words = " ".join(["word"] * 125)
        script = ScriptDocument(
            job_id="test-job",
            manga_title="Test Manga",
            segments=[
                {"chapter": "1", "text": words, "panel_start": 0, "panel_end": 2},
                {"chapter": "2", "text": words, "panel_start": 3, "panel_end": 5},
                {"chapter": "3", "text": words, "panel_start": 6, "panel_end": 8},
                {"chapter": "4", "text": words, "panel_start": 9, "panel_end": 11},
            ],
        )

        duration = script_builder.estimate_duration_minutes(script)

        # Should be approximately 2 minutes
        assert 1.9 <= duration <= 2.1

    def test_handles_empty_script(self, script_builder: ScriptBuilder) -> None:
        """Test duration for empty script."""
        script = ScriptDocument(
            job_id="test-job",
            manga_title="Test Manga",
            segments=[],
        )

        duration = script_builder.estimate_duration_minutes(script)

        # Should be 0
        assert duration == 0.0

    def test_handles_vietnamese_text(self, script_builder: ScriptBuilder) -> None:
        """Test duration calculation with Vietnamese text."""
        vietnamese_text = (
            "Đây là một câu chuyện phiêu lưu tuyệt vời về One Piece. "
            "Luffy là một cậu bé mơ ước trở thành Vua Hải Tặc."
        )
        # Count words (split by whitespace)
        word_count = len(vietnamese_text.split())

        script = ScriptDocument(
            job_id="test-job",
            manga_title="Test Manga",
            segments=[
                {
                    "chapter": "1",
                    "text": vietnamese_text,
                    "panel_start": 0,
                    "panel_end": 5,
                }
            ],
        )

        duration = script_builder.estimate_duration_minutes(script)

        # Expected duration
        expected = word_count / 250
        assert abs(duration - expected) < 0.01

    def test_duration_estimate_is_reasonable(
        self, script_builder: ScriptBuilder
    ) -> None:
        """Test that duration estimate is in reasonable range."""
        # Typical chapter script might be 100-300 words
        typical_script = " ".join(["word"] * 200)
        script = ScriptDocument(
            job_id="test-job",
            manga_title="Test Manga",
            segments=[
                {"chapter": "1", "text": typical_script, "panel_start": 0, "panel_end": 5}
            ],
        )

        duration = script_builder.estimate_duration_minutes(script)

        # 200 words / 250 = 0.8 minutes
        assert 0.7 <= duration <= 0.9


class TestScriptBuilderInitialization:
    """Tests for ScriptBuilder initialization."""

    def test_initializes_with_client(
        self, mock_deepinfra_client: MagicMock
    ) -> None:
        """Test that ScriptBuilder initializes with client."""
        builder = ScriptBuilder(mock_deepinfra_client)

        assert builder._client is mock_deepinfra_client
