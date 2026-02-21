"""Lambda handler for review script generation."""

import re
import uuid
from typing import Any

from src.common.config import get_settings
from src.common.db import DynamoDBClient
from src.common.logging_config import set_correlation_id, setup_logger
from src.common.models import (
    JobStatus,
    ReviewManifest,
    ReviewScriptDocument,
    ReviewScriptSegment,
)
from src.common.secrets import SecretsClient
from src.common.storage import S3Client
from src.review_scriptgen.prompts import (
    REVIEW_SYSTEM_PROMPT,
    format_batch_chapters_prompt,
    format_conclusion_prompt,
    format_image_only_prompt,
    format_intro_prompt,
)
from src.scriptgen.deepinfra_client import DeepInfraClient

logger = setup_logger(__name__)

# Constants
BATCH_SIZE = 10  # Number of chapters to summarize in one LLM call
MAX_CONTENT_LENGTH = 500  # Max characters per chapter content to send to LLM


def _truncate_content(content: str, max_length: int = MAX_CONTENT_LENGTH) -> str:
    """Truncate content to max length while preserving word boundaries.

    Args:
        content: Text content to truncate
        max_length: Maximum length

    Returns:
        Truncated content
    """
    if len(content) <= max_length:
        return content

    # Truncate at word boundary
    truncated = content[:max_length].rsplit(" ", 1)[0]
    return truncated + "..."


def _parse_batch_response(response: str, chapter_numbers: list[float]) -> dict[float, str]:
    """Parse batch chapter summary response into individual summaries.

    Args:
        response: LLM response with [CHƯƠNG X] markers
        chapter_numbers: Expected chapter numbers

    Returns:
        Dict mapping chapter number to summary text
    """
    summaries: dict[float, str] = {}

    # Split by chapter markers
    pattern = r"\[CHƯƠNG\s*(\d+(?:\.\d+)?)\]"
    parts = re.split(pattern, response, flags=re.IGNORECASE)

    # parts will be [intro_text, chapter_num, summary, chapter_num, summary, ...]
    i = 1
    while i < len(parts) - 1:
        try:
            chapter_num = float(parts[i])
            summary = parts[i + 1].strip()
            summaries[chapter_num] = summary
            i += 2
        except (ValueError, IndexError):
            i += 1

    # Fill in missing chapters with empty summaries
    for num in chapter_numbers:
        if num not in summaries:
            summaries[num] = ""

    return summaries


