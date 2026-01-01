from __future__ import annotations
import asyncio
from pathlib import Path
from PIL import Image, ImageOps
import mimetypes


async def resize_image(input_path: Path, output_path: Path, target_size: tuple[int, int]) -> None:
    """Resize an image to the target size while maintaining aspect ratio.
    
    Args:
        input_path: Path to the input image
        output_path: Path to save the resized image
        target_size: Target size as (width, height)
    """
    def _resize():
        with Image.open(input_path) as img:
            # Calculate the aspect ratio
            img_ratio = img.width / img.height
            target_ratio = target_size[0] / target_size[1]
            
            # Determine which dimension to fit to the target
            if img_ratio > target_ratio:
                # Image is wider relative to target, fit to width
                new_width = target_size[0]
                new_height = int(target_size[0] / img_ratio)
            else:
                # Image is taller relative to target, fit to height
                new_height = target_size[1]
                new_width = int(target_size[1] * img_ratio)
            
            # Resize the image
            resized_img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
            
            # Save the resized image
            resized_img.save(output_path, format='JPEG', quality=95)
    
    # Run the PIL operation in a separate thread since it's CPU-bound
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, _resize)


async def add_padding(input_path: Path, output_path: Path, target_size: tuple[int, int]) -> None:
    """Add padding to an image to make it fit the target size with centering.
    
    Args:
        input_path: Path to the input image (should already be resized)
        output_path: Path to save the padded image
        target_size: Target size as (width, height)
    """
    def _add_padding():
        with Image.open(input_path) as img:
            # Calculate position to center the image
            x_offset = (target_size[0] - img.width) // 2
            y_offset = (target_size[1] - img.height) // 2
            
            # Create a new image with the target size and black background
            padded_img = Image.new('RGB', target_size, (0, 0, 0))
            
            # Paste the resized image in the center
            padded_img.paste(img, (x_offset, y_offset))
            
            # Save the padded image
            padded_img.save(output_path, format='JPEG', quality=95)
    
    # Run the PIL operation in a separate thread since it's CPU-bound
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, _add_padding)


async def get_video_duration(video_path: Path) -> float:
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
            raise Exception(f"ffprobe failed to get duration: {stderr.decode()}")
    except FileNotFoundError:
        raise FileNotFoundError("ffprobe not found. Please install ffmpeg.")
    except Exception as e:
        raise Exception(f"Error getting video duration: {e}")


async def validate_video(video_path: Path) -> bool:
    """Validate a video file to ensure it meets basic requirements.
    
    Args:
        video_path: Path to the video file
        
    Returns:
        True if the video is valid, False otherwise
    """
    if not video_path.exists():
        return False
    
    # Check file size (should be greater than 0)
    if video_path.stat().st_size == 0:
        return False
    
    # Try to get the video duration to verify it's a valid video file
    try:
        duration = await get_video_duration(video_path)
        if duration <= 0:
            return False
    except:
        return False  # Invalid video file
    
    # Check if it's actually a video file based on extension or MIME type
    extension = video_path.suffix.lower()
    mime_type, _ = mimetypes.guess_type(str(video_path))
    
    if extension in ['.mp4', '.avi', '.mov', '.mkv', '.wmv', '.flv', '.webm']:
        return True
    
    if mime_type and mime_type.startswith('video/'):
        return True
    
    return False