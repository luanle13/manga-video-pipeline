"""Video compositor for rendering final videos using MoviePy."""

import os
import subprocess
import tempfile
from pathlib import Path

from moviepy import (
    AudioFileClip,
    CompositeVideoClip,
    ImageClip,
    concatenate_videoclips,
)
from PIL import Image

from src.common.logging_config import setup_logger
from src.renderer.scene_builder import Scene

logger = setup_logger(__name__)


class VideoCompositor:
    """Compositor for rendering videos from manga panels and audio."""

    def __init__(
        self,
        resolution: tuple[int, int] = (1920, 1080),
        fps: int = 24,
    ) -> None:
        """
        Initialize the video compositor.

        Args:
            resolution: Video resolution as (width, height). Default: 1080p.
            fps: Frames per second. Default: 24.
        """
        self.resolution = resolution
        self.fps = fps

        logger.info(
            "VideoCompositor initialized",
            extra={
                "resolution": f"{resolution[0]}x{resolution[1]}",
                "fps": fps,
            },
        )

    def create_panel_clip(
        self,
        image_path: str,
        duration: float,
    ) -> ImageClip:
        """
        Create a video clip from a panel image.

        Loads the image, resizes to fit resolution (maintaining aspect ratio),
        and pads with black bars if necessary.

        Args:
            image_path: Path to the panel image.
            duration: Duration of the clip in seconds.

        Returns:
            MoviePy ImageClip with the specified duration.
        """
        # Load image with Pillow
        img = Image.open(image_path)
        original_width, original_height = img.size

        target_width, target_height = self.resolution

        # Calculate scaling to fit within resolution while maintaining aspect ratio
        width_ratio = target_width / original_width
        height_ratio = target_height / original_height
        scale_ratio = min(width_ratio, height_ratio)

        new_width = int(original_width * scale_ratio)
        new_height = int(original_height * scale_ratio)

        # Resize image
        img_resized = img.resize((new_width, new_height), Image.Resampling.LANCZOS)

        # Create black background
        background = Image.new("RGB", (target_width, target_height), (0, 0, 0))

        # Paste resized image centered on background
        x_offset = (target_width - new_width) // 2
        y_offset = (target_height - new_height) // 2
        background.paste(img_resized, (x_offset, y_offset))

        # Save to temporary file for MoviePy
        temp_file = tempfile.NamedTemporaryFile(
            suffix=".jpg",
            delete=False,
        )
        temp_path = temp_file.name
        temp_file.close()

        background.save(temp_path, quality=95)

        # Create MoviePy ImageClip
        clip = ImageClip(temp_path, duration=duration)

        logger.debug(
            "Panel clip created",
            extra={
                "image_path": image_path,
                "original_size": f"{original_width}x{original_height}",
                "resized_size": f"{new_width}x{new_height}",
                "duration": duration,
            },
        )

        # Clean up temp file after clip is created
        # Note: MoviePy loads the image, so we can delete the temp file
        try:
            os.unlink(temp_path)
        except Exception:
            pass

        return clip

    def add_transition(
        self,
        clip1: ImageClip,
        clip2: ImageClip,
        transition_duration: float = 0.5,
    ) -> CompositeVideoClip:
        """
        Add a cross-dissolve transition between two clips.

        Args:
            clip1: First clip (will fade out).
            clip2: Second clip (will fade in).
            transition_duration: Duration of the transition in seconds.

        Returns:
            CompositeVideoClip with the transition effect.
        """
        # Set clip2 to start during clip1's transition
        clip2_start = clip1.duration - transition_duration

        # Apply fade out to clip1 (last transition_duration seconds)
        clip1_with_fadeout = clip1.crossfadeout(transition_duration)

        # Apply fade in to clip2 (first transition_duration seconds)
        clip2_with_fadein = clip2.crossfadein(transition_duration).set_start(
            clip2_start
        )

        # Composite the clips
        composite = CompositeVideoClip(
            [clip1_with_fadeout, clip2_with_fadein],
            size=self.resolution,
        )

        return composite

    def compose_video(
        self,
        scenes: list[Scene],
        panel_dir: str,
        audio_path: str,
        output_path: str,
    ) -> str:
        """
        Compose the final video from scenes and audio.

        Args:
            scenes: List of Scene objects with timing information.
            panel_dir: Directory where panel images are stored (for local testing).
                      In production, panels will be downloaded from S3.
            audio_path: Path to the audio file.
            output_path: Path where the output video will be saved.

        Returns:
            Path to the rendered video file.
        """
        logger.info(
            "Starting video composition",
            extra={
                "total_scenes": len(scenes),
                "audio_path": audio_path,
                "output_path": output_path,
            },
        )

        if not scenes:
            raise ValueError("No scenes provided for video composition")

        # Create clips for each scene
        clips = []
        for idx, scene in enumerate(scenes):
            # Calculate duration from scene timing
            duration = scene.end_time - scene.start_time

            # For local testing, use panel_dir; in production, download from S3
            panel_filename = os.path.basename(scene.panel_s3_key)
            panel_path = os.path.join(panel_dir, panel_filename)

            # Create clip
            clip = self.create_panel_clip(panel_path, duration)
            clips.append(clip)

            if (idx + 1) % 10 == 0:
                logger.info(
                    f"Created {idx + 1}/{len(scenes)} clips",
                    extra={
                        "progress_pct": int((idx + 1) / len(scenes) * 100),
                    },
                )

        logger.info("All clips created, concatenating")

        # Concatenate all clips
        # Note: crossfadein/out applied during concatenation would add transitions
        # For now, we concatenate without transitions to simplify
        final_video = concatenate_videoclips(clips, method="compose")

        # Set audio
        logger.info("Adding audio to video")
        audio_clip = AudioFileClip(audio_path)
        final_video = final_video.set_audio(audio_clip)

        # Write output video
        logger.info(
            "Writing output video",
            extra={"output_path": output_path},
        )

        final_video.write_videofile(
            output_path,
            codec="libx264",
            audio_codec="aac",
            preset="medium",
            fps=self.fps,
            bitrate="2000k",
            logger=None,  # Disable MoviePy's verbose logging
        )

        # Clean up clips
        for clip in clips:
            clip.close()
        audio_clip.close()
        final_video.close()

        logger.info(
            "Video composition complete",
            extra={
                "output_path": output_path,
                "file_size_mb": round(os.path.getsize(output_path) / (1024 * 1024), 2),
            },
        )

        return output_path

    def compose_video_chunked(
        self,
        scenes: list[Scene],
        panel_dir: str,
        audio_path: str,
        output_path: str,
        chunk_size: int = 100,
    ) -> str:
        """
        Compose video in chunks for memory efficiency.

        For very long videos (2-5 hours), rendering in chunks prevents
        MoviePy from holding the entire video in memory.

        Args:
            scenes: List of Scene objects with timing information.
            panel_dir: Directory where panel images are stored.
            audio_path: Path to the audio file.
            output_path: Path where the output video will be saved.
            chunk_size: Number of scenes per chunk (default: 100).

        Returns:
            Path to the rendered video file.
        """
        logger.info(
            "Starting chunked video composition",
            extra={
                "total_scenes": len(scenes),
                "chunk_size": chunk_size,
                "chunks": (len(scenes) + chunk_size - 1) // chunk_size,
            },
        )

        if not scenes:
            raise ValueError("No scenes provided for video composition")

        # Create temporary directory for chunks
        temp_dir = tempfile.mkdtemp(prefix="video_chunks_")
        chunk_files = []

        try:
            # Render each chunk
            num_chunks = (len(scenes) + chunk_size - 1) // chunk_size

            for chunk_idx in range(num_chunks):
                start_idx = chunk_idx * chunk_size
                end_idx = min(start_idx + chunk_size, len(scenes))
                chunk_scenes = scenes[start_idx:end_idx]

                logger.info(
                    f"Rendering chunk {chunk_idx + 1}/{num_chunks}",
                    extra={
                        "start_scene": start_idx,
                        "end_scene": end_idx,
                        "scenes_in_chunk": len(chunk_scenes),
                    },
                )

                # Create clips for this chunk
                clips = []
                for scene in chunk_scenes:
                    duration = scene.end_time - scene.start_time
                    panel_filename = os.path.basename(scene.panel_s3_key)
                    panel_path = os.path.join(panel_dir, panel_filename)

                    clip = self.create_panel_clip(panel_path, duration)
                    clips.append(clip)

                # Concatenate clips in this chunk
                chunk_video = concatenate_videoclips(clips, method="compose")

                # Write chunk to temp file (no audio yet)
                chunk_file = os.path.join(temp_dir, f"chunk_{chunk_idx:04d}.mp4")
                chunk_video.write_videofile(
                    chunk_file,
                    codec="libx264",
                    preset="medium",
                    fps=self.fps,
                    bitrate="2000k",
                    audio=False,  # No audio in chunks
                    logger=None,
                )

                chunk_files.append(chunk_file)

                # Clean up clips
                for clip in clips:
                    clip.close()
                chunk_video.close()

                logger.info(
                    f"Chunk {chunk_idx + 1}/{num_chunks} complete",
                    extra={
                        "chunk_file": chunk_file,
                        "file_size_mb": round(
                            os.path.getsize(chunk_file) / (1024 * 1024), 2
                        ),
                    },
                )

            # Concatenate chunks using FFmpeg
            logger.info("Concatenating chunks with FFmpeg")

            # Create concat file for FFmpeg
            concat_file = os.path.join(temp_dir, "concat_list.txt")
            with open(concat_file, "w") as f:
                for chunk_file in chunk_files:
                    f.write(f"file '{chunk_file}'\n")

            # Concatenate without re-encoding (fast)
            temp_output = os.path.join(temp_dir, "concatenated.mp4")
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
                    "copy",
                    temp_output,
                ],
                check=True,
                capture_output=True,
            )

            logger.info("Chunks concatenated, adding audio")

            # Add audio using FFmpeg
            subprocess.run(
                [
                    "ffmpeg",
                    "-i",
                    temp_output,
                    "-i",
                    audio_path,
                    "-c:v",
                    "copy",
                    "-c:a",
                    "aac",
                    "-b:a",
                    "192k",
                    "-shortest",
                    output_path,
                ],
                check=True,
                capture_output=True,
            )

            logger.info(
                "Chunked video composition complete",
                extra={
                    "output_path": output_path,
                    "file_size_mb": round(
                        os.path.getsize(output_path) / (1024 * 1024), 2
                    ),
                },
            )

            return output_path

        finally:
            # Clean up temporary files
            logger.info("Cleaning up temporary chunk files")
            try:
                for chunk_file in chunk_files:
                    if os.path.exists(chunk_file):
                        os.unlink(chunk_file)

                # Clean up other temp files
                for file in ["concat_list.txt", "concatenated.mp4"]:
                    filepath = os.path.join(temp_dir, file)
                    if os.path.exists(filepath):
                        os.unlink(filepath)

                # Remove temp directory
                os.rmdir(temp_dir)
            except Exception as e:
                logger.warning(
                    "Failed to clean up some temporary files",
                    extra={"error": str(e)},
                )
