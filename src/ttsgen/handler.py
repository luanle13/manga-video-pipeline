"""Lambda handler for TTS generation."""

import asyncio
import time
import uuid
from typing import Any

from src.common.config import get_settings
from src.common.db import DynamoDBClient
from src.common.logging_config import set_correlation_id, setup_logger
from src.common.models import AudioManifest, JobStatus, ScriptDocument
from src.common.storage import S3Client
from src.ttsgen.segment_processor import TTSSegmentProcessor
from src.ttsgen.tts_client import EdgeTTSClient

logger = setup_logger(__name__)

# Lambda timeout safety: reserve 3 minutes for cleanup and safety margin
# If Lambda timeout is 900s (15 min), we target processing for 12 minutes
LAMBDA_TIMEOUT_SECONDS = 900
PROCESSING_TIME_LIMIT_SECONDS = LAMBDA_TIMEOUT_SECONDS - 180  # 12 minutes

# Estimate: average segment takes ~5 seconds to process (TTS + upload)
ESTIMATED_SECONDS_PER_SEGMENT = 5


def handler(event: dict, context: Any) -> dict:
    """
    Lambda handler for generating audio from script segments.

    Args:
        event: Lambda event with job_id, script_s3_key, and optional segment_offset.
        context: Lambda context.

    Returns:
        Result dict with job_id, audio_manifest_s3_key, total_duration_seconds,
        and optionally continuation_needed flag.
    """
    # Generate correlation ID for request tracing
    correlation_id = str(uuid.uuid4())
    set_correlation_id(correlation_id)

    job_id = event.get("job_id")
    script_s3_key = event.get("script_s3_key")
    segment_offset = event.get("segment_offset", 0)

    logger.info(
        "TTS generation handler started",
        extra={
            "correlation_id": correlation_id,
            "job_id": job_id,
            "script_s3_key": script_s3_key,
            "segment_offset": segment_offset,
        },
    )

    # Initialize configuration and clients
    settings = get_settings()
    db_client = DynamoDBClient(settings)
    s3_client = S3Client(settings)

    start_time = time.time()

    try:
        # Step 1: Load job record from DynamoDB
        logger.info("Loading job record", extra={"job_id": job_id})
        job_record = db_client.get_job(job_id)

        if not job_record:
            raise ValueError(f"Job not found: {job_id}")

        # Step 2: Load pipeline settings to get voice_id
        logger.info("Loading pipeline settings")
        pipeline_settings = db_client.get_settings()
        voice_id = pipeline_settings.voice_id

        logger.info(
            "Pipeline settings loaded",
            extra={"voice_id": voice_id},
        )

        # Step 3: Load script from S3
        logger.info(
            "Loading script from S3",
            extra={"s3_key": script_s3_key},
        )
        script_data = s3_client.download_json(script_s3_key)

        # Step 4: Parse into ScriptDocument
        script_document = ScriptDocument(**script_data)
        total_segments = len(script_document.segments)

        logger.info(
            "Script loaded",
            extra={
                "job_id": job_id,
                "total_segments": total_segments,
                "segment_offset": segment_offset,
            },
        )

        # Step 5: Determine how many segments to process
        # Calculate maximum segments we can process within time limit
        max_segments_to_process = (
            PROCESSING_TIME_LIMIT_SECONDS // ESTIMATED_SECONDS_PER_SEGMENT
        )

        segments_remaining = total_segments - segment_offset
        segments_to_process = min(segments_remaining, max_segments_to_process)

        # If this is a continuation, load existing manifest
        existing_manifest: AudioManifest | None = None
        if segment_offset > 0:
            try:
                logger.info("Loading existing audio manifest for continuation")
                manifest_key = f"jobs/{job_id}/audio_manifest.json"
                manifest_data = s3_client.download_json(manifest_key)
                existing_manifest = AudioManifest(**manifest_data)
            except Exception as e:
                logger.warning(
                    "Could not load existing manifest for continuation",
                    extra={"error": str(e)},
                )

        logger.info(
            "Processing plan",
            extra={
                "total_segments": total_segments,
                "segment_offset": segment_offset,
                "segments_to_process": segments_to_process,
                "max_segments_to_process": max_segments_to_process,
            },
        )

        # Step 6: Initialize EdgeTTSClient with voice_id
        tts_client = EdgeTTSClient(voice_id=voice_id)

        # Step 7: Initialize TTSSegmentProcessor
        segment_processor = TTSSegmentProcessor(
            tts_client=tts_client,
            s3_client=s3_client,
        )

        # Step 8: Create a partial script for processing
        segments_to_process_list = script_document.segments[
            segment_offset : segment_offset + segments_to_process
        ]

        partial_script = ScriptDocument(
            job_id=job_id,
            manga_title=script_document.manga_title,
            segments=segments_to_process_list,
        )

        logger.info(
            "Starting TTS processing",
            extra={
                "segments_to_process": len(segments_to_process_list),
                "start_index": segment_offset,
            },
        )

        # Step 9: Process segments using asyncio.run()
        # Note: We need to adjust indices for continuation
        manifest = asyncio.run(
            _process_segments_with_offset(
                segment_processor=segment_processor,
                script=partial_script,
                job_id=job_id,
                segment_offset=segment_offset,
                existing_manifest=existing_manifest,
            )
        )

        elapsed_time = time.time() - start_time
        logger.info(
            "TTS processing complete",
            extra={
                "job_id": job_id,
                "segments_processed": len(manifest.segments),
                "total_duration_seconds": manifest.total_duration_seconds,
                "elapsed_time_seconds": round(elapsed_time, 2),
            },
        )

        # Step 10: Determine if continuation is needed
        continuation_needed = (segment_offset + segments_to_process) < total_segments
        next_offset = segment_offset + segments_to_process if continuation_needed else None

        # Step 11: Update job status
        if continuation_needed:
            # Still more segments to process
            logger.info(
                "Continuation needed for remaining segments",
                extra={
                    "next_offset": next_offset,
                    "segments_remaining": total_segments - (segment_offset + segments_to_process),
                },
            )
            # Progress is proportional to segments processed
            progress_pct = int(40 + (next_offset / total_segments) * 20)
            db_client.update_job_status(
                job_id=job_id,
                status=JobStatus.tts,
                progress_pct=progress_pct,
            )
        else:
            # All segments processed
            logger.info("All segments processed, moving to rendering stage")
            db_client.update_job_status(
                job_id=job_id,
                status=JobStatus.rendering,
                progress_pct=60,
            )

        # Step 12: Prepare result
        result = {
            "job_id": job_id,
            "audio_manifest_s3_key": f"jobs/{job_id}/audio_manifest.json",
            "total_duration_seconds": manifest.total_duration_seconds,
            "segments_processed": len(manifest.segments),
            "total_segments": total_segments,
        }

        if continuation_needed:
            result["continuation_needed"] = True
            result["next_segment_offset"] = next_offset
        else:
            result["continuation_needed"] = False

        logger.info(
            "TTS generation handler completed successfully",
            extra={"job_id": job_id, "result": result},
        )

        return result

    except Exception as e:
        logger.error(
            "TTS generation handler failed",
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


async def _process_segments_with_offset(
    segment_processor: TTSSegmentProcessor,
    script: ScriptDocument,
    job_id: str,
    segment_offset: int,
    existing_manifest: AudioManifest | None,
) -> AudioManifest:
    """
    Process segments with offset adjustment for continuation.

    Args:
        segment_processor: TTS segment processor.
        script: Script document (partial) to process.
        job_id: Job ID.
        segment_offset: Starting offset for segment indices.
        existing_manifest: Existing manifest from previous continuation (if any).

    Returns:
        Updated audio manifest with all segments (including previous ones).
    """
    # Process segments, adjusting indices based on offset
    audio_segments = []
    cumulative_duration = existing_manifest.total_duration_seconds if existing_manifest else 0.0

    for local_index, segment in enumerate(script.segments):
        global_index = segment_offset + local_index
        audio_segment = await segment_processor.process_segment(
            segment, job_id, global_index
        )
        audio_segments.append(audio_segment)
        cumulative_duration += audio_segment.duration_seconds

        logger.info(
            f"TTS segment {global_index + 1}/{segment_offset + len(script.segments)} done ({round(audio_segment.duration_seconds, 2)}s)",
            extra={
                "job_id": job_id,
                "segment_index": global_index,
                "segment_duration": round(audio_segment.duration_seconds, 2),
                "cumulative_duration": round(cumulative_duration, 2),
            },
        )

    # Merge with existing manifest if continuation
    if existing_manifest:
        all_segments = existing_manifest.segments + audio_segments
    else:
        all_segments = audio_segments

    # Build complete manifest
    manifest = AudioManifest(
        job_id=job_id,
        segments=all_segments,
        total_duration_seconds=cumulative_duration,
    )

    # Store manifest in S3 (overwrites previous version)
    manifest_key = f"jobs/{job_id}/audio_manifest.json"
    segment_processor._s3_client.upload_json(
        data=manifest.model_dump(),
        s3_key=manifest_key,
    )

    logger.info(
        "Audio manifest updated",
        extra={
            "job_id": job_id,
            "total_segments": len(all_segments),
            "total_duration": round(cumulative_duration, 2),
            "manifest_key": manifest_key,
        },
    )

    return manifest
