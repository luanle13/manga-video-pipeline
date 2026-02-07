"""Edge TTS wrapper for Vietnamese audio generation."""

import asyncio
import os
import tempfile
import time
from typing import BinaryIO

import edge_tts
from mutagen.mp3 import MP3

from src.common.logging_config import setup_logger

logger = setup_logger(__name__)


class EdgeTTSClient:
    """Client for generating Vietnamese audio using Edge TTS."""

    def __init__(self, voice_id: str = "vi-VN-HoaiMyNeural") -> None:
        """
        Initialize the Edge TTS client.

        Args:
            voice_id: Voice ID to use for generation (default: Vietnamese female voice).
        """
        self._voice_id = voice_id
        logger.info(
            "EdgeTTSClient initialized",
            extra={"voice_id": voice_id},
        )

    async def generate_audio(self, text: str, output_path: str) -> float:
        """
        Generate audio from text and save to file.

        Args:
            text: Text to convert to speech.
            output_path: Path to save the MP3 file.

        Returns:
            Duration of the audio in seconds.
        """
        # Handle empty text
        if not text or not text.strip():
            logger.warning("Empty text provided, skipping audio generation")
            return 0.0

        text_length = len(text)
        start_time = time.time()

        logger.info(
            "Generating audio",
            extra={
                "voice_id": self._voice_id,
                "text_length": text_length,
                "output_path": output_path,
            },
        )

        # Generate audio using edge-tts
        communicate = edge_tts.Communicate(text, self._voice_id)
        await communicate.save(output_path)

        # Calculate generation time
        generation_time = time.time() - start_time

        # Get audio duration
        duration = self._get_audio_duration(output_path)

        logger.info(
            "Audio generated successfully",
            extra={
                "voice_id": self._voice_id,
                "text_length": text_length,
                "duration_seconds": round(duration, 2),
                "generation_time_seconds": round(generation_time, 2),
                "output_path": output_path,
            },
        )

        return duration

    async def generate_audio_bytes(self, text: str) -> tuple[bytes, float]:
        """
        Generate audio from text and return as bytes.

        Args:
            text: Text to convert to speech.

        Returns:
            Tuple of (audio_bytes, duration_seconds).
        """
        # Handle empty text
        if not text or not text.strip():
            logger.warning("Empty text provided, returning empty bytes")
            return b"", 0.0

        logger.info(
            "Generating audio bytes",
            extra={
                "voice_id": self._voice_id,
                "text_length": len(text),
            },
        )

        # Generate to temporary file
        with tempfile.NamedTemporaryFile(
            suffix=".mp3", delete=False
        ) as temp_file:
            temp_path = temp_file.name

        try:
            # Generate audio
            duration = await self.generate_audio(text, temp_path)

            # Read bytes
            with open(temp_path, "rb") as f:
                audio_bytes = f.read()

            logger.info(
                "Audio bytes generated",
                extra={
                    "voice_id": self._voice_id,
                    "bytes_size": len(audio_bytes),
                    "duration_seconds": round(duration, 2),
                },
            )

            return audio_bytes, duration

        finally:
            # Clean up temp file
            try:
                os.unlink(temp_path)
            except Exception as e:
                logger.warning(
                    "Failed to delete temp file",
                    extra={"temp_path": temp_path, "error": str(e)},
                )

    @staticmethod
    def _get_audio_duration(file_path: str) -> float:
        """
        Get duration of an MP3 file.

        Args:
            file_path: Path to the MP3 file.

        Returns:
            Duration in seconds.
        """
        try:
            audio = MP3(file_path)
            return audio.info.length
        except Exception as e:
            logger.error(
                "Failed to read audio duration",
                extra={"file_path": file_path, "error": str(e)},
            )
            return 0.0

    @staticmethod
    async def get_available_vietnamese_voices() -> list[dict]:
        """
        Get list of available Vietnamese voices from Edge TTS.

        Returns:
            List of voice dictionaries with voice_id, name, and gender.
        """
        logger.info("Fetching available Vietnamese voices")

        try:
            # Get all voices
            all_voices = await edge_tts.list_voices()

            # Filter for Vietnamese voices (vi-VN locale)
            vietnamese_voices = []
            for voice in all_voices:
                locale = voice.get("Locale", "")
                if locale.startswith("vi-VN"):
                    vietnamese_voices.append(
                        {
                            "voice_id": voice.get("ShortName", ""),
                            "name": voice.get("FriendlyName", ""),
                            "gender": voice.get("Gender", ""),
                        }
                    )

            logger.info(
                "Vietnamese voices fetched",
                extra={"count": len(vietnamese_voices)},
            )

            return vietnamese_voices

        except Exception as e:
            logger.error(
                "Failed to fetch Vietnamese voices",
                extra={"error": str(e)},
            )
            return []


# Synchronous wrapper for asyncio contexts
def generate_audio_sync(
    text: str, output_path: str, voice_id: str = "vi-VN-HoaiMyNeural"
) -> float:
    """
    Synchronous wrapper for generate_audio.

    Args:
        text: Text to convert to speech.
        output_path: Path to save the MP3 file.
        voice_id: Voice ID to use.

    Returns:
        Duration of the audio in seconds.
    """
    client = EdgeTTSClient(voice_id=voice_id)
    return asyncio.run(client.generate_audio(text, output_path))


def generate_audio_bytes_sync(
    text: str, voice_id: str = "vi-VN-HoaiMyNeural"
) -> tuple[bytes, float]:
    """
    Synchronous wrapper for generate_audio_bytes.

    Args:
        text: Text to convert to speech.
        voice_id: Voice ID to use.

    Returns:
        Tuple of (audio_bytes, duration_seconds).
    """
    client = EdgeTTSClient(voice_id=voice_id)
    return asyncio.run(client.generate_audio_bytes(text))


def get_vietnamese_voices_sync() -> list[dict]:
    """
    Synchronous wrapper for get_available_vietnamese_voices.

    Returns:
        List of voice dictionaries.
    """
    return asyncio.run(EdgeTTSClient.get_available_vietnamese_voices())
