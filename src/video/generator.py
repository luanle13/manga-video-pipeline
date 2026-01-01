from __future__ import annotations
import asyncio
import tempfile
from dataclasses import dataclass
from pathlib import Path
import logging
from typing import List, Tuple


@dataclass(slots=True)
class VideoResult:
    """Result of video generation."""
    video_path: Path
    duration_seconds: float
    resolution: Tuple[int, int]  # (width, height)
    file_size_bytes: int


class VideoGenerator:
    """Video generator using FFmpeg for creating YouTube Shorts compatible videos."""
    
    def __init__(self):
        """Initialize the VideoGenerator."""
        pass
    
    async def generate_video(
        self,
        images: List[Path],
        audio_path: Path,
        output_path: Path
    ) -> VideoResult:
        """
        Generate a video from images and audio.
        
        Args:
            images: List of image paths
            audio_path: Path to the audio file
            output_path: Path to save the generated video
            
        Returns:
            VideoResult object with video path, duration, resolution, and file size
        """
        # Validate inputs
        if not images:
            raise ValueError("Images list cannot be empty")
        
        if not audio_path.exists():
            raise FileNotFoundError(f"Audio file not found: {audio_path}")
        
        # Get audio duration
        audio_duration = await self._get_audio_duration(audio_path)
        
        # Process images: resize to 1080x1920, add padding, center
        processed_images = await self._process_images(images)
        
        # Calculate duration per image based on audio duration
        duration_per_image = audio_duration / len(processed_images)
        if duration_per_image < 0.1:  # Minimum 0.1 seconds per image
            duration_per_image = 0.1
            # Adjust audio duration to match
            audio_duration = duration_per_image * len(processed_images)
        
        # Build and run FFmpeg command
        await self._create_video_from_images_and_audio(
            processed_images,
            audio_path,
            output_path,
            duration_per_image
        )
        
        # Get video info
        video_duration = await self._get_video_duration(output_path)
        resolution = await self._get_video_resolution(output_path)
        file_size = output_path.stat().st_size
        
        return VideoResult(
            video_path=output_path,
            duration_seconds=video_duration,
            resolution=resolution,
            file_size_bytes=file_size
        )
    
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
                logging.warning(f"ffprobe failed to get audio duration: {stderr.decode()}")
                # If ffprobe fails, return 0.0 as fallback
                return 0.0
        except FileNotFoundError:
            logging.warning("ffprobe not found. Please install ffmpeg.")
            return 0.0
        except Exception as e:
            logging.warning(f"Error getting audio duration: {e}")
            return 0.0
    
    async def _process_images(self, images: List[Path]) -> List[Path]:
        """Process images: resize to 1080x1920, add padding, center.
        
        Args:
            images: List of input image paths
            
        Returns:
            List of processed image paths
        """
        from .utils import resize_image, add_padding
        
        processed_images = []
        
        for img_path in images:
            # Create a temporary file for the processed image
            with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as temp_file:
                temp_path = Path(temp_file.name)
            
            # Resize and add padding to the image
            await resize_image(img_path, temp_path, (1080, 1920))
            await add_padding(temp_path, temp_path, (1080, 1920))  # Center processed image
            
            processed_images.append(temp_path)
        
        return processed_images
    
    async def _create_video_from_images_and_audio(
        self,
        images: List[Path],
        audio_path: Path,
        output_path: Path,
        duration_per_image: float
    ) -> None:
        """Create a video from images and audio using FFmpeg.
        
        Args:
            images: List of processed image paths
            audio_path: Path to the audio file
            output_path: Path to save the video
            duration_per_image: Duration in seconds for each image
        """
        # Create a temporary file listing all input images
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as temp_list:
            for img_path in images:
                # Repeat each image for the specified duration (at 30fps)
                frame_count = int(duration_per_image * 30)  # 30 FPS
                for _ in range(frame_count):
                    temp_list.write(f"file '{img_path}'\n")
            temp_list_path = Path(temp_list.name)
        
        try:
            # Build FFmpeg command
            cmd = [
                'ffmpeg',
                '-f', 'concat',
                '-safe', '0',
                '-i', str(temp_list_path),
                '-i', str(audio_path),
                '-c:v', 'libx264',       # H.264 video codec
                '-c:a', 'aac',            # AAC audio codec
                '-pix_fmt', 'yuv420p',    # Pixel format for compatibility
                '-r', '30',               # 30 FPS
                '-s', '1080x1920',        # Resolution for YouTube Shorts
                '-shortest',              # End when the shortest input ends
                '-y',                     # Overwrite output file
                str(output_path)
            ]
            
            # Run FFmpeg command
            result = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await result.communicate()
            
            if result.returncode != 0:
                raise Exception(f"FFmpeg failed to create video: {stderr.decode()}")
        
        finally:
            # Clean up the temporary file
            temp_list_path.unlink()
    
    async def _get_video_duration(self, video_path: Path) -> float:
        """Get the duration of a video file using ffprobe.
        
        Args:
            video_path: Path to the video file
            
        Returns:
            Duration in seconds
        """
        try:
            result = await asyncio.create_subprocess_exec(
                'ffprobe',
                '-v', 'quiet',
                '-show_entries', 'format=duration',
                '-of', 'csv=p=0',
                str(video_path),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await result.communicate()
            
            if result.returncode == 0:
                duration = float(stdout.decode().strip())
                return duration
            else:
                logging.warning(f"ffprobe failed to get video duration: {stderr.decode()}")
                return 0.0
        except FileNotFoundError:
            logging.warning("ffprobe not found. Please install ffmpeg.")
            return 0.0
        except Exception as e:
            logging.warning(f"Error getting video duration: {e}")
            return 0.0
    
    async def _get_video_resolution(self, video_path: Path) -> Tuple[int, int]:
        """Get the resolution of a video file using ffprobe.
        
        Args:
            video_path: Path to the video file
            
        Returns:
            Tuple of (width, height)
        """
        try:
            result = await asyncio.create_subprocess_exec(
                'ffprobe',
                '-v', 'quiet',
                '-select_streams', 'v:0',
                '-show_entries', 'stream=width,height',
                '-of', 'csv=p=0',
                str(video_path),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await result.communicate()
            
            if result.returncode == 0:
                resolution_str = stdout.decode().strip()
                width, height = resolution_str.split(',')
                return int(width), int(height)
            else:
                logging.warning(f"ffprobe failed to get video resolution: {stderr.decode()}")
                return 0, 0
        except FileNotFoundError:
            logging.warning("ffprobe not found. Please install ffmpeg.")
            return 0, 0
        except Exception as e:
            logging.warning(f"Error getting video resolution: {e}")
            return 0, 0


# For backward compatibility or synchronous use
async def generate_video(images: List[Path], audio_path: Path, output_path: Path) -> VideoResult:
    """Synchronous wrapper for generate_video method."""
    generator = VideoGenerator()
    return await generator.generate_video(images, audio_path, output_path)