"""TTS segment processor for converting script segments to audio files."""

import asyncio
import tempfile
from pathlib import Path

from src.common.logging_config import setup_logger
from src.common.models import AudioManifest, AudioSegment, ScriptDocument, ScriptSegment
from src.common.storage import S3Client
from src.ttsgen.tts_client import EdgeTTSClient

logger = setup_logger(__name__)


class TTSSegmentProcessor:
    """Processor for converting script segments to audio files."""

    def __init__(self, tts_client: EdgeTTSClient, s3_client: S3Client) -> None:
        """
        Initialize the TTS segment processor.

        Args:
            tts_client: Edge TTS client for audio generation.
            s3_client: S3 client for file uploads.
        """
        self._tts_client = tts_client
        self._s3_client = s3_client
        logger.info("TTSSegmentProcessor initialized")

    def split_long_text(self, text: str, max_chars: int = 3000) -> list[str]:
        """
        Split long text into chunks at sentence boundaries.

        Edge TTS may have limits on text length. This method splits text
        on Vietnamese sentence boundaries (period ".") to stay under the limit.

        Args:
            text: Text to split.
            max_chars: Maximum characters per chunk (default: 3000).

        Returns:
            List of text chunks, each under max_chars.
        """
        # Handle empty or whitespace-only text
        if not text or not text.strip():
            return []

        # If text is already short enough, return as-is
        if len(text) <= max_chars:
            return [text]

        chunks: list[str] = []
        current_chunk = ""

        # Split on sentence boundaries (Vietnamese period ".")
        sentences = text.split(".")

        for i, sentence in enumerate(sentences):
            # Add back the period (except for last sentence if it was empty)
            if i < len(sentences) - 1 or sentence.strip():
                sentence_with_period = sentence + "."
            else:
                sentence_with_period = sentence

            # If adding this sentence would exceed limit
            if current_chunk and len(current_chunk) + len(sentence_with_period) > max_chars:
                # Save current chunk and start new one
                chunks.append(current_chunk.strip())
                current_chunk = sentence_with_period
            else:
                # Add to current chunk
                current_chunk += sentence_with_period

        # Add final chunk if not empty
        if current_chunk.strip():
            chunks.append(current_chunk.strip())

        logger.info(
            "Long text split into chunks",
            extra={
                "original_length": len(text),
                "num_chunks": len(chunks),
                "max_chars": max_chars,
            },
        )

        return chunks

    async def process_segment(
        self, segment: ScriptSegment, job_id: str, index: int
    ) -> AudioSegment:
        """
        Process a single script segment to generate audio.

        Args:
            segment: Script segment to process.
            job_id: Job ID for S3 key generation.
            index: Segment index for naming.

        Returns:
            AudioSegment with S3 key and duration.

        Raises:
            Exception: If audio generation fails after retries.
        """
        logger.info(
            "Processing segment",
            extra={
                "job_id": job_id,
                "index": index,
                "text_length": len(segment.text),
                "chapter": segment.chapter,
            },
        )

        # Split text if it's too long
        text_chunks = self.split_long_text(segment.text)

        # Generate audio for each chunk with retries
        audio_parts: list[tuple[bytes, float]] = []
        total_duration = 0.0

        for chunk_idx, chunk in enumerate(text_chunks):
            retries = 2
            last_error = None

            for attempt in range(retries + 1):
                try:
                    audio_bytes, duration = await self._tts_client.generate_audio_bytes(chunk)
                    audio_parts.append((audio_bytes, duration))
                    total_duration += duration

                    logger.info(
                        "Chunk audio generated",
                        extra={
                            "job_id": job_id,
                            "index": index,
                            "chunk_idx": chunk_idx,
                            "duration": round(duration, 2),
                            "attempt": attempt + 1,
                        },
                    )
                    break

                except Exception as e:
                    last_error = e
                    if attempt < retries:
                        wait_time = (attempt + 1) * 2
                        logger.warning(
                            "TTS generation failed, retrying",
                            extra={
                                "job_id": job_id,
                                "index": index,
                                "chunk_idx": chunk_idx,
                                "attempt": attempt + 1,
                                "error": str(e),
                                "retry_after_seconds": wait_time,
                            },
                        )
                        await asyncio.sleep(wait_time)
                    else:
                        logger.error(
                            "TTS generation failed after all retries, skipping segment",
                            extra={
                                "job_id": job_id,
                                "index": index,
                                "chunk_idx": chunk_idx,
                                "error": str(e),
                            },
                        )
                        # Return a silent segment instead of crashing
                        s3_key = f"jobs/{job_id}/audio/{index:04d}.mp3"
                        return AudioSegment(
                            index=index,
                            s3_key=s3_key,
                            duration_seconds=0.0,
                            chapter=segment.chapter,
                            panel_start=segment.panel_start,
                            panel_end=segment.panel_end,
                        )

        # Concatenate audio parts if multiple chunks
        if len(audio_parts) == 1:
            final_audio_bytes = audio_parts[0][0]
        else:
            # For multiple chunks, we need to concatenate the MP3 files
            # This is a simple approach - write to temp files and use pydub
            final_audio_bytes = await self._concatenate_audio_chunks(audio_parts)

        # Upload to S3
        s3_key = f"jobs/{job_id}/audio/{index:04d}.mp3"
        self._s3_client.upload_bytes(
            data=final_audio_bytes,
            s3_key=s3_key,
            content_type="audio/mpeg",
        )

        logger.info(
            "Segment processed successfully",
            extra={
                "job_id": job_id,
                "index": index,
                "s3_key": s3_key,
                "duration": round(total_duration, 2),
                "num_chunks": len(text_chunks),
            },
        )

        return AudioSegment(
            index=index,
            s3_key=s3_key,
            duration_seconds=total_duration,
            chapter=segment.chapter,
            panel_start=segment.panel_start,
            panel_end=segment.panel_end,
        )

    async def _concatenate_audio_chunks(
        self, audio_parts: list[tuple[bytes, float]]
    ) -> bytes:
        """
        Concatenate multiple audio chunks into a single MP3.

        Args:
            audio_parts: List of (audio_bytes, duration) tuples.

        Returns:
            Concatenated audio as bytes.
        """
        try:
            from pydub import AudioSegment as PydubAudioSegment

            # Load all audio chunks
            audio_segments = []
            for audio_bytes, _ in audio_parts:
                with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as temp_file:
                    temp_file.write(audio_bytes)
                    temp_path = temp_file.name

                try:
                    segment = PydubAudioSegment.from_mp3(temp_path)
                    audio_segments.append(segment)
                finally:
                    Path(temp_path).unlink(missing_ok=True)

            # Concatenate all segments
            combined = audio_segments[0]
            for segment in audio_segments[1:]:
                combined += segment

            # Export to bytes
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as temp_file:
                temp_path = temp_file.name
                combined.export(temp_path, format="mp3")

            try:
                with open(temp_path, "rb") as f:
                    return f.read()
            finally:
                Path(temp_path).unlink(missing_ok=True)

        except ImportError:
            # If pydub is not available, just return the first chunk
            logger.warning(
                "pydub not available, using first chunk only",
                extra={"num_chunks": len(audio_parts)},
            )
            return audio_parts[0][0]

    async def process_all_segments(
        self, script: ScriptDocument, job_id: str
    ) -> AudioManifest:
        """
        Process all segments in a script document.

        Args:
            script: Script document with segments to process.
            job_id: Job ID for tracking.

        Returns:
            AudioManifest with all processed segments.
        """
        total_segments = len(script.segments)
        logger.info(
            "Starting segment processing",
            extra={
                "job_id": job_id,
                "total_segments": total_segments,
            },
        )

        audio_segments: list[AudioSegment] = []
        cumulative_duration = 0.0

        # Process each segment sequentially (Edge TTS may rate-limit parallel)
        for index, segment in enumerate(script.segments):
            audio_segment = await self.process_segment(segment, job_id, index)
            audio_segments.append(audio_segment)
            cumulative_duration += audio_segment.duration_seconds

            logger.info(
                f"TTS segment {index + 1}/{total_segments} done ({round(audio_segment.duration_seconds, 2)}s)",
                extra={
                    "job_id": job_id,
                    "segment_index": index,
                    "segment_duration": round(audio_segment.duration_seconds, 2),
                    "cumulative_duration": round(cumulative_duration, 2),
                },
            )

        # Build manifest
        manifest = AudioManifest(
            job_id=job_id,
            segments=audio_segments,
            total_duration_seconds=cumulative_duration,
        )

        # Store manifest in S3
        manifest_key = f"jobs/{job_id}/audio_manifest.json"
        self._s3_client.upload_json(
            data=manifest.model_dump(),
            s3_key=manifest_key,
        )

        logger.info(
            "All segments processed and manifest stored",
            extra={
                "job_id": job_id,
                "total_segments": total_segments,
                "total_duration": round(cumulative_duration, 2),
                "manifest_key": manifest_key,
            },
        )

        return manifest
