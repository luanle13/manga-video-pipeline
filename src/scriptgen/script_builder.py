"""Script builder for generating chapter-by-chapter narration scripts."""

from src.common.logging_config import setup_logger
from src.common.models import (
    ChapterInfo,
    MangaInfo,
    PipelineSettings,
    ScriptDocument,
    ScriptSegment,
)
from src.scriptgen.deepinfra_client import DeepInfraAPIError, DeepInfraClient

logger = setup_logger(__name__)

# Vietnamese speaking rate for duration estimation
VIETNAMESE_WORDS_PER_MINUTE = 250
PLACEHOLDER_TEXT = "[Chương này không có sẵn]"


class ScriptBuilder:
    """Builds chapter-by-chapter narration scripts for manga videos."""

    def __init__(self, deepinfra_client: DeepInfraClient) -> None:
        """
        Initialize the ScriptBuilder.

        Args:
            deepinfra_client: Client for calling DeepInfra API.
        """
        self._client = deepinfra_client
        logger.info("ScriptBuilder initialized")

    def build_chapter_prompt(
        self,
        manga: MangaInfo,
        chapter: ChapterInfo,
        chapter_idx: int,
        total_chapters: int,
        tone: str,
        style: str,
    ) -> tuple[str, str]:
        """
        Build system and user prompts for chapter script generation.

        Args:
            manga: Manga information for context.
            chapter: Chapter to generate script for.
            chapter_idx: 0-based index of this chapter.
            total_chapters: Total number of chapters.
            tone: Desired tone for narration.
            style: Desired writing style.

        Returns:
            Tuple of (system_prompt, user_prompt).
        """
        # Build system prompt with Vietnamese reviewer persona
        system_prompt = (
            f"You are a Vietnamese manga reviewer creating video narration. "
            f"Write in Vietnamese. "
            f"Tone: {tone}. "
            f"Style: {style}."
        )

        # Build user prompt with full context
        genres_text = ", ".join(manga.genres) if manga.genres else "N/A"
        chapter_position = f"chapter {chapter_idx + 1} of {total_chapters}"
        page_count = len(chapter.page_urls)

        user_prompt = f"""Create Vietnamese narration for this manga chapter:

Manga Title: {manga.title}
Genres: {genres_text}
Description: {manga.description}

Chapter: {chapter.chapter_number or '?'}
Chapter Title: {chapter.title}
Number of Pages: {page_count}
Position: This is {chapter_position} in the series.

Instructions:
- Write narration for this chapter that will be used as voiceover
- Group related pages together naturally
- Make the narration engaging and suitable for video format
- Keep the tone {tone} and style {style}
- Write entirely in Vietnamese
- Focus on storytelling and maintaining viewer interest"""

        logger.debug(
            "Built chapter prompt",
            extra={
                "manga_title": manga.title,
                "chapter": chapter.chapter_number,
                "chapter_idx": chapter_idx,
                "total_chapters": total_chapters,
            },
        )

        return system_prompt, user_prompt

    def generate_full_script(
        self,
        manga: MangaInfo,
        panel_manifest: dict,
        settings: PipelineSettings,
    ) -> ScriptDocument:
        """
        Generate complete script for all chapters in the manga.

        Args:
            manga: Manga information with chapters.
            panel_manifest: Panel manifest with chapter-to-panel mappings.
            settings: Pipeline settings with tone and style preferences.

        Returns:
            Complete ScriptDocument with all segments.
        """
        job_id = panel_manifest.get("job_id", "unknown")
        total_chapters = len(manga.chapters)

        logger.info(
            "Starting script generation",
            extra={
                "job_id": job_id,
                "manga_title": manga.title,
                "total_chapters": total_chapters,
            },
        )

        segments: list[ScriptSegment] = []
        cumulative_panel_idx = 0

        # Build chapter_id to panel info mapping
        chapter_panel_map: dict[str, dict] = {}
        for chapter_data in panel_manifest.get("chapters", []):
            chapter_id = chapter_data.get("chapter_id")
            if chapter_id:
                chapter_panel_map[chapter_id] = chapter_data

        # Generate script for each chapter
        for chapter_idx, chapter in enumerate(manga.chapters):
            chapter_number = chapter.chapter_number or str(chapter_idx + 1)

            logger.info(
                "Generating script for chapter",
                extra={
                    "chapter": chapter_number,
                    "chapter_idx": chapter_idx + 1,
                    "total": total_chapters,
                },
            )

            # Get panel count for this chapter
            chapter_panels = chapter_panel_map.get(chapter.chapter_id, {})
            panel_keys = chapter_panels.get("panel_keys", [])
            panel_count = len(panel_keys)

            # Calculate panel range for this chapter
            panel_start = cumulative_panel_idx
            panel_end = cumulative_panel_idx + panel_count - 1

            # Generate script text
            try:
                # Build prompts
                system_prompt, user_prompt = self.build_chapter_prompt(
                    manga=manga,
                    chapter=chapter,
                    chapter_idx=chapter_idx,
                    total_chapters=total_chapters,
                    tone=settings.tone,
                    style=settings.script_style,
                )

                # Call LLM
                script_text = self._client.generate_text(
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                )

                logger.info(
                    "Generated script for chapter",
                    extra={
                        "chapter": chapter_number,
                        "script_length": len(script_text),
                        "panel_range": f"{panel_start}-{panel_end}",
                    },
                )

            except (DeepInfraAPIError, Exception) as e:
                # Insert placeholder on failure
                script_text = PLACEHOLDER_TEXT
                logger.warning(
                    "Failed to generate script for chapter, using placeholder",
                    extra={
                        "chapter": chapter_number,
                        "error": str(e),
                    },
                )

            # Create segment
            segment = ScriptSegment(
                chapter=chapter_number,
                text=script_text,
                panel_start=panel_start,
                panel_end=panel_end,
            )
            segments.append(segment)

            # Update cumulative panel index
            cumulative_panel_idx += panel_count

        logger.info(
            "Script generation complete",
            extra={
                "job_id": job_id,
                "manga_title": manga.title,
                "segments": len(segments),
                "total_panels": cumulative_panel_idx,
            },
        )

        return ScriptDocument(
            job_id=job_id,
            manga_title=manga.title,
            segments=segments,
        )

    def estimate_duration_minutes(self, script: ScriptDocument) -> float:
        """
        Estimate the duration of the script in minutes.

        Uses Vietnamese speaking rate of ~250 words per minute.

        Args:
            script: Complete script document.

        Returns:
            Estimated duration in minutes.
        """
        total_words = 0

        for segment in script.segments:
            # Split on whitespace to count words
            words = segment.text.split()
            total_words += len(words)

        # Calculate duration in minutes
        duration_minutes = total_words / VIETNAMESE_WORDS_PER_MINUTE

        logger.info(
            "Estimated script duration",
            extra={
                "job_id": script.job_id,
                "total_words": total_words,
                "duration_minutes": round(duration_minutes, 2),
            },
        )

        return duration_minutes
