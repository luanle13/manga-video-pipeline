#!/usr/bin/env python3
"""
Test script for the VideoGenerator and utils functions.
This script tests the implementation without actually running FFmpeg
since that would require external dependencies and files.
"""

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, patch, MagicMock
import sys
import os

# Add src to the path so we can import the module
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from video.generator import VideoGenerator, VideoResult
from video import utils


async def test_video_generator():
    """Test the VideoGenerator class."""
    print("Testing VideoGenerator...")
    
    # Create a generator instance
    generator = VideoGenerator()
    
    # Mock input paths
    images = [Path("image1.jpg"), Path("image2.jpg")]
    audio_path = Path("audio.mp3")
    output_path = Path("output.mp4")
    
    # Test the generate_video method with mocking
    with patch.object(generator, '_get_audio_duration', return_value=10.0):
        with patch.object(generator, '_process_images', return_value=images):
            with patch.object(generator, '_create_video_from_images_and_audio', return_value=None):
                with patch.object(generator, '_get_video_duration', return_value=10.0):
                    with patch.object(generator, '_get_video_resolution', return_value=(1080, 1920)):
                        with patch('pathlib.Path.stat') as mock_stat:
                            mock_stat.return_value.st_size = 1000000
                            # Test the generate_video method
                            result = await generator.generate_video(
                                images=images,
                                audio_path=audio_path,
                                output_path=output_path
                            )

                            # Verify the result
                            assert isinstance(result, VideoResult), "Result should be a VideoResult instance"
                            assert result.video_path == output_path, "Video path should match output path"
                            assert result.duration_seconds == 10.0, "Duration should match mocked value"
                            assert result.resolution == (1080, 1920), "Resolution should match mocked value"
                            assert result.file_size_bytes == 1000000, "File size should match mocked value"

                            print(f"✓ Basic test passed! Generated video: {result.video_path}")
                            print(f"✓ Duration: {result.duration_seconds} seconds")
                            print(f"✓ Resolution: {result.resolution}")
                            print(f"✓ File size: {result.file_size_bytes} bytes")
    
    # Test error handling for empty images list
    try:
        await generator.generate_video(
            images=[],
            audio_path=audio_path,
            output_path=output_path
        )
        assert False, "Should have raised an error for empty images list"
    except ValueError as e:
        print(f"✓ Error handling for empty images test passed: {e}")
    
    # Test error handling for non-existent audio file
    with patch('pathlib.Path.exists', return_value=False):
        try:
            await generator.generate_video(
                images=images,
                audio_path=audio_path,
                output_path=output_path
            )
            assert False, "Should have raised an error for non-existent audio file"
        except FileNotFoundError as e:
            print(f"✓ Error handling for non-existent audio file test passed: {e}")
    
    print(f"✓ VideoGenerator class test passed!")


def test_dataclass():
    """Test the VideoResult dataclass."""
    print("Testing VideoResult dataclass...")
    
    result = VideoResult(
        video_path=Path("test.mp4"),
        duration_seconds=10.5,
        resolution=(1080, 1920),
        file_size_bytes=2000000
    )
    
    assert result.video_path == Path("test.mp4")
    assert result.duration_seconds == 10.5
    assert result.resolution == (1080, 1920)
    assert result.file_size_bytes == 2000000
    
    print("✓ VideoResult dataclass test passed!")


async def test_utils_functions():
    """Test the utils functions."""
    print("Testing utils functions...")
    
    # Mock paths
    image_path = Path("test_image.jpg")
    video_path = Path("test_video.mp4")
    
    # Test get_video_duration
    with patch('video.utils.asyncio.create_subprocess_exec') as mock_subprocess:
        mock_process = AsyncMock()
        mock_process.communicate.return_value = (b'10.5\n', b'')
        mock_process.returncode = 0
        mock_subprocess.return_value = mock_process
        
        duration = await utils.get_video_duration(video_path)
        assert duration == 10.5
        print(f"✓ get_video_duration test passed! Duration: {duration}")
    
    # Test validate_video
    with patch('pathlib.Path.exists', return_value=True):
        with patch('pathlib.Path.stat') as mock_stat:
            mock_stat.return_value.st_size = 1000000
            with patch('video.utils.get_video_duration', return_value=10.0):
                with patch('mimetypes.guess_type', return_value=('video/mp4', None)):
                    is_valid = await utils.validate_video(video_path)
                    assert is_valid == True
                    print(f"✓ validate_video test passed! Valid: {is_valid}")

    # Test validate_video with invalid file
    with patch('pathlib.Path.exists', return_value=False):
        is_valid = await utils.validate_video(video_path)
        assert is_valid == False
        print(f"✓ validate_video invalid file test passed! Valid: {is_valid}")
    
    print("✓ All utils functions test passed!")


if __name__ == "__main__":
    # Run the dataclass test
    test_dataclass()
    
    # Run the async tests
    asyncio.run(test_video_generator())
    asyncio.run(test_utils_functions())
    
    print("\nAll tests passed! VideoGenerator and utils are working correctly.")