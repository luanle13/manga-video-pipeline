"""Tests for video compositor."""

import os
import tempfile
from unittest.mock import MagicMock, Mock, call, patch

import pytest
from PIL import Image

from src.renderer.compositor import VideoCompositor
from src.renderer.scene_builder import Scene


@pytest.fixture
def compositor():
    """Create a VideoCompositor instance."""
    return VideoCompositor(resolution=(1920, 1080), fps=24)


@pytest.fixture
def sample_scenes():
    """Create sample scenes."""
    return [
        Scene(
            panel_s3_key="jobs/job-123/panels/0000_0000.jpg",
            start_time=0.0,
            end_time=5.0,
            transition_duration=0.5,
        ),
        Scene(
            panel_s3_key="jobs/job-123/panels/0000_0001.jpg",
            start_time=5.0,
            end_time=10.0,
            transition_duration=0.5,
        ),
        Scene(
            panel_s3_key="jobs/job-123/panels/0000_0002.jpg",
            start_time=10.0,
            end_time=15.0,
            transition_duration=0.5,
        ),
    ]


@pytest.fixture
def temp_image():
    """Create a temporary test image."""
    temp_file = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
    temp_path = temp_file.name
    temp_file.close()

    # Create a simple test image
    img = Image.new("RGB", (800, 600), color=(255, 0, 0))
    img.save(temp_path)

    yield temp_path

    # Cleanup
    try:
        os.unlink(temp_path)
    except Exception:
        pass


class TestVideoCompositorInitialization:
    """Tests for VideoCompositor initialization."""

    def test_initializes_with_default_settings(self):
        """Test that compositor initializes with default settings."""
        compositor = VideoCompositor()

        assert compositor.resolution == (1920, 1080)
        assert compositor.fps == 24

    def test_initializes_with_custom_settings(self):
        """Test that compositor initializes with custom settings."""
        compositor = VideoCompositor(resolution=(1280, 720), fps=30)

        assert compositor.resolution == (1280, 720)
        assert compositor.fps == 30


class TestCreatePanelClip:
    """Tests for create_panel_clip method."""

    def test_creates_clip_with_correct_duration(self, compositor, temp_image):
        """Test that clip is created with correct duration."""
        with patch("src.renderer.compositor.ImageClip") as mock_image_clip:
            mock_clip = MagicMock()
            mock_image_clip.return_value = mock_clip

            clip = compositor.create_panel_clip(temp_image, duration=5.0)

            # Verify ImageClip was called with duration
            assert mock_image_clip.called
            call_args = mock_image_clip.call_args
            assert call_args[1]["duration"] == 5.0

    def test_resizes_image_to_fit_resolution(self, compositor, temp_image):
        """Test that image is resized to fit resolution."""
        with patch("src.renderer.compositor.ImageClip") as mock_image_clip, \
             patch("src.renderer.compositor.Image.open") as mock_open, \
             patch("src.renderer.compositor.Image.new") as mock_new:

            # Create mock image with specific size
            mock_img = MagicMock()
            mock_img.size = (800, 600)  # Smaller than target resolution
            mock_open.return_value = mock_img

            # Mock resize to return a proper PIL Image mock
            mock_resized = MagicMock()
            mock_resized.size = (1440, 1080)  # After resize
            mock_img.resize.return_value = mock_resized

            # Mock background
            mock_background = MagicMock()
            mock_new.return_value = mock_background

            compositor.create_panel_clip(temp_image, duration=5.0)

            # Verify image was opened
            mock_open.assert_called_once_with(temp_image)

            # Verify resize was called
            assert mock_img.resize.called

    def test_pads_image_with_black_bars(self, compositor):
        """Test that image is padded with black bars to maintain aspect ratio."""
        with patch("src.renderer.compositor.ImageClip") as mock_image_clip, \
             patch("src.renderer.compositor.Image.open") as mock_open, \
             patch("src.renderer.compositor.Image.new") as mock_new:

            # Create mock image (portrait orientation)
            mock_img = MagicMock()
            mock_img.size = (800, 1200)  # Portrait
            mock_open.return_value = mock_img

            # Mock resize
            mock_resized = MagicMock()
            mock_img.resize.return_value = mock_resized

            # Mock background
            mock_background = MagicMock()
            mock_new.return_value = mock_background

            compositor.create_panel_clip("/fake/path.jpg", duration=5.0)

            # Verify black background was created with target resolution
            mock_new.assert_called_once_with("RGB", (1920, 1080), (0, 0, 0))

            # Verify paste was called (to center image on background)
            assert mock_background.paste.called

    def test_handles_landscape_image(self, compositor):
        """Test handling of landscape-oriented image."""
        with patch("src.renderer.compositor.ImageClip") as mock_image_clip, \
             patch("src.renderer.compositor.Image.open") as mock_open, \
             patch("src.renderer.compositor.Image.new") as mock_new:

            # Wide landscape image
            mock_img = MagicMock()
            mock_img.size = (2000, 800)  # Landscape
            mock_open.return_value = mock_img

            mock_resized = MagicMock()
            mock_resized.size = (1920, 768)  # After resize
            mock_img.resize.return_value = mock_resized

            # Mock background
            mock_background = MagicMock()
            mock_new.return_value = mock_background

            compositor.create_panel_clip("/fake/path.jpg", duration=5.0)

            # Should resize to fit within 1920x1080
            # Width ratio: 1920/2000 = 0.96
            # Height ratio: 1080/800 = 1.35
            # Should use width ratio (0.96) to maintain aspect
            expected_width = int(2000 * 0.96)
            expected_height = int(800 * 0.96)

            # Verify resize was called with correct dimensions
            resize_call = mock_img.resize.call_args
            new_width, new_height = resize_call[0][0]
            assert new_width == expected_width
            assert new_height == expected_height

    def test_handles_portrait_image(self, compositor):
        """Test handling of portrait-oriented image."""
        with patch("src.renderer.compositor.ImageClip") as mock_image_clip, \
             patch("src.renderer.compositor.Image.open") as mock_open, \
             patch("src.renderer.compositor.Image.new") as mock_new:

            # Tall portrait image
            mock_img = MagicMock()
            mock_img.size = (600, 1200)  # Portrait
            mock_open.return_value = mock_img

            mock_resized = MagicMock()
            mock_resized.size = (540, 1080)  # After resize
            mock_img.resize.return_value = mock_resized

            # Mock background
            mock_background = MagicMock()
            mock_new.return_value = mock_background

            compositor.create_panel_clip("/fake/path.jpg", duration=5.0)

            # Height ratio: 1080/1200 = 0.9
            # Width ratio: 1920/600 = 3.2
            # Should use height ratio (0.9)
            expected_width = int(600 * 0.9)
            expected_height = int(1200 * 0.9)

            resize_call = mock_img.resize.call_args
            new_width, new_height = resize_call[0][0]
            assert new_width == expected_width
            assert new_height == expected_height