def handler(event: dict, context: Any) -> dict:
    """
    Lambda handler for generating review scripts.

    Args:
        event: Lambda event with:
            - job_id: Job ID
            - review_manifest_s3_key: S3 key for review manifest
        context: Lambda context.

    Returns:
        Result dict with job_id, script_s3_key, segment_count.
    """
    # Generate correlation ID for request tracing
    correlation_id = str(uuid.uuid4())
    set_correlation_id(correlation_id)

    job_id = event.get("job_id")
    review_manifest_s3_key = event.get("review_manifest_s3_key")

    logger.info(
        "Review script generation handler started",
        extra={
            "correlation_id": correlation_id,
            "job_id": job_id,
            "manifest_key": review_manifest_s3_key,
        },
    )

    # Initialize configuration and clients
    settings = get_settings()
    db_client = DynamoDBClient(settings)
    s3_client = S3Client(settings)
    secrets_client = SecretsClient(region=settings.aws_region)

    deepinfra_client: DeepInfraClient | None = None

    try:
        # Step 1: Load API key from Secrets Manager
        logger.info("Loading DeepInfra API key from Secrets Manager")
        api_key = secrets_client.get_deepinfra_api_key(settings.deepinfra_secret_name)

        if not api_key:
            raise ValueError("DeepInfra API key is empty")

        # Step 2: Initialize DeepInfra client
        deepinfra_client = DeepInfraClient(
            api_key=api_key,
            base_url=settings.deepinfra_base_url,
        )

        # Step 3: Load review manifest from S3
        logger.info(
            "Loading review manifest",
            extra={"s3_key": review_manifest_s3_key},
        )
        manifest_data = s3_client.download_json(review_manifest_s3_key)
        manifest = ReviewManifest.model_validate(manifest_data)

        manga_info = manifest.manga_info

        # Step 4: Generate introduction segment
        logger.info("Generating introduction segment")
        intro_prompt = format_intro_prompt(
            title=manga_info.title,
            author=manga_info.author,
            genres=manga_info.genres,
            description=manga_info.description,
            total_chapters=manga_info.total_chapters,
        )

        intro_text = deepinfra_client.generate_text(
            system_prompt=REVIEW_SYSTEM_PROMPT,
            user_prompt=intro_prompt,
            max_tokens=1024,
            temperature=0.7,
        )

        segments: list[ReviewScriptSegment] = [
            ReviewScriptSegment(
                segment_type="intro",
                chapter_number=None,
                text=intro_text.strip(),
                panel_indices=[0] if manifest.panel_s3_keys else [],  # Use cover
            )
        ]

        logger.info(
            "Introduction segment generated",
            extra={"length": len(intro_text)},
        )

        # Step 5: Generate chapter summaries in batches
        chapters = manga_info.chapters
        chapter_summaries: dict[float, str] = {}

        for i in range(0, len(chapters), BATCH_SIZE):
            batch = chapters[i : i + BATCH_SIZE]

            # Check if we have content to summarize
            has_content = any(ch.content_text for ch in batch)

            if has_content:
                # Use batch summarization
                chapter_data = [
                    (ch.chapter_number, _truncate_content(ch.content_text))
                    for ch in batch
                ]
                batch_prompt = format_batch_chapters_prompt(
                    title=manga_info.title,
                    chapters=chapter_data,
                )

                logger.info(
                    "Generating batch chapter summaries",
                    extra={
                        "batch_start": i,
                        "batch_size": len(batch),
                    },
                )

                batch_response = deepinfra_client.generate_text(
                    system_prompt=REVIEW_SYSTEM_PROMPT,
                    user_prompt=batch_prompt,
                    max_tokens=2048,
                    temperature=0.7,
                )

                # Parse batch response
                batch_summaries = _parse_batch_response(
                    batch_response,
                    [ch.chapter_number for ch in batch],
                )
                chapter_summaries.update(batch_summaries)

            else:
                # Image-only manga - generate brief transitions
                for ch in batch:
                    prompt = format_image_only_prompt(
                        title=manga_info.title,
                        chapter_number=ch.chapter_number,
                        chapter_title=ch.title,
                        panel_count=1,  # We don't have panel count in ReviewChapterInfo
                        genres=manga_info.genres,
                    )

                    summary = deepinfra_client.generate_text(
                        system_prompt=REVIEW_SYSTEM_PROMPT,
                        user_prompt=prompt,
                        max_tokens=256,
                        temperature=0.7,
                    )
                    chapter_summaries[ch.chapter_number] = summary.strip()

        # Step 6: Create chapter segments
        for ch in chapters:
            summary = chapter_summaries.get(ch.chapter_number, "")
            if summary:
                # Find panel index for this chapter
                panel_idx = []
                ch_num_int = int(ch.chapter_number)
                for idx, key in enumerate(manifest.panel_s3_keys):
                    if f"chapter_{ch_num_int}_" in key:
                        panel_idx.append(idx)
                        break

                segments.append(
                    ReviewScriptSegment(
                        segment_type="chapter",
                        chapter_number=ch.chapter_number,
                        text=summary,
                        panel_indices=panel_idx,
                    )
                )

        logger.info(
            "Chapter segments generated",
            extra={"count": len(segments) - 1},  # Minus intro
        )

        # Step 7: Generate conclusion segment
        logger.info("Generating conclusion segment")

        # Create highlights from chapter summaries
        highlights_list = list(chapter_summaries.values())[:5]  # First 5 summaries
        highlights = "\n".join(f"- {h[:100]}..." for h in highlights_list if h)

        conclusion_prompt = format_conclusion_prompt(
            title=manga_info.title,
            author=manga_info.author,
            genres=manga_info.genres,
            chapters_reviewed=len(chapters),
            highlights=highlights or "Không có thông tin chi tiết",
        )

        conclusion_text = deepinfra_client.generate_text(
            system_prompt=REVIEW_SYSTEM_PROMPT,
            user_prompt=conclusion_prompt,
            max_tokens=1024,
            temperature=0.7,
        )

        segments.append(
            ReviewScriptSegment(
                segment_type="conclusion",
                chapter_number=None,
                text=conclusion_text.strip(),
                panel_indices=[],
            )
        )

        logger.info(
            "Conclusion segment generated",
            extra={"length": len(conclusion_text)},
        )

        # Step 8: Create script document
        script_document = ReviewScriptDocument(
            job_id=job_id,
            manga_title=manga_info.title,
            total_chapters=manga_info.total_chapters,
            segments=segments,
        )

        # Step 9: Store script in S3
        script_s3_key = f"jobs/{job_id}/review_script.json"
        logger.info(
            "Storing review script in S3",
            extra={"s3_key": script_s3_key},
        )
        s3_client.upload_json(script_document.model_dump(), script_s3_key)

        # Step 10: Update job status to tts
        db_client.update_job_status(
            job_id=job_id,
            status=JobStatus.tts,
            progress_pct=40,
        )

        logger.info(
            "Review script generation handler completed successfully",
            extra={
                "job_id": job_id,
                "segment_count": len(segments),
            },
        )

        return {
            "job_id": job_id,
            "script_s3_key": script_s3_key,
            "segment_count": len(segments),
            "continuation_needed": False,
        }

    except Exception as e:
        logger.error(
            "Review script generation handler failed",
            extra={
                "job_id": job_id,
                "error": str(e),
                "error_type": type(e).__name__,
            },
        )

        # Update job status to failed
        if job_id is not None:
            try:
                db_client.update_job_status(
                    job_id=job_id,
                    status=JobStatus.failed,
                    error_message=str(e),
                )
            except Exception as update_error:
                logger.error(
                    "Failed to update job status to failed",
                    extra={"job_id": job_id, "error": str(update_error)},
                )

        raise

    finally:
        # Clean up clients
        if deepinfra_client:
            try:
                deepinfra_client.close()
            except Exception:
                pass  # Ignore cleanup errors
