from __future__ import annotations
import asyncio
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path
import logging
from typing import List


@dataclass(slots=True)
class TTSResult:
    """Result of text-to-speech conversion."""
    audio_path: Path
    duration_seconds: float
    voice: str


class TextToSpeechService:
    """Text-to-speech service using OpenAI TTS API."""
    
    def __init__(self, api_key: str | None = None):
        """
        Initialize the TextToSpeechService.
        
        Args:
            api_key: OpenAI API key. If None, will be read from environment variables.
        """
        from openai import AsyncOpenAI
        self.client = AsyncOpenAI(api_key=api_key)
    
    def _split_text(self, text: str, language: str, max_length: int = 4096) -> List[str]:
        """Split text into chunks at sentence boundaries to handle long text.

        Args:
            text: Input text to split
            language: Language code ("en" or "vn") to handle different sentence endings
            max_length: Maximum length per chunk (default OpenAI TTS limit is 4096)

        Returns:
            List of text chunks
        """
        # Handle different sentence endings for different languages
        if language == "vn":
            # Vietnamese uses different punctuation
            sentences = re.split(r'[.!?।।？！]+', text)
        else:
            # Default to English punctuation
            sentences = re.split(r'[.!?]+', text)

        chunks = []
        current_chunk = ""

        for sentence in sentences:
            # Add the sentence separator back
            sentence = sentence.strip()
            if not sentence:
                continue

            # Check if adding this sentence would exceed the limit
            if len(current_chunk) + len(sentence) + 1 <= max_length:
                if language == "vn":
                    current_chunk += sentence + ". "
                else:
                    current_chunk += sentence + ". "
            else:
                # If current chunk is not empty, save it and start a new one
                if current_chunk.strip():
                    chunks.append(current_chunk.strip())

                # If the sentence itself is longer than max_length, we need to split it further
                if len(sentence) > max_length:
                    # Split the long sentence into smaller parts
                    parts = [sentence[i:i+max_length] for i in range(0, len(sentence), max_length)]
                    for part in parts[:-1]:
                        chunks.append(part)
                    if language == "vn":
                        current_chunk = parts[-1] + ". "
                    else:
                        current_chunk = parts[-1] + ". "
                else:
                    if language == "vn":
                        current_chunk = sentence + ". "
                    else:
                        current_chunk = sentence + ". "

        # Add the last chunk if it's not empty
        if current_chunk.strip():
            chunks.append(current_chunk.strip())

        return chunks
    
    async def _get_audio_duration(self, audio_path: Path) -> float:
        """Get the duration of an audio file using ffprobe.
        
        Args:
            audio_path: Path to the audio file
            
        Returns:
            Duration in seconds
        """
        try:
            result = await asyncio.create_subprocess_exec(
                'ffprobe',
                '-v', 'quiet',
                '-show_entries', 'format=duration',
                '-of', 'csv=p=0',
                str(audio_path),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await result.communicate()

            if result.returncode == 0:
                duration = float(stdout.decode().strip())
                return duration
            else:
                logging.warning(f"ffprobe failed to get duration: {stderr.decode()}")
                # If ffprobe fails, return 0.0 as fallback
                return 0.0
        except FileNotFoundError:
            logging.warning("ffprobe not found. Please install ffmpeg.")
            return 0.0
        except Exception as e:
            logging.warning(f"Error getting audio duration: {e}")
            return 0.0
    
    async def _concatenate_audio_files(self, input_files: List[Path], output_path: Path) -> None:
        """Concatenate multiple audio files into a single file using FFmpeg.
        
        Args:
            input_files: List of input audio file paths
            output_path: Output audio file path
        """
        # Create a temporary file listing all input files
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as temp_list:
            for file_path in input_files:
                temp_list.write(f"file '{file_path}'\n")
            temp_list_path = temp_list.name
        
        try:
            # Run FFmpeg to concatenate files
            result = await asyncio.create_subprocess_exec(
                'ffmpeg',
                '-f', 'concat',
                '-safe', '0',
                '-i', temp_list_path,
                '-c', 'copy',
                str(output_path),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await result.communicate()

            if result.returncode != 0:
                raise Exception(f"FFmpeg failed to concatenate files: {stderr.decode()}")
        finally:
            # Clean up the temporary file
            Path(temp_list_path).unlink()
    
    async def generate_audio(
        self,
        text: str,
        output_path: Path,
        language: str,
        voice: str = "alloy",
        speed: float = 1.0
    ) -> TTSResult:
        """
        Generate audio from text using OpenAI TTS API.
        
        Args:
            text: Input text to convert to speech
            output_path: Path to save the generated audio (MP3 format)
            language: Language code ("en" or "vn")
            voice: Voice to use (default "alloy")
            speed: Speed multiplier (default 1.0)
            
        Returns:
            TTSResult object with audio path, duration, and voice
        """
        # Validate language
        if language not in ["en", "vn"]:
            raise ValueError(f"Unsupported language: {language}. Supported languages are 'en' and 'vn'.")
        
        # Define available voices for OpenAI TTS
        valid_voices = ["alloy", "echo", "fable", "onyx", "nova", "shimmer"]
        if voice not in valid_voices:
            raise ValueError(f"Invalid voice: {voice}. Valid voices are: {valid_voices}")
        
        # Check if text is too long and needs to be chunked
        if len(text) > 4096:
            # Split text into chunks based on language
            text_chunks = self._split_text(text, language, 4096)
            
            # Create temporary files for each chunk
            temp_audio_files = []
            temp_dir = Path(tempfile.mkdtemp())
            
            try:
                for i, chunk in enumerate(text_chunks):
                    temp_audio_path = temp_dir / f"chunk_{i}.mp3"
                    temp_audio_files.append(temp_audio_path)
                    
                    # Generate audio for this chunk
                    response = await self.client.audio.speech.create(
                        model="tts-1",
                        voice=voice,
                        input=chunk,
                        response_format="mp3",
                        speed=speed
                    )
                    
                    # Save the audio to the temporary file
                    with open(temp_audio_path, 'wb') as f:
                        async for chunk in response.iter_bytes():
                            f.write(chunk)
                
                # Concatenate all temporary audio files into the final output
                await self._concatenate_audio_files(temp_audio_files, output_path)
            finally:
                # Clean up temporary files
                for temp_file in temp_audio_files:
                    if temp_file.exists():
                        temp_file.unlink()
                # Remove temporary directory
                temp_dir.rmdir()
        else:
            # Generate audio for the entire text in one request
            await self._generate_single_audio(text, output_path, voice, speed)

        # Get the duration of the generated audio
        duration = await self._get_audio_duration(output_path)

        return TTSResult(
            audio_path=output_path,
            duration_seconds=duration,
            voice=voice
        )

    async def _generate_single_audio(self, text: str, output_path: Path, voice: str, speed: float):
        """Generate a single audio file from text using OpenAI TTS API.

        Args:
            text: Input text to convert to speech
            output_path: Path to save the generated audio
            voice: Voice to use
            speed: Speed multiplier
        """
        response = await self.client.audio.speech.create(
            model="tts-1",
            voice=voice,
            input=text,
            response_format="mp3",
            speed=speed
        )

        # Save the audio to the output file
        with open(output_path, 'wb') as f:
            async for chunk in response.iter_bytes():
                f.write(chunk)


# For backward compatibility or synchronous use
def generate_audio(
    text: str,
    output_path: Path,
    language: str,
    voice: str = "alloy",
    speed: float = 1.0
) -> TTSResult:
    """Synchronous version of the generate_audio method."""
    import os
    from openai import OpenAI
    
    api_key = os.getenv("OPENAI_API_KEY")
    client = OpenAI(api_key=api_key)
    
    # For sync version, use the sync OpenAI client directly
    # This is different from the async version above
    # For consistency with the async implementation, we'll create a temporary async service
    service = TextToSpeechService(api_key=api_key)
    
    # Run the async function in a new event loop
    try:
        loop = asyncio.get_running_loop()
        
        # If already in an event loop, we need to run in a separate thread
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future = executor.submit(
                lambda: asyncio.run(
                    service.generate_audio(
                        text, output_path, language, voice, speed
                    )
                )
            )
            return future.result()
    except RuntimeError:
        # No event loop running, safe to use asyncio.run
        return asyncio.run(service.generate_audio(
            text, output_path, language, voice, speed
        ))