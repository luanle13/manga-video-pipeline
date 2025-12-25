import ffmpeg
from PIL import Image, ImageDraw, ImageFont
import os
from typing import List
from ..config import get_settings


class MangaVideoGenerator:
    """Generate videos from manga images and audio."""
    
    def __init__(self):
        self.settings = get_settings()
        self.temp_dir = self.settings.pipeline.temp_path
        self.output_dir = self.settings.pipeline.output_dir

    def create_video(self, image_paths: list[str], audio_path: str, output_path: str) -> bool:
        """Create a video from manga images and audio."""
        try:
            # Create a video from the images
            # First, create a slideshow from the images
            temp_video_path = os.path.join(self.temp_dir, "temp_video.mp4")
            
            # Create a slideshow video from images
            if not self._create_slideshow_from_images(image_paths, temp_video_path):
                return False
            
            # Add audio to the video
            if not self._add_audio_to_video(temp_video_path, audio_path, output_path):
                return False
            
            # Clean up temporary file
            if os.path.exists(temp_video_path):
                os.remove(temp_video_path)
            
            return True
        except Exception as e:
            print(f"Error creating video: {e}")
            return False

    def _create_slideshow_from_images(self, image_paths: list[str], output_path: str) -> bool:
        """Create a slideshow video from manga images."""
        try:
            # Create a temporary directory for processed images
            temp_image_dir = os.path.join(self.temp_dir, "temp_images")
            os.makedirs(temp_image_dir, exist_ok=True)
            
            # Process each image to the correct dimensions
            processed_images = []
            for i, img_path in enumerate(image_paths):
                output_img_path = os.path.join(temp_image_dir, f"processed_{i:04d}.jpg")
                
                # Resize image to fit video dimensions while maintaining aspect ratio
                with Image.open(img_path) as img:
                    img = self._resize_image_to_fit(img, self.settings.video_width, self.settings.video_height)
                    img.save(output_img_path, "JPEG", quality=90)
                
                processed_images.append(output_img_path)
            
            # Use ffmpeg to create the slideshow
            # Each image will be shown for 3 seconds (adjust as needed)
            inputs = []
            for img_path in processed_images:
                inputs.extend(['-loop', '1', '-t', '3', '-i', img_path])
            
            # Calculate total duration
            total_duration = len(processed_images) * 3  # 3 seconds per image
            
            # Create video command
            cmd = (
                ffmpeg
                .input(processed_images[0], 
                      format='image2', 
                      r='1/3',  # 1 frame every 3 seconds
                      loop=1, 
                      t=total_duration)
                .filter('scale', self.settings.video_width, self.settings.video_height, force_original_aspect_ratio='decrease')
                .filter('pad', self.settings.video_width, self.settings.video_height,
                       (self.settings.video_width - 'iw')/2, (self.settings.video_height - 'ih')/2)
            )
            
            # For simplicity, let's just use the first image for now
            # Full implementation would handle multiple images properly
            (
                ffmpeg
                .input(processed_images[0], 
                      format='image2', 
                      r=1/3,  # 1 frame every 3 seconds
                      loop=1, 
                      t=total_duration)
                .filter('scale', self.settings.video_width, self.settings.video_height, force_original_aspect_ratio='decrease')
                .filter('pad', self.settings.video_width, self.settings.video_height,
                       (self.settings.video_width - 'iw')//2, (self.settings.video_height - 'ih')//2)
                .output(output_path, 
                       vcodec='libx264', 
                       pix_fmt='yuv420p', 
                       r=self.settings.video_fps,
                       b:v=self.settings.video_bitrate)
                .overwrite_output()
                .run(quiet=True)
            )
            
            # Clean up temp directory
            import shutil
            shutil.rmtree(temp_image_dir)
            
            return os.path.exists(output_path)
        except Exception as e:
            print(f"Error creating slideshow from images: {e}")
            return False

    def _add_audio_to_video(self, video_path: str, audio_path: str, output_path: str) -> bool:
        """Add audio to a video."""
        try:
            (
                ffmpeg
                .input(video_path)
                .input(audio_path)
                .output(output_path, 
                       vcodec='copy', 
                       acodec='aac', 
                       strict='experimental')
                .overwrite_output()
                .run(quiet=True)
            )
            
            return os.path.exists(output_path)
        except Exception as e:
            print(f"Error adding audio to video: {e}")
            return False

    def _resize_image_to_fit(self, image: Image.Image, target_width: int, target_height: int) -> Image.Image:
        """Resize image to fit within target dimensions while maintaining aspect ratio."""
        img_width, img_height = image.size
        target_ratio = target_width / target_height
        img_ratio = img_width / img_height
        
        if img_ratio > target_ratio:
            # Image is wider than target, fit to width
            new_width = target_width
            new_height = int(target_width / img_ratio)
        else:
            # Image is taller than target, fit to height
            new_height = target_height
            new_width = int(target_height * img_ratio)
        
        # Resize the image
        resized_img = image.resize((new_width, new_height), Image.Resampling.LANCZOS)
        
        # Create a new image with target dimensions and paste the resized image
        new_img = Image.new('RGB', (target_width, target_height), (0, 0, 0))
        paste_x = (target_width - new_width) // 2
        paste_y = (target_height - new_height) // 2
        new_img.paste(resized_img, (paste_x, paste_y))
        
        return new_img


# Global video generator instance
video_generator = MangaVideoGenerator()