class TestAddTransition:
    """Tests for add_transition method."""

    def test_adds_crossfade_transition(self, compositor):
        """Test that crossfade transition is added between clips."""
        # Create mock clips
        mock_clip1 = MagicMock()
        mock_clip1.duration = 5.0
        mock_clip1_fadeout = MagicMock()
        mock_clip1.crossfadeout.return_value = mock_clip1_fadeout

        mock_clip2 = MagicMock()
        mock_clip2_fadein = MagicMock()
        mock_clip2_with_start = MagicMock()
        mock_clip2.crossfadein.return_value = mock_clip2_fadein
        mock_clip2_fadein.set_start.return_value = mock_clip2_with_start

        with patch("src.renderer.compositor.CompositeVideoClip") as mock_composite:
            compositor.add_transition(mock_clip1, mock_clip2, transition_duration=0.5)

            # Verify crossfadeout was called on clip1
            mock_clip1.crossfadeout.assert_called_once_with(0.5)

            # Verify crossfadein was called on clip2
            mock_clip2.crossfadein.assert_called_once_with(0.5)

            # Verify clip2 start time was set
            mock_clip2_fadein.set_start.assert_called_once_with(4.5)  # 5.0 - 0.5

            # Verify CompositeVideoClip was created
            assert mock_composite.called

    def test_transition_timing_correct(self, compositor):
        """Test that transition timing is calculated correctly."""
        mock_clip1 = MagicMock()
        mock_clip1.duration = 10.0
        mock_clip1_fadeout = MagicMock()
        mock_clip1.crossfadeout.return_value = mock_clip1_fadeout

        mock_clip2 = MagicMock()
        mock_clip2_fadein = MagicMock()
        mock_clip2_with_start = MagicMock()
        mock_clip2.crossfadein.return_value = mock_clip2_fadein
        mock_clip2_fadein.set_start.return_value = mock_clip2_with_start

        with patch("src.renderer.compositor.CompositeVideoClip"):
            compositor.add_transition(mock_clip1, mock_clip2, transition_duration=1.0)

            # Clip2 should start at clip1.duration - transition_duration
            mock_clip2_fadein.set_start.assert_called_once_with(9.0)  # 10.0 - 1.0


class TestComposeVideo:
    """Tests for compose_video method."""

    def test_creates_clips_for_all_scenes(self, compositor, sample_scenes):
        """Test that clips are created for all scenes."""
        with patch.object(compositor, "create_panel_clip") as mock_create_clip, \
             patch("src.renderer.compositor.concatenate_videoclips") as mock_concat, \
             patch("src.renderer.compositor.AudioFileClip") as mock_audio, \
             patch("os.path.getsize", return_value=1024 * 1024):

            mock_clip = MagicMock()
            mock_clip.close = MagicMock()
            mock_create_clip.return_value = mock_clip

            mock_final_video = MagicMock()
            mock_final_video.set_audio.return_value = mock_final_video
            mock_final_video.write_videofile = MagicMock()
            mock_final_video.close = MagicMock()
            mock_concat.return_value = mock_final_video

            mock_audio_clip = MagicMock()
            mock_audio_clip.close = MagicMock()
            mock_audio.return_value = mock_audio_clip

            compositor.compose_video(
                scenes=sample_scenes,
                panel_dir="/fake/panels",
                audio_path="/fake/audio.mp3",
                output_path="/fake/output.mp4",
            )

            # Should create 3 clips (one per scene)
            assert mock_create_clip.call_count == 3

            # Verify durations (second argument is duration)
            calls = mock_create_clip.call_args_list
            assert calls[0][0][1] == 5.0  # 5.0 - 0.0
            assert calls[1][0][1] == 5.0  # 10.0 - 5.0
            assert calls[2][0][1] == 5.0  # 15.0 - 10.0

    def test_concatenates_clips(self, compositor, sample_scenes):
        """Test that clips are concatenated."""
        with patch.object(compositor, "create_panel_clip") as mock_create_clip, \
             patch("src.renderer.compositor.concatenate_videoclips") as mock_concat, \
             patch("src.renderer.compositor.AudioFileClip") as mock_audio, \
             patch("os.path.getsize", return_value=1024 * 1024):

            mock_clip = MagicMock()
            mock_create_clip.return_value = mock_clip

            mock_final_video = MagicMock()
            mock_final_video.set_audio.return_value = mock_final_video
            mock_concat.return_value = mock_final_video

            mock_audio_clip = MagicMock()
            mock_audio.return_value = mock_audio_clip

            compositor.compose_video(
                scenes=sample_scenes,
                panel_dir="/fake/panels",
                audio_path="/fake/audio.mp3",
                output_path="/fake/output.mp4",
            )

            # Verify concatenate was called
            mock_concat.assert_called_once()
            concat_args = mock_concat.call_args
            assert len(concat_args[0][0]) == 3  # 3 clips
            assert concat_args[1]["method"] == "compose"

    def test_adds_audio_to_video(self, compositor, sample_scenes):
        """Test that audio is added to video."""
        with patch.object(compositor, "create_panel_clip") as mock_create_clip, \
             patch("src.renderer.compositor.concatenate_videoclips") as mock_concat, \
             patch("src.renderer.compositor.AudioFileClip") as mock_audio, \
             patch("os.path.getsize", return_value=1024 * 1024):

            mock_clip = MagicMock()
            mock_create_clip.return_value = mock_clip

            mock_final_video = MagicMock()
            mock_final_video.set_audio.return_value = mock_final_video
            mock_concat.return_value = mock_final_video

            mock_audio_clip = MagicMock()
            mock_audio.return_value = mock_audio_clip

            compositor.compose_video(
                scenes=sample_scenes,
                panel_dir="/fake/panels",
                audio_path="/fake/audio.mp3",
                output_path="/fake/output.mp4",
            )

            # Verify audio was loaded
            mock_audio.assert_called_once_with("/fake/audio.mp3")

            # Verify audio was set on video
            mock_final_video.set_audio.assert_called_once_with(mock_audio_clip)

    def test_writes_video_with_correct_settings(self, compositor, sample_scenes):
        """Test that video is written with correct codec settings."""
        with patch.object(compositor, "create_panel_clip") as mock_create_clip, \
             patch("src.renderer.compositor.concatenate_videoclips") as mock_concat, \
             patch("src.renderer.compositor.AudioFileClip") as mock_audio, \
             patch("os.path.getsize", return_value=1024 * 1024):

            mock_clip = MagicMock()
            mock_create_clip.return_value = mock_clip

            mock_final_video = MagicMock()
            mock_final_video.set_audio.return_value = mock_final_video
            mock_concat.return_value = mock_final_video

            mock_audio_clip = MagicMock()
            mock_audio.return_value = mock_audio_clip

            compositor.compose_video(
                scenes=sample_scenes,
                panel_dir="/fake/panels",
                audio_path="/fake/audio.mp3",
                output_path="/fake/output.mp4",
            )

            # Verify write_videofile was called with correct settings
            mock_final_video.write_videofile.assert_called_once()
            call_args = mock_final_video.write_videofile.call_args

            assert call_args[0][0] == "/fake/output.mp4"
            assert call_args[1]["codec"] == "libx264"
            assert call_args[1]["audio_codec"] == "aac"
            assert call_args[1]["preset"] == "medium"
            assert call_args[1]["fps"] == 24
            assert call_args[1]["bitrate"] == "2000k"

    def test_raises_error_on_empty_scenes(self, compositor):
        """Test that error is raised when no scenes provided."""
        with pytest.raises(ValueError, match="No scenes provided"):
            compositor.compose_video(
                scenes=[],
                panel_dir="/fake/panels",
                audio_path="/fake/audio.mp3",
                output_path="/fake/output.mp4",
            )

    def test_returns_output_path(self, compositor, sample_scenes):
        """Test that output path is returned."""
        with patch.object(compositor, "create_panel_clip") as mock_create_clip, \
             patch("src.renderer.compositor.concatenate_videoclips") as mock_concat, \
             patch("src.renderer.compositor.AudioFileClip") as mock_audio, \
             patch("os.path.getsize", return_value=1024 * 1024):

            mock_clip = MagicMock()
            mock_create_clip.return_value = mock_clip

            mock_final_video = MagicMock()
            mock_final_video.set_audio.return_value = mock_final_video
            mock_concat.return_value = mock_final_video

            mock_audio_clip = MagicMock()
            mock_audio.return_value = mock_audio_clip

            result = compositor.compose_video(
                scenes=sample_scenes,
                panel_dir="/fake/panels",
                audio_path="/fake/audio.mp3",
                output_path="/fake/output.mp4",
            )

            assert result == "/fake/output.mp4"


class TestComposeVideoChunked:
    """Tests for compose_video_chunked method."""

    def test_creates_chunks_for_large_scene_list(self, compositor):
        """Test that scenes are split into chunks."""
        # Create 250 scenes (should be split into 3 chunks of 100)
        scenes = [
            Scene(
                panel_s3_key=f"jobs/job-123/panels/{i:04d}.jpg",
                start_time=float(i * 5),
                end_time=float((i + 1) * 5),
                transition_duration=0.5,
            )
            for i in range(250)
        ]

        with patch.object(compositor, "create_panel_clip") as mock_create_clip, \
             patch("src.renderer.compositor.concatenate_videoclips") as mock_concat, \
             patch("src.renderer.compositor.subprocess.run") as mock_subprocess, \
             patch("tempfile.mkdtemp") as mock_mkdtemp, \
             patch("os.unlink"), \
             patch("os.rmdir"), \
             patch("os.path.getsize", return_value=1024 * 1024), \
             patch("builtins.open", create=True):

            mock_mkdtemp.return_value = "/tmp/chunks"

            mock_clip = MagicMock()
            mock_create_clip.return_value = mock_clip

            mock_video = MagicMock()
            mock_concat.return_value = mock_video

            compositor.compose_video_chunked(
                scenes=scenes,
                panel_dir="/fake/panels",
                audio_path="/fake/audio.mp3",
                output_path="/fake/output.mp4",
                chunk_size=100,
            )

            # Should create 3 chunks (100, 100, 50)
            # Each chunk renders to a file, so write_videofile called 3 times
            assert mock_video.write_videofile.call_count == 3

    def test_concatenates_chunks_with_ffmpeg(self, compositor):
        """Test that chunks are concatenated with FFmpeg."""
        scenes = [
            Scene(
                panel_s3_key=f"jobs/job-123/panels/{i:04d}.jpg",
                start_time=float(i * 5),
                end_time=float((i + 1) * 5),
                transition_duration=0.5,
            )
            for i in range(150)
        ]

        with patch.object(compositor, "create_panel_clip") as mock_create_clip, \
             patch("src.renderer.compositor.concatenate_videoclips") as mock_concat, \
             patch("src.renderer.compositor.subprocess.run") as mock_subprocess, \
             patch("tempfile.mkdtemp") as mock_mkdtemp, \
             patch("os.unlink"), \
             patch("os.rmdir"), \
             patch("os.path.getsize", return_value=1024 * 1024), \
             patch("builtins.open", create=True):

            mock_mkdtemp.return_value = "/tmp/chunks"

            mock_clip = MagicMock()
            mock_create_clip.return_value = mock_clip

            mock_video = MagicMock()
            mock_concat.return_value = mock_video

            compositor.compose_video_chunked(
                scenes=scenes,
                panel_dir="/fake/panels",
                audio_path="/fake/audio.mp3",
                output_path="/fake/output.mp4",
                chunk_size=100,
            )

            # Verify FFmpeg was called twice (concat + add audio)
            assert mock_subprocess.call_count == 2

            # First call should be concat
            first_call = mock_subprocess.call_args_list[0]
            assert "ffmpeg" in first_call[0][0]
            assert "-f" in first_call[0][0]
            assert "concat" in first_call[0][0]

            # Second call should add audio
            second_call = mock_subprocess.call_args_list[1]
            assert "ffmpeg" in second_call[0][0]
            assert "/fake/audio.mp3" in second_call[0][0]

    def test_cleans_up_temporary_files(self, compositor):
        """Test that temporary chunk files are cleaned up."""
        scenes = [
            Scene(
                panel_s3_key=f"jobs/job-123/panels/{i:04d}.jpg",
                start_time=float(i * 5),
                end_time=float((i + 1) * 5),
                transition_duration=0.5,
            )
            for i in range(50)
        ]

        with patch.object(compositor, "create_panel_clip") as mock_create_clip, \
             patch("src.renderer.compositor.concatenate_videoclips") as mock_concat, \
             patch("src.renderer.compositor.subprocess.run") as mock_subprocess, \
             patch("tempfile.mkdtemp") as mock_mkdtemp, \
             patch("os.unlink") as mock_unlink, \
             patch("os.rmdir") as mock_rmdir, \
             patch("os.path.getsize", return_value=1024 * 1024), \
             patch("builtins.open", create=True), \
             patch("os.path.exists", return_value=True):

            mock_mkdtemp.return_value = "/tmp/chunks"

            mock_clip = MagicMock()
            mock_create_clip.return_value = mock_clip

            mock_video = MagicMock()
            mock_concat.return_value = mock_video

            compositor.compose_video_chunked(
                scenes=scenes,
                panel_dir="/fake/panels",
                audio_path="/fake/audio.mp3",
                output_path="/fake/output.mp4",
                chunk_size=100,
            )

            # Verify cleanup was attempted
            assert mock_unlink.called
            assert mock_rmdir.called

    def test_raises_error_on_empty_scenes(self, compositor):
        """Test that error is raised when no scenes provided."""
        with pytest.raises(ValueError, match="No scenes provided"):
            compositor.compose_video_chunked(
                scenes=[],
                panel_dir="/fake/panels",
                audio_path="/fake/audio.mp3",
                output_path="/fake/output.mp4",
            )


class TestResolutionLogic:
    """Tests for resolution and padding logic."""

    def test_different_resolutions(self):
        """Test compositor with different resolutions."""
        compositor_720p = VideoCompositor(resolution=(1280, 720), fps=30)
        compositor_4k = VideoCompositor(resolution=(3840, 2160), fps=60)

        assert compositor_720p.resolution == (1280, 720)
        assert compositor_720p.fps == 30

        assert compositor_4k.resolution == (3840, 2160)
        assert compositor_4k.fps == 60

    def test_square_image_padding(self):
        """Test that square image is padded correctly."""
        compositor = VideoCompositor(resolution=(1920, 1080))

        with patch("src.renderer.compositor.ImageClip") as mock_image_clip, \
             patch("src.renderer.compositor.Image.open") as mock_open, \
             patch("src.renderer.compositor.Image.new") as mock_new:

            # Square image
            mock_img = MagicMock()
            mock_img.size = (1000, 1000)
            mock_open.return_value = mock_img

            mock_resized = MagicMock()
            mock_resized.size = (1080, 1080)  # After resize
            mock_img.resize.return_value = mock_resized

            # Mock background
            mock_background = MagicMock()
            mock_new.return_value = mock_background

            compositor.create_panel_clip("/fake/path.jpg", duration=5.0)

            # For 1920x1080 target and 1000x1000 source
            # Width ratio: 1920/1000 = 1.92
            # Height ratio: 1080/1000 = 1.08
            # Should use height ratio (1.08) as minimum
            expected_size = (1080, 1080)

            resize_call = mock_img.resize.call_args
            actual_size = resize_call[0][0]
            assert actual_size == expected_size
