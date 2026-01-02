import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from pathlib import Path
from dataclasses import dataclass
import tempfile


@dataclass
class MockTTSResult:
    """Mock class for TTSResult."""
    audio_path: Path
    duration_seconds: float
    voice: str


class TestTextToSpeechService:
    """Test cases for TextTo Speech service."""
    
    @pytest.mark.asyncio
    async def test_generate_audio_happy_path(self):
        """Test the generate_audio function with valid inputs."""
        with patch('openai.AsyncOpenAI') as mock_client:
            mock_instance = AsyncMock()
            
            # Mock the audio.speech.create method to return a stream
            async def mock_iter_bytes():
                # Create a simple mock audio content
                yield b'mock_audio_content'
            
            mock_response = AsyncMock()
            mock_response.iter_bytes.return_value = mock_iter_bytes()
            mock_instance.audio.speech.create.return_value = mock_response
            mock_client.return_value = mock_instance
            
            from src.ai.tts import TextToSpeechService
            tts = TextToSpeechService(api_key='test_key')
            
            with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as temp_file:
                output_path = Path(temp_file.name)
            
            try:
                result = await tts.generate_audio(
                    text="This is a test audio generation.",
                    output_path=output_path,
                    language="en",
                    voice="alloy",
                    speed=1.0
                )
                
                # Verify the result
                assert isinstance(result, MockTTSResult) or hasattr(result, 'audio_path')
                assert result.audio_path == output_path
                assert result.voice == "alloy"
                
                # Verify the API was called correctly
                mock_instance.audio.speech.create.assert_called_once_with(
                    model="tts-1",
                    voice="alloy",
                    input="This is a test audio generation.",
                    response_format="mp3",
                    speed=1.0
                )
                
                # Verify the file was created
                assert output_path.exists()
                
            finally:
                # Clean up
                if output_path.exists():
                    output_path.unlink()
    
    @pytest.mark.asyncio
    async def test_generate_audio_with_different_voices(self):
        """Test the generate_audio function with different voices."""
        with patch('openai.AsyncOpenAI') as mock_client:
            mock_instance = AsyncMock()
            
            async def mock_iter_bytes():
                yield b'mock_audio_content'
            
            mock_response = AsyncMock()
            mock_response.iter_bytes.return_value = mock_iter_bytes()
            mock_instance.audio.speech.create.return_value = mock_response
            mock_client.return_value = mock_instance
            
            from src.ai.tts import TextToSpeechService
            tts = TextToSpeechService(api_key='test_key')
            
            voices = ["alloy", "echo", "fable", "onyx", "nova", "shimmer"]
            
            for voice in voices:
                with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as temp_file:
                    output_path = Path(temp_file.name)
                
                try:
                    result = await tts.generate_audio(
                        text="Testing voice: " + voice,
                        output_path=output_path,
                        language="en",
                        voice=voice,
                        speed=1.0
                    )
                    
                    assert result.voice == voice
                    mock_instance.audio.speech.create.assert_called_with(
                        model="tts-1",
                        voice=voice,
                        input="Testing voice: " + voice,
                        response_format="mp3",
                        speed=1.0
                    )
                    
                finally:
                    # Clean up
                    if output_path.exists():
                        output_path.unlink()
    
    @pytest.mark.asyncio
    async def test_generate_audio_with_vietnamese_language(self):
        """Test the generate_audio function with Vietnamese text."""
        with patch('openai.AsyncOpenAI') as mock_client:
            mock_instance = AsyncMock()
            
            async def mock_iter_bytes():
                yield b'mock_audio_content'
            
            mock_response = AsyncMock()
            mock_response.iter_bytes.return_value = mock_iter_bytes()
            mock_instance.audio.speech.create.return_value = mock_response
            mock_client.return_value = mock_instance
            
            from src.ai.tts import TextToSpeechService
            tts = TextToSpeechService(api_key='test_key')
            
            vietnamese_text = "Đây là văn bản tiếng Việt để kiểm tra."
            
            with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as temp_file:
                output_path = Path(temp_file.name)
            
            try:
                result = await tts.generate_audio(
                    text=vietnamese_text,
                    output_path=output_path,
                    language="vn",
                    voice="alloy",
                    speed=1.0
                )
                
                assert result.voice == "alloy"
                mock_instance.audio.speech.create.assert_called_once_with(
                    model="tts-1",
                    voice="alloy",
                    input=vietnamese_text,
                    response_format="mp3",
                    speed=1.0
                )
                
            finally:
                # Clean up
                if output_path.exists():
                    output_path.unlink()
    
    @pytest.mark.asyncio
    async def test_generate_audio_with_speed_variations(self):
        """Test the generate_audio function with different speeds."""
        with patch('openai.AsyncOpenAI') as mock_client:
            mock_instance = AsyncMock()
            
            async def mock_iter_bytes():
                yield b'mock_audio_content'
            
            mock_response = AsyncMock()
            mock_response.iter_bytes.return_value = mock_iter_bytes()
            mock_instance.audio.speech.create.return_value = mock_response
            mock_client.return_value = mock_instance
            
            from src.ai.tts import TextToSpeechService
            tts = TextToSpeechService(api_key='test_key')
            
            speeds = [0.5, 1.0, 1.5, 2.0]
            
            for speed in speeds:
                with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as temp_file:
                    output_path = Path(temp_file.name)
                
                try:
                    result = await tts.generate_audio(
                        text="Speed test for: " + str(speed),
                        output_path=output_path,
                        language="en",
                        voice="alloy",
                        speed=speed
                    )
                    
                    # Verify the API was called with the correct speed
                    mock_instance.audio.speech.create.assert_called_with(
                        model="tts-1",
                        voice="alloy",
                        input="Speed test for: " + str(speed),
                        response_format="mp3",
                        speed=speed
                    )
                    
                finally:
                    # Clean up
                    if output_path.exists():
                        output_path.unlink()
    
    @pytest.mark.asyncio
    async def test_generate_audio_with_invalid_voice(self):
        """Test error handling with invalid voice parameter."""
        from src.ai.tts import TextToSpeechService
        tts = TextToSpeechService(api_key='test_key')
        
        with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as temp_file:
            output_path = Path(temp_file.name)
        
        try:
            with pytest.raises(ValueError, match="Invalid voice: invalid_voice"):
                await tts.generate_audio(
                    text="Test with invalid voice",
                    output_path=output_path,
                    language="en",
                    voice="invalid_voice",  # Not a valid voice
                    speed=1.0
                )
        finally:
            # Clean up
            if output_path.exists():
                output_path.unlink()
    
    @pytest.mark.asyncio
    async def test_generate_audio_with_unsupported_language(self):
        """Test error handling with unsupported language."""
        from src.ai.tts import TextToSpeechService
        tts = TextToSpeechService(api_key='test_key')
        
        with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as temp_file:
            output_path = Path(temp_file.name)
        
        try:
            with pytest.raises(ValueError, match="Unsupported language: fr"):
                await tts.generate_audio(
                    text="Test with unsupported language",
                    output_path=output_path,
                    language="fr",  # Not supported ('en' or 'vn')
                    voice="alloy",
                    speed=1.0
                )
        finally:
            # Clean up
            if output_path.exists():
                output_path.unlink()
    
    @pytest.mark.asyncio
    async def test_generate_audio_with_long_text(self):
        """Test handling of long text that needs to be chunked."""
        with patch('src.ai.tts.TextToSpeechService._process_images') as mock_process_images, \
             patch('src.ai.tts.TextToSpeechService._create_video_from_images_and_audio') as mock_create_video, \
             patch('src.ai.tts.TextToSpeechService._get_video_duration') as mock_get_duration, \
             patch('src.ai.tts.TextToSpeechService._get_video_resolution') as mock_get_resolution:
            
            # We are testing text processing, so mock the video-related methods
            mock_process_images.return_value = ["mock_image_path"]
            mock_create_video.return_value = None
            mock_get_duration.return_value = 10.0
            mock_get_resolution.return_value = (1080, 1920)
            
            from src.ai.tts import TextToSpeechService
            tts = TextToSpeechService(api_key='test_key')
            
            # Create a long text (over 4096 characters)
            long_text = "This is a very long text. " * 200  # More than 4096 chars
            
            with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as temp_file:
                output_path = Path(temp_file.name)
            
            try:
                # This test would normally work with the actual TTS service
                # but here we're just verifying the logic flow
                with patch('openai.AsyncOpenAI') as mock_client:
                    mock_instance = AsyncMock()
                    
                    async def mock_iter_bytes():
                        yield b'mock_audio_content'
                    
                    mock_response = AsyncMock()
                    mock_response.iter_bytes.return_value = mock_iter_bytes()
                    mock_instance.audio.speech.create.return_value = mock_response
                    mock_client.return_value = mock_instance
                    
                    result = await tts.generate_audio(
                        text=long_text,
                        output_path=output_path,
                        language="en",
                        voice="alloy",
                        speed=1.0
                    )
                    
                    # Verify that the text was processed
                    assert result.audio_path == output_path
                    assert result.voice == "alloy"
                    
            finally:
                # Clean up
                if output_path.exists():
                    output_path.unlink()
    
    @pytest.mark.asyncio
    async def test_generate_audio_api_failure(self):
        """Test error handling when the TTS API fails."""
        with patch('openai.AsyncOpenAI') as mock_client:
            mock_instance = AsyncMock()
            mock_instance.audio.speech.create.side_effect = Exception("API Error")
            mock_client.return_value = mock_instance
            
            from src.ai.tts import TextToSpeechService
            tts = TextToSpeechService(api_key='test_key')
            
            with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as temp_file:
                output_path = Path(temp_file.name)
            
            try:
                with pytest.raises(Exception, match="API Error"):
                    await tts.generate_audio(
                        text="This should fail",
                        output_path=output_path,
                        language="en",
                        voice="alloy",
                        speed=1.0
                    )
            finally:
                # Clean up
                if output_path.exists():
                    output_path.unlink()
    
    @pytest.mark.asyncio
    async def test_synchronous_generate_audio(self):
        """Test the synchronous version of generate_audio function."""
        with patch('openai.AsyncOpenAI') as mock_client:
            mock_instance = AsyncMock()
            
            async def mock_iter_bytes():
                yield b'mock_audio_content'
            
            mock_response = AsyncMock()
            mock_response.iter_bytes.return_value = mock_iter_bytes()
            mock_instance.audio.speech.create.return_value = mock_response
            mock_client.return_value = mock_instance
            
            from src.ai.tts import generate_audio
            
            with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as temp_file:
                output_path = Path(temp_file.name)
            
            try:
                # Call the synchronous version
                result = await generate_audio(
                    text="Synchronous test audio",
                    output_path=output_path,
                    language="en",
                    voice="alloy",
                    speed=1.0
                )
                
                # Verify the result
                assert result.audio_path == output_path
                assert result.voice == "alloy"
                
            finally:
                # Clean up
                if output_path.exists():
                    output_path.unlink()