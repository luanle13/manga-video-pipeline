"""Main entry point for the video renderer running on EC2 Spot instances."""

import json
import os
import shutil
from pathlib import Path
from typing import Any

import boto3

from src.common.config import get_settings
from src.common.db import DynamoDBClient
from src.common.logging_config import setup_logger
from src.common.models import AudioManifest, JobStatus
from src.common.storage import S3Client
from src.renderer.audio_merger import AudioMerger
from src.renderer.compositor import VideoCompositor
from src.renderer.scene_builder import SceneBuilder
from src.renderer.spot_handler import (
    delete_checkpoint,
    load_checkpoint,
    register_spot_interruption_handler,
    save_checkpoint,
)

logger = setup_logger(__name__)

# Global state for checkpoint callback
_current_state: dict[str, Any] = {}


def get_checkpoint_callback() -> dict[str, Any]:
    """Return current checkpoint state."""
    return _current_state.copy()


def main() -> None:
    """
    Main entry point for the video renderer.

    Orchestrates the entire rendering process:
    1. Initialize components
    2. Load job data
    3. Download panels and audio
    4. Build scenes and render video
    5. Upload final video
    6. Clean up
    """
    job_id = None
    local_dir = None

    try:
        # Step 1: Read job_id from environment
        job_id = os.environ.get("JOB_ID")
        if not job_id:
            raise ValueError("JOB_ID environment variable not set")

        logger.info(
            "Starting video renderer",
            extra={"job_id": job_id},
        )

        # Step 2: Initialize config, logger, DB, S3
        logger.info("Initializing components")
        config = get_settings()
        db_client = DynamoDBClient(settings=config)
        s3_client = S3Client(settings=config)

        # Step 3: Register spot interruption handler
        register_spot_interruption_handler(
            job_id=job_id,
            s3_client=s3_client,
            checkpoint_callback=get_checkpoint_callback,
        )

        # Step 4: Load job record from DynamoDB
        logger.info("Loading job record", extra={"job_id": job_id})
        job_record = db_client.get_job(job_id)
        if not job_record:
            raise ValueError(f"Job {job_id} not found in database")

        logger.info(
            "Job record loaded",
            extra={
                "job_id": job_id,
                "status": job_record.status,
                "manga_title": job_record.manga_title,
            },
        )

        # Step 5: Load panel manifest from S3
        panel_manifest_key = f"jobs/{job_id}/panel_manifest.json"
        logger.info(
            "Loading panel manifest",
            extra={"s3_key": panel_manifest_key},
        )
        panel_manifest = s3_client.download_json(panel_manifest_key)
        if not panel_manifest:
            raise ValueError(f"Panel manifest not found at {panel_manifest_key}")

        # Step 6: Load audio manifest from S3
        audio_manifest_key = f"jobs/{job_id}/audio_manifest.json"
        logger.info(
            "Loading audio manifest",
            extra={"s3_key": audio_manifest_key},
        )
        audio_manifest_data = s3_client.download_json(audio_manifest_key)
        if not audio_manifest_data:
            raise ValueError(f"Audio manifest not found at {audio_manifest_key}")

        audio_manifest = AudioManifest(**audio_manifest_data)

        logger.info(
            "Manifests loaded",
            extra={
                "total_panels": panel_manifest.get("total_panels", 0),
                "total_audio_segments": len(audio_manifest.segments),
                "total_duration": audio_manifest.total_duration_seconds,
            },
        )

        # Step 7: Check for checkpoint to resume from
        checkpoint = load_checkpoint(job_id, s3_client)
        start_chunk = 0
        if checkpoint:
            start_chunk = checkpoint.get("last_completed_chunk", 0) + 1
            logger.info(
                "Resuming from checkpoint",
                extra={"start_chunk": start_chunk},
            )

        # Step 8: Update job status to "rendering"
        db_client.update_job_status(
            job_id=job_id,
            status=JobStatus.rendering,
            progress_pct=65,
        )

        # Step 9: Create local working directory
        local_dir = f"/tmp/render/{job_id}"
        os.makedirs(local_dir, exist_ok=True)
        logger.info("Created local working directory", extra={"path": local_dir})

        panels_dir = os.path.join(local_dir, "panels")
        audio_dir = os.path.join(local_dir, "audio")
        os.makedirs(panels_dir, exist_ok=True)
        os.makedirs(audio_dir, exist_ok=True)

        # Step 10: Download all panel images from S3
        logger.info("Downloading panel images from S3")
        panel_count = 0

        for chapter in panel_manifest.get("chapters", []):
            # Handle both formats: panel_keys (list of strings) and panels (list of objects)
            panel_keys = chapter.get("panel_keys", [])
            if not panel_keys:
                # Fallback to panels format with s3_key
                panel_keys = [p.get("s3_key") for p in chapter.get("panels", []) if p.get("s3_key")]

            for panel_s3_key in panel_keys:
                if not panel_s3_key:
                    continue

                # Download panel to local directory
                panel_filename = os.path.basename(panel_s3_key)
                local_panel_path = os.path.join(panels_dir, panel_filename)

                s3_client.download_file(panel_s3_key, local_panel_path)
                panel_count += 1

                if panel_count % 50 == 0:
                    logger.info(
                        f"Downloaded {panel_count} panels",
                        extra={"progress": f"{panel_count}/{panel_manifest.get('total_panels', 0)}"},
                    )

        logger.info(
            "All panels downloaded",
            extra={"total_panels": panel_count},
        )

        # Step 11: Download and merge all audio segments
        logger.info("Downloading and merging audio segments")
        audio_merger = AudioMerger()

        merged_audio_path, audio_duration = audio_merger.merge_from_s3(
            audio_manifest=audio_manifest,
            s3_client=s3_client,
            job_id=job_id,
            local_dir=audio_dir,
        )

        logger.info(
            "Audio merged successfully",
            extra={
                "path": merged_audio_path,
                "duration_seconds": audio_duration,
            },
        )

        # Step 12: Build scenes using SceneBuilder
        logger.info("Building scenes from panels and audio")
        scene_builder = SceneBuilder()
        scenes = scene_builder.build_scenes(
            panel_manifest=panel_manifest,
            audio_manifest=audio_manifest,
        )

        logger.info(
            "Scenes built successfully",
            extra={"total_scenes": len(scenes)},
        )

        # Update progress
        db_client.update_job_status(
            job_id=job_id,
            status=JobStatus.rendering,
            progress_pct=70,
        )

        # Step 13: Render video using VideoCompositor
        logger.info("Starting video rendering (chunked)")
        compositor = VideoCompositor(
            resolution=(1920, 1080),
            fps=24,
        )

        output_video_path = os.path.join(local_dir, "video.mp4")

        # Use chunked composition for memory efficiency
        # Chunk size of 100 scenes is reasonable for Spot instances
        compositor.compose_video_chunked(
            scenes=scenes,
            panel_dir=panels_dir,
            audio_path=merged_audio_path,
            output_path=output_video_path,
            chunk_size=100,
        )

        logger.info(
            "Video rendering complete",
            extra={
                "output_path": output_video_path,
                "file_size_mb": round(os.path.getsize(output_video_path) / (1024 * 1024), 2),
            },
        )

        # Step 14: Update job status to "uploading"
        db_client.update_job_status(
            job_id=job_id,
            status=JobStatus.uploading,
            progress_pct=85,
        )

        # Step 15: Upload rendered video to S3
        video_s3_key = f"jobs/{job_id}/video.mp4"
        logger.info(
            "Uploading video to S3",
            extra={"s3_key": video_s3_key},
        )

        s3_client.upload_file(output_video_path, video_s3_key)

        logger.info(
            "Video uploaded successfully",
            extra={"s3_key": video_s3_key},
        )

        # Step 16: Check manual review mode setting
        pipeline_settings = db_client.get_settings()
        manual_review_mode = pipeline_settings.manual_review_mode if pipeline_settings else False

        if manual_review_mode:
            # Manual review mode: pause for user review before YouTube upload
            logger.info(
                "Manual review mode enabled, setting status to awaiting_review",
                extra={"job_id": job_id},
            )
            db_client.update_job_status(
                job_id=job_id,
                status=JobStatus.awaiting_review,
                progress_pct=85,
            )
        else:
            # Auto mode: mark as completed (uploader will be triggered by Step Functions)
            db_client.update_job_status(
                job_id=job_id,
                status=JobStatus.completed,
                progress_pct=100,
            )

        # Step 17: Delete checkpoint if it exists
        delete_checkpoint(job_id, s3_client)

        # Step 18: Signal Step Functions task completion (if task token provided)
        task_token = os.environ.get("TASK_TOKEN")
        if task_token:
            logger.info("Signaling Step Functions task success")
            sfn_client = boto3.client("stepfunctions")

            output = {
                "job_id": job_id,
                "video_s3_key": video_s3_key,
                "status": "awaiting_review" if manual_review_mode else "completed",
                "manual_review_mode": manual_review_mode,
            }

            sfn_client.send_task_success(
                taskToken=task_token,
                output=json.dumps(output),
            )

            logger.info(
                "Step Functions task signaled successfully",
                extra={"manual_review_mode": manual_review_mode},
            )

        logger.info(
            "Video rendering completed successfully",
            extra={"job_id": job_id},
        )

    except Exception as e:
        logger.error(
            "Video rendering failed",
            extra={
                "job_id": job_id,
                "error": str(e),
            },
            exc_info=True,
        )

        # Update job status to failed
        if job_id:
            try:
                config = get_settings()
                db_client = DynamoDBClient(settings=config)
                db_client.update_job_status(
                    job_id=job_id,
                    status=JobStatus.failed,
                    error_message=str(e),
                )
            except Exception as update_error:
                logger.error(
                    "Failed to update job status",
                    extra={"error": str(update_error)},
                )

        # Signal Step Functions task failure (if task token provided)
        task_token = os.environ.get("TASK_TOKEN")
        if task_token:
            try:
                logger.info("Signaling Step Functions task failure")
                sfn_client = boto3.client("stepfunctions")

                sfn_client.send_task_failure(
                    taskToken=task_token,
                    error="RenderingError",
                    cause=str(e),
                )
            except Exception as sfn_error:
                logger.error(
                    "Failed to signal Step Functions",
                    extra={"error": str(sfn_error)},
                )

        raise

    finally:
        # Step 19: Clean up local /tmp/render/{job_id}/
        if local_dir and os.path.exists(local_dir):
            try:
                logger.info("Cleaning up local directory", extra={"path": local_dir})
                shutil.rmtree(local_dir)
                logger.info("Local directory cleaned up successfully")
            except Exception as cleanup_error:
                logger.warning(
                    "Failed to clean up local directory",
                    extra={"error": str(cleanup_error)},
                )


if __name__ == "__main__":
    main()
