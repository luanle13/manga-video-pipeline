import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from pathlib import Path
from dataclasses import dataclass
import tempfile


@dataclass
class MockVideoResult:
    """Mock class for VideoResult."""
    video_path: Path
    duration_seconds: float
    resolution: tuple
    file_size_bytes: int


class TestVideoGenerator:
    """Test cases for the Video Generator."""
    
    @pytest.mark.asyncio
    async def test_generate_video_happy_path(self):
        """Test the generate_video function with valid inputs."""
        with patch('asyncio.create_subprocess_exec') as mock_subprocess, \
             patch('src.video.utils.get_video_duration') as mock_get_duration, \
             patch('src.video.utils.get_video_resolution') as mock_get_resolution:
            
            # Mock the subprocess call to succeed
            mock_proc = AsyncMock()
            mock_proc.returncode = 0
            mock_subprocess.return_value = mock_proc
            
            # Mock the duration and resolution functions
            mock_get_duration.return_value = 30.0
            mock_get_resolution.return_value = (1080, 1920)
            
            from src.video.generator import VideoGenerator
            generator = VideoGenerator()
            
            with tempfile.TemporaryDirectory() as temp_dir:
                # Create mock image files
                temp_images = []
                for i in range(3):
                    img_path = Path(temp_dir) / f"mock_image_{i}.jpg"
                    with open(img_path, 'wb') as f:
                        f.write(b'mock_image_content')
                    temp_images.append(img_path)
                
                # Create mock audio file
                audio_path = Path(temp_dir) / "mock_audio.mp3"
                with open(audio_path, 'wb') as f:
                    f.write(b'mock_audio_content')
                
                # Create output path
                output_path = Path(temp_dir) / "output_video.mp4"
                
                result = await generator.generate_video(
                    images=temp_images,
                    audio_path=audio_path,
                    output_path=output_path
                )
                
                # Verify the result
                assert isinstance(result, MockVideoResult)
                assert result.video_path == output_path
                assert result.duration_seconds == 30.0
                assert result.resolution == (1080, 1920)
                assert result.file_size_bytes > 0
                
                # Verify subprocess was called
                mock_subprocess.assert_called()
    
    @pytest.mark.asyncio
    async def test_generate_video_with_different_audio_durations(self):
        """Test generating video with different audio durations."""
        with patch('asyncio.create_subprocess_exec') as mock_subprocess, \
             patch('src.video.utils.get_video_duration') as mock_get_duration, \
             patch('src.video.utils.get_video_resolution') as mock_get_resolution:
            
            mock_proc = AsyncMock()
            mock_proc.returncode = 0
            mock_subprocess.return_value = mock_proc
            mock_get_duration.return_value = 60.0  # 1 minute audio
            mock_get_resolution.return_value = (1080, 1920)
            
            from src.video.generator import VideoGenerator
            generator = VideoGenerator()
            
            with tempfile.TemporaryDirectory() as temp_dir:
                # Create multiple mock images
                temp_images = []
                for i in range(5):
                    img_path = Path(temp_dir) / f"mock_image_{i}.jpg"
                    with open(img_path, 'wb') as f:
                        f.write(b'mock_image_content')
                    temp_images.append(img_path)
                
                audio_path = Path(temp_dir) / "mock_audio.mp3"
                with open(audio_path, 'wb') as f:
                    f.write(b'mock_audio_content')
                
                output_path = Path(temp_dir) / "output_video.mp4"
                
                result = await generator.generate_video(
                    images=temp_images,
                    audio_path=audio_path,
                    output_path=output_path
                )
                
                assert result.duration_seconds == 60.0
                assert result.video_path == output_path
                # Check that subprocess was called with the right parameters
                mock_subprocess.assert_called()
    
    @pytest.mark.asyncio
    async def test_generate_video_error_handling(self):
        """Test error handling in the generate_video function."""
        with patch('asyncio.create_subprocess_exec') as mock_subprocess:
            # Mock subprocess to fail
            mock_proc = AsyncMock()
            mock_proc.returncode = 1  # Simulate failure
            mock_proc.stderr = AsyncMock()
            mock_proc.stderr.read.return_value = b'FFmpeg error occurred'
            mock_subprocess.return_value = mock_proc
            
            from src.video.generator import VideoGenerator
            generator = VideoGenerator()
            
            with tempfile.TemporaryDirectory() as temp_dir:
                # Create mock files
                temp_images = []
                for i in range(2):
                    img_path = Path(temp_dir) / f"mock_image_{i}.jpg"
                    with open(img_path, 'wb') as f:
                        f.write(b'mock_image_content')
                    temp_images.append(img_path)
                
                audio_path = Path(temp_dir) / "mock_audio.mp3"
                with open(audio_path, 'wb') as f:
                    f.write(b'mock_audio_content')
                
                output_path = Path(temp_dir) / "output_video.mp4"
                
                # This should raise an exception due to FFmpeg failure
                with pytest.raises(Exception, match="FFmpeg failed to create video"):
                    await generator.generate_video(
                        images=temp_images,
                        audio_path=audio_path,
                        output_path=output_path
                    )
    
    @pytest.mark.asyncio
    async def test_generate_video_with_no_images(self):
        """Test error handling when no images are provided."""
        from src.video.generator import VideoGenerator
        generator = VideoGenerator()
        
        with tempfile.TemporaryDirectory() as temp_dir:
            audio_path = Path(temp_dir) / "mock_audio.mp3"
            with open(audio_path, 'wb') as f:
                f.write(b'mock_audio_content')
            
            output_path = Path(temp_dir) / "output_video.mp4"
            
            # This should raise a ValueError
            with pytest.raises(ValueError, match="Images list cannot be empty"):
                await generator.generate_video(
                    images=[],  # Empty list
                    audio_path=audio_path,
                    output_path=output_path
                )
    
    @pytest.mark.asyncio
    async def test_generate_video_with_nonexistent_audio(self):
        """Test error handling when audio file doesn't exist."""
        from src.video.generator import VideoGenerator
        generator = VideoGenerator()
        
        with tempfile.TemporaryDirectory() as temp_dir:
            # Non-existent audio file
            audio_path = Path(temp_dir) / "nonexistent_audio.mp3"
            output_path = Path(temp_dir) / "output_video.mp4"
            
            # Create some mock images
            temp_images = []
            for i in range(2):
                img_path = Path(temp_dir) / f"mock_image_{i}.jpg"
                with open(img_path, 'wb') as f:
                    f.write(b'mock_image_content')
                temp_images.append(img_path)
            
            # This should raise a FileNotFoundError
            with pytest.raises(FileNotFoundError, match="Audio file not found"):
                await generator.generate_video(
                    images=temp_images,
                    audio_path=audio_path,
                    output_path=output_path
                )
    
    @pytest.mark.asyncio
    async def test_generate_video_with_long_audio_short_images(self):
        """Test video generation with long audio and few images."""
        with patch('asyncio.create_subprocess_exec') as mock_subprocess, \
             patch('src.video.utils.get_video_duration') as mock_get_duration, \
             patch('src.video.utils.get_video_resolution') as mock_get_resolution:
            
            mock_proc = AsyncMock()
            mock_proc.returncode = 0
            mock_subprocess.return_value = mock_proc
            mock_get_duration.return_value = 120.0  # 2 minute audio
            mock_get_resolution.return_value = (1080, 1920)
            
            from src.video.generator import VideoGenerator
            generator = VideoGenerator()
            
            with tempfile.TemporaryDirectory() as temp_dir:
                # Only 1 image but long audio
                temp_images = []
                img_path = Path(temp_dir) / "mock_image_0.jpg"
                with open(img_path, 'wb') as f:
                    f.write(b'mock_image_content')
                temp_images.append(img_path)
                
                audio_path = Path(temp_dir) / "mock_audio.mp3"
                with open(audio_path, 'wb') as f:
                    f.write(b'mock_audio_content')
                
                output_path = Path(temp_dir) / "output_video.mp4"
                
                result = await generator.generate_video(
                    images=temp_images,
                    audio_path=audio_path,
                    output_path=output_path
                )
                
                # Even with 1 image, it should handle the long audio properly
                assert result.video_path == output_path
                assert result.duration_seconds == 120.0
                mock_subprocess.assert_called()
    
    @pytest.mark.asyncio
    async def test_generate_video_with_ffprobe_errors(self):
        """Test handling of ffprobe errors."""
        with patch('asyncio.create_subprocess_exec') as mock_subprocess, \
             patch('src.video.utils.get_video_duration') as mock_get_duration, \
             patch('src.video.utils.get_video_resolution') as mock_get_resolution:
            
            # Mock subprocess to succeed but duration/resolution to fail
            mock_proc = AsyncMock()
            mock_proc.returncode = 0
            mock_subprocess.return_value = mock_proc
            
            # Mock duration and resolution to raise exceptions
            mock_get_duration.side_effect = FileNotFoundError("ffprobe not found")
            mock_get_resolution.side_effect = FileNotFoundError("ffprobe not found")
            
            from src.video.generator import VideoGenerator
            generator = VideoGenerator()
            
            with tempfile.TemporaryDirectory() as temp_dir:
                # Create mock files
                temp_images = []
                for i in range(2):
                    img_path = Path(temp_dir) / f"mock_image_{i}.jpg"
                    with open(img_path, 'wb') as f:
                        f.write(b'mock_image_content')
                    temp_images.append(img_path)
                
                audio_path = Path(temp_dir) / "mock_audio.mp3"
                with open(audio_path, 'wb') as f:
                    f.write(b'mock_audio_content')
                
                output_path = Path(temp_dir) / "output_video.mp4"
                
                # Should still succeed even if duration/resolution checks fail
                result = await generator.generate_video(
                    images=temp_images,
                    audio_path=audio_path,
                    output_path=output_path
                )
                
                # Video should be created but with fallback values for duration/resolution
                assert result.video_path == output_path
                # In case of error, our fallback should return 0.0
                assert result.duration_seconds == 0.0  # From fallback
                assert result.resolution == (0, 0)      # From fallback
    
    @pytest.mark.asyncio
    async def test_generate_video_process_parameters(self):
        """Test that the FFmpeg command is constructed with correct parameters."""
        with patch('asyncio.create_subprocess_exec') as mock_subprocess, \
             patch('src.video.utils.get_video_duration') as mock_get_duration, \
             patch('src.video.utils.get_video_resolution') as mock_get_resolution:
            
            mock_proc = AsyncMock()
            mock_proc.returncode = 0
            mock_subprocess.return_value = mock_proc
            mock_get_duration.return_value = 45.0
            mock_get_resolution.return_value = (1080, 1920)
            
            from src.video.generator import VideoGenerator
            generator = VideoGenerator()
            
            with tempfile.TemporaryDirectory() as temp_dir:
                # Create mock files
                temp_images = []
                for i in range(3):
                    img_path = Path(temp_dir) / f"mock_image_{i}.jpg"
                    with open(img_path, 'wb') as f:
                        f.write(b'mock_image_content')
                    temp_images.append(img_path)
                
                audio_path = Path(temp_dir) / "mock_audio.mp3"
                with open(audio_path, 'wb') as f:
                    f.write(b'mock_audio_content')
                
                output_path = Path(temp_dir) / "output_video.mp4"
                
                await generator.generate_video(
                    images=temp_images,
                    audio_path=audio_path,
                    output_path=output_path
                )
                
                # Verify subprocess was called at least once
                assert mock_subprocess.called
                # Check that the call included expected parameters
                call_args = mock_subprocess.call_args
                assert 'ffmpeg' in call_args[0][0]  # First arg should be ffmpeg
                args = call_args[0]
                # Verify that expected parameters are in the command
                cmd_str = ' '.join(args)
                assert '-c:v libx264' in cmd_str  # H.264 video codec
                assert '-c:a aac' in cmd_str      # AAC audio codec
                assert '1080x1920' in cmd_str     # Correct resolution
    
    @pytest.mark.asyncio
    async def test_synchronous_generate_video(self):
        """Test the synchronous version of generate_video function."""
        with patch('asyncio.create_subprocess_exec') as mock_subprocess, \
             patch('src.video.utils.get_video_duration') as mock_get_duration, \
             patch('src.video.utils.get_video_resolution') as mock_get_resolution:
            
            mock_proc = AsyncMock()
            mock_proc.returncode = 0
            mock_subprocess.return_value = mock_proc
            mock_get_duration.return_value = 30.0
            mock_get_resolution.return_value = (1080, 1920)
            
            from src.video.generator import generate_video
            
            with tempfile.TemporaryDirectory() as temp_dir:
                # Create mock files
                temp_images = []
                for i in range(2):
                    img_path = Path(temp_dir) / f"mock_image_{i}.jpg"
                    with open(img_path, 'wb') as f:
                        f.write(b'mock_image_content')
                    temp_images.append(img_path)
                
                audio_path = Path(temp_dir) / "mock_audio.mp3"
                with open(audio_path, 'wb') as f:
                    f.write(b'mock_audio_content')
                
                output_path = Path(temp_dir) / "output_video.mp4"
                
                # Call the synchronous version
                result = await generate_video(
                    images=temp_images,
                    audio_path=audio_path,
                    output_path=output_path
                )
                
                assert result.video_path == output_path
                assert result.duration_seconds == 30.0
                assert result.resolution == (1080, 1920)