"""Audio merger for concatenating TTS segments."""

import os
import subprocess
from pathlib import Path

from pydub import AudioSegment

from src.common.logging_config import setup_logger
from src.common.models import AudioManifest
from src.common.storage import S3Client

logger = setup_logger(__name__)


class AudioMerger:
    """Merger for concatenating audio segments into a single file."""

    def __init__(self) -> None:
        """Initialize the audio merger."""
        logger.info("AudioMerger initialized")

    def merge_audio_files(
        self,
        audio_paths: list[str],
        output_path: str,
        use_ffmpeg: bool = False,
    ) -> float:
        """
        Merge multiple audio files into a single file.

        Args:
            audio_paths: List of paths to audio files (in order).
            output_path: Path where merged audio will be saved.
            use_ffmpeg: If True, use FFmpeg for memory-efficient concatenation.
                       Recommended for long audio files (> 1 hour).

        Returns:
            Total duration of merged audio in seconds.
        """
        if not audio_paths:
            raise ValueError("No audio files provided for merging")

        logger.info(
            "Starting audio merge",
            extra={
                "num_segments": len(audio_paths),
                "output_path": output_path,
                "use_ffmpeg": use_ffmpeg,
            },
        )

        if use_ffmpeg:
            return self._merge_with_ffmpeg(audio_paths, output_path)
        else:
            return self._merge_with_pydub(audio_paths, output_path)

    def _merge_with_pydub(
        self,
        audio_paths: list[str],
        output_path: str,
    ) -> float:
        """
        Merge audio files using pydub (in-memory).

        Args:
            audio_paths: List of paths to audio files.
            output_path: Path where merged audio will be saved.

        Returns:
            Total duration in seconds.
        """
        logger.info("Merging audio with pydub")

        # Load first audio file
        combined = AudioSegment.from_mp3(audio_paths[0])

        # Concatenate remaining files
        for i, audio_path in enumerate(audio_paths[1:], start=1):
            audio = AudioSegment.from_mp3(audio_path)
            combined += audio

            if (i + 1) % 10 == 0:
                logger.info(
                    f"Processed {i + 1}/{len(audio_paths)} audio segments",
                    extra={"progress_pct": int((i + 1) / len(audio_paths) * 100)},
                )

        # Calculate duration in seconds
        duration_seconds = len(combined) / 1000.0

        # Export merged audio
        logger.info("Exporting merged audio")

        # Determine format from output path
        output_format = Path(output_path).suffix[1:]  # Remove leading dot
        if output_format not in ["mp3", "wav"]:
            output_format = "mp3"

        combined.export(
            output_path,
            format=output_format,
            bitrate="192k" if output_format == "mp3" else None,
        )

        file_size_mb = os.path.getsize(output_path) / (1024 * 1024)

        logger.info(
            "Audio merge complete",
            extra={
                "num_segments": len(audio_paths),
                "duration_seconds": round(duration_seconds, 2),
                "file_size_mb": round(file_size_mb, 2),
                "output_path": output_path,
            },
        )

        return duration_seconds

    def _merge_with_ffmpeg(
        self,
        audio_paths: list[str],
        output_path: str,
    ) -> float:
        """
        Merge audio files using FFmpeg (streaming, memory-efficient).

        Args:
            audio_paths: List of paths to audio files.
            output_path: Path where merged audio will be saved.

        Returns:
            Total duration in seconds.
        """
        logger.info("Merging audio with FFmpeg (memory-efficient)")

        # Create concat file for FFmpeg
        concat_file = output_path + ".concat.txt"
        with open(concat_file, "w") as f:
            for audio_path in audio_paths:
                # FFmpeg concat format
                f.write(f"file '{audio_path}'\n")

        try:
            # Concatenate using FFmpeg
            subprocess.run(
                [
                    "ffmpeg",
                    "-f",
                    "concat",
                    "-safe",
                    "0",
                    "-i",
                    concat_file,
                    "-c",
                    "copy",  # No re-encoding (fast)
                    output_path,
                ],
                check=True,
                capture_output=True,
            )

            # Get duration using ffprobe
            result = subprocess.run(
                [
                    "ffprobe",
                    "-v",
                    "error",
                    "-show_entries",
                    "format=duration",
                    "-of",
                    "default=noprint_wrappers=1:nokey=1",
                    output_path,
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            duration_seconds = float(result.stdout.strip())

            file_size_mb = os.path.getsize(output_path) / (1024 * 1024)

            logger.info(
                "Audio merge complete (FFmpeg)",
                extra={
                    "num_segments": len(audio_paths),
                    "duration_seconds": round(duration_seconds, 2),
                    "file_size_mb": round(file_size_mb, 2),
                    "output_path": output_path,
                },
            )

            return duration_seconds

        finally:
            # Clean up concat file
            try:
                os.unlink(concat_file)
            except Exception:
                pass

    def merge_from_s3(
        self,
        audio_manifest: AudioManifest,
        s3_client: S3Client,
        job_id: str,
        local_dir: str,
    ) -> tuple[str, float]:
        """
        Download audio segments from S3 and merge them.

        Args:
            audio_manifest: Audio manifest with segment information.
            s3_client: S3 client for downloading files.
            job_id: Job ID for naming output file.
            local_dir: Local directory for downloading and storing files.

        Returns:
            Tuple of (merged_file_path, total_duration_seconds).
        """
        logger.info(
            "Starting audio merge from S3",
            extra={
                "job_id": job_id,
                "num_segments": len(audio_manifest.segments),
                "total_duration": audio_manifest.total_duration_seconds,
            },
        )

        # Create local directory if it doesn't exist
        os.makedirs(local_dir, exist_ok=True)

        # Download all audio segments
        audio_paths = []
        for idx, segment in enumerate(audio_manifest.segments):
            local_path = os.path.join(
                local_dir, f"segment_{segment.index:04d}.mp3"
            )

            logger.debug(
                f"Downloading segment {idx + 1}/{len(audio_manifest.segments)}",
                extra={
                    "segment_index": segment.index,
                    "s3_key": segment.s3_key,
                },
            )

            s3_client.download_file(segment.s3_key, local_path)
            audio_paths.append(local_path)

            if (idx + 1) % 10 == 0:
                logger.info(
                    f"Downloaded {idx + 1}/{len(audio_manifest.segments)} segments",
                    extra={"progress_pct": int((idx + 1) / len(audio_manifest.segments) * 100)},
                )

        logger.info("All segments downloaded, starting merge")

        # Merge audio files
        output_path = os.path.join(local_dir, f"{job_id}_merged.mp3")

        # Use FFmpeg for large files (> 1 hour or > 100 segments)
        use_ffmpeg = (
            audio_manifest.total_duration_seconds > 3600
            or len(audio_manifest.segments) > 100
        )

        duration = self.merge_audio_files(
            audio_paths=audio_paths,
            output_path=output_path,
            use_ffmpeg=use_ffmpeg,
        )

        # Clean up individual segment files
        logger.info("Cleaning up downloaded segments")
        for audio_path in audio_paths:
            try:
                os.unlink(audio_path)
            except Exception as e:
                logger.warning(
                    "Failed to delete segment file",
                    extra={"file": audio_path, "error": str(e)},
                )

        logger.info(
            "Audio merge from S3 complete",
            extra={
                "job_id": job_id,
                "output_path": output_path,
                "duration_seconds": round(duration, 2),
            },
        )

        return output_path, duration
