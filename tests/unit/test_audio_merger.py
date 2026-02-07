"""Tests for audio merger."""

import os
import sys
import tempfile
from unittest.mock import MagicMock, Mock, call, mock_open, patch

import pytest

# Mock pydub before importing AudioMerger to avoid audioop issues
sys.modules["pydub"] = MagicMock()
sys.modules["pydub.AudioSegment"] = MagicMock()

from src.common.models import AudioManifest, AudioSegment
from src.renderer.audio_merger import AudioMerger


@pytest.fixture
def audio_merger():
    """Create an AudioMerger instance."""
    return AudioMerger()


@pytest.fixture
def sample_audio_manifest():
    """Create a sample audio manifest."""
    return AudioManifest(
        job_id="job-123",
        segments=[
            AudioSegment(
                index=0,
                s3_key="jobs/job-123/audio/0000.mp3",
                duration_seconds=3.5,
                chapter="1",
                panel_start=0,
                panel_end=2,
            ),
            AudioSegment(
                index=1,
                s3_key="jobs/job-123/audio/0001.mp3",
                duration_seconds=4.2,
                chapter="1",
                panel_start=3,
                panel_end=5,
            ),
            AudioSegment(
                index=2,
                s3_key="jobs/job-123/audio/0002.mp3",
                duration_seconds=3.8,
                chapter="2",
                panel_start=6,
                panel_end=8,
            ),
        ],
        total_duration_seconds=11.5,
    )


class TestAudioMergerInitialization:
    """Tests for AudioMerger initialization."""

    def test_initializes_successfully(self):
        """Test that AudioMerger initializes."""
        merger = AudioMerger()
        assert merger is not None


class TestMergeAudioFiles:
    """Tests for merge_audio_files method."""

    def test_merges_files_with_pydub(self, audio_merger):
        """Test merging audio files with pydub."""
        audio_paths = [
            "/fake/audio1.mp3",
            "/fake/audio2.mp3",
            "/fake/audio3.mp3",
        ]

        with patch("src.renderer.audio_merger.AudioSegment") as mock_audio_segment, \
             patch("os.path.getsize", return_value=1024 * 1024):

            # Mock audio segments
            mock_segment1 = MagicMock()
            mock_segment1.__len__.return_value = 3500  # 3.5 seconds in ms

            mock_segment2 = MagicMock()
            mock_segment2.__len__.return_value = 4200  # 4.2 seconds

            mock_segment3 = MagicMock()
            mock_segment3.__len__.return_value = 3800  # 3.8 seconds

            # Mock combined segment
            mock_combined = MagicMock()
            mock_combined.__len__.return_value = 11500  # Total
            mock_combined.export = MagicMock()

            # Set up addition behavior (both __add__ and __iadd__ for +=)
            mock_segment1.__add__.return_value = mock_combined
            mock_segment1.__iadd__ = lambda self, other: mock_combined
            mock_combined.__add__.return_value = mock_combined
            mock_combined.__iadd__ = lambda self, other: mock_combined

            mock_audio_segment.from_mp3.side_effect = [
                mock_segment1,
                mock_segment2,
                mock_segment3,
            ]

            duration = audio_merger.merge_audio_files(
                audio_paths=audio_paths,
                output_path="/fake/output.mp3",
                use_ffmpeg=False,
            )

            # Verify all files were loaded
            assert mock_audio_segment.from_mp3.call_count == 3

            # Verify export was called
            mock_combined.export.assert_called_once()

            # Verify duration (11500ms = 11.5s)
            assert duration == 11.5

    def test_merges_files_in_correct_order(self, audio_merger):
        """Test that files are merged in the correct order."""
        audio_paths = [
            "/fake/audio1.mp3",
            "/fake/audio2.mp3",
            "/fake/audio3.mp3",
        ]

        with patch("src.renderer.audio_merger.AudioSegment") as mock_audio_segment, \
             patch("os.path.getsize", return_value=1024 * 1024):

            mock_segment1 = MagicMock()
            mock_segment1.__len__ = MagicMock(return_value=1000)

            mock_segment2 = MagicMock()
            mock_segment2.__len__ = MagicMock(return_value=2000)

            mock_segment3 = MagicMock()
            mock_segment3.__len__ = MagicMock(return_value=3000)

            mock_combined = MagicMock()
            mock_combined.__len__ = MagicMock(return_value=6000)
            mock_combined.export = MagicMock()

            mock_segment1.__add__ = MagicMock(return_value=mock_combined)
            mock_combined.__add__ = MagicMock(return_value=mock_combined)

            mock_audio_segment.from_mp3.side_effect = [
                mock_segment1,
                mock_segment2,
                mock_segment3,
            ]

            audio_merger.merge_audio_files(
                audio_paths=audio_paths,
                output_path="/fake/output.mp3",
                use_ffmpeg=False,
            )

            # Verify files loaded in order
            calls = mock_audio_segment.from_mp3.call_args_list
            assert calls[0][0][0] == "/fake/audio1.mp3"
            assert calls[1][0][0] == "/fake/audio2.mp3"
            assert calls[2][0][0] == "/fake/audio3.mp3"

    def test_exports_with_correct_format(self, audio_merger):
        """Test that output is exported with correct format."""
        audio_paths = ["/fake/audio1.mp3"]

        with patch("src.renderer.audio_merger.AudioSegment") as mock_audio_segment, \
             patch("os.path.getsize", return_value=1024 * 1024):

            mock_segment = MagicMock()
            mock_segment.__len__ = MagicMock(return_value=1000)
            mock_segment.export = MagicMock()

            mock_audio_segment.from_mp3.return_value = mock_segment

            # Test MP3 output
            audio_merger.merge_audio_files(
                audio_paths=audio_paths,
                output_path="/fake/output.mp3",
                use_ffmpeg=False,
            )

            export_call = mock_segment.export.call_args
            assert export_call[0][0] == "/fake/output.mp3"
            assert export_call[1]["format"] == "mp3"
            assert export_call[1]["bitrate"] == "192k"

    def test_exports_wav_format(self, audio_merger):
        """Test exporting as WAV format."""
        audio_paths = ["/fake/audio1.mp3"]

        with patch("src.renderer.audio_merger.AudioSegment") as mock_audio_segment, \
             patch("os.path.getsize", return_value=1024 * 1024):

            mock_segment = MagicMock()
            mock_segment.__len__ = MagicMock(return_value=1000)
            mock_segment.export = MagicMock()

            mock_audio_segment.from_mp3.return_value = mock_segment

            # Test WAV output
            audio_merger.merge_audio_files(
                audio_paths=audio_paths,
                output_path="/fake/output.wav",
                use_ffmpeg=False,
            )

            export_call = mock_segment.export.call_args
            assert export_call[0][0] == "/fake/output.wav"
            assert export_call[1]["format"] == "wav"
            assert export_call[1]["bitrate"] is None  # No bitrate for WAV

    def test_raises_error_on_empty_list(self, audio_merger):
        """Test that error is raised when no files provided."""
        with pytest.raises(ValueError, match="No audio files provided"):
            audio_merger.merge_audio_files(
                audio_paths=[],
                output_path="/fake/output.mp3",
            )

    def test_merges_with_ffmpeg(self, audio_merger):
        """Test merging with FFmpeg for memory efficiency."""
        audio_paths = [
            "/fake/audio1.mp3",
            "/fake/audio2.mp3",
        ]

        with patch("src.renderer.audio_merger.subprocess.run") as mock_subprocess, \
             patch("builtins.open", mock_open()) as mock_file, \
             patch("os.path.getsize", return_value=1024 * 1024), \
             patch("os.unlink"):

            # Mock ffprobe output
            mock_result = MagicMock()
            mock_result.stdout = "12.5\n"
            mock_subprocess.return_value = mock_result

            duration = audio_merger.merge_audio_files(
                audio_paths=audio_paths,
                output_path="/fake/output.mp3",
                use_ffmpeg=True,
            )

            # Verify FFmpeg was called (2 calls: concat + probe)
            assert mock_subprocess.call_count == 2

            # Verify first call is ffmpeg concat
            first_call = mock_subprocess.call_args_list[0]
            assert "ffmpeg" in first_call[0][0]
            assert "-f" in first_call[0][0]
            assert "concat" in first_call[0][0]

            # Verify second call is ffprobe
            second_call = mock_subprocess.call_args_list[1]
            assert "ffprobe" in second_call[0][0]

            # Verify duration
            assert duration == 12.5


class TestMergeFromS3:
    """Tests for merge_from_s3 method."""

    def test_downloads_all_segments(self, audio_merger, sample_audio_manifest):
        """Test that all segments are downloaded from S3."""
        mock_s3_client = MagicMock()

        with patch.object(audio_merger, "merge_audio_files") as mock_merge, \
             patch("os.makedirs"), \
             patch("os.unlink"):

            mock_merge.return_value = 11.5

            output_path, duration = audio_merger.merge_from_s3(
                audio_manifest=sample_audio_manifest,
                s3_client=mock_s3_client,
                job_id="job-123",
                local_dir="/fake/dir",
            )

            # Verify all 3 segments were downloaded
            assert mock_s3_client.download_file.call_count == 3

            # Verify downloads in correct order
            calls = mock_s3_client.download_file.call_args_list
            assert calls[0][0][0] == "jobs/job-123/audio/0000.mp3"
            assert calls[1][0][0] == "jobs/job-123/audio/0001.mp3"
            assert calls[2][0][0] == "jobs/job-123/audio/0002.mp3"

    def test_merges_downloaded_files(self, audio_merger, sample_audio_manifest):
        """Test that downloaded files are merged."""
        mock_s3_client = MagicMock()

        with patch.object(audio_merger, "merge_audio_files") as mock_merge, \
             patch("os.makedirs"), \
             patch("os.unlink"):

            mock_merge.return_value = 11.5

            output_path, duration = audio_merger.merge_from_s3(
                audio_manifest=sample_audio_manifest,
                s3_client=mock_s3_client,
                job_id="job-123",
                local_dir="/fake/dir",
            )

            # Verify merge was called
            mock_merge.assert_called_once()

            # Verify output path includes job_id
            assert "job-123_merged.mp3" in output_path

            # Verify duration returned
            assert duration == 11.5

    def test_uses_ffmpeg_for_long_audio(self, audio_merger):
        """Test that FFmpeg is used for audio > 1 hour."""
        # Create manifest with long duration
        long_manifest = AudioManifest(
            job_id="job-123",
            segments=[
                AudioSegment(
                    index=i,
                    s3_key=f"jobs/job-123/audio/{i:04d}.mp3",
                    duration_seconds=60.0,
                    chapter="1",
                    panel_start=i * 2,
                    panel_end=i * 2 + 1,
                )
                for i in range(100)  # 100 segments * 60s = 6000s > 1 hour
            ],
            total_duration_seconds=6000.0,
        )

        mock_s3_client = MagicMock()

        with patch.object(audio_merger, "merge_audio_files") as mock_merge, \
             patch("os.makedirs"), \
             patch("os.unlink"):

            mock_merge.return_value = 6000.0

            audio_merger.merge_from_s3(
                audio_manifest=long_manifest,
                s3_client=mock_s3_client,
                job_id="job-123",
                local_dir="/fake/dir",
            )

            # Verify merge was called with use_ffmpeg=True
            call_kwargs = mock_merge.call_args[1]
            assert call_kwargs["use_ffmpeg"] is True

    def test_uses_ffmpeg_for_many_segments(self, audio_merger):
        """Test that FFmpeg is used for > 100 segments."""
        # Create manifest with many segments
        many_segments_manifest = AudioManifest(
            job_id="job-123",
            segments=[
                AudioSegment(
                    index=i,
                    s3_key=f"jobs/job-123/audio/{i:04d}.mp3",
                    duration_seconds=5.0,
                    chapter="1",
                    panel_start=i * 2,
                    panel_end=i * 2 + 1,
                )
                for i in range(150)  # > 100 segments
            ],
            total_duration_seconds=750.0,
        )

        mock_s3_client = MagicMock()

        with patch.object(audio_merger, "merge_audio_files") as mock_merge, \
             patch("os.makedirs"), \
             patch("os.unlink"):

            mock_merge.return_value = 750.0

            audio_merger.merge_from_s3(
                audio_manifest=many_segments_manifest,
                s3_client=mock_s3_client,
                job_id="job-123",
                local_dir="/fake/dir",
            )

            # Verify merge was called with use_ffmpeg=True
            call_kwargs = mock_merge.call_args[1]
            assert call_kwargs["use_ffmpeg"] is True

    def test_cleans_up_segment_files(self, audio_merger, sample_audio_manifest):
        """Test that individual segment files are cleaned up."""
        mock_s3_client = MagicMock()

        with patch.object(audio_merger, "merge_audio_files") as mock_merge, \
             patch("os.makedirs"), \
             patch("os.unlink") as mock_unlink:

            mock_merge.return_value = 11.5

            audio_merger.merge_from_s3(
                audio_manifest=sample_audio_manifest,
                s3_client=mock_s3_client,
                job_id="job-123",
                local_dir="/fake/dir",
            )

            # Verify segment files were deleted (3 segments)
            assert mock_unlink.call_count == 3

    def test_creates_local_directory(self, audio_merger, sample_audio_manifest):
        """Test that local directory is created if it doesn't exist."""
        mock_s3_client = MagicMock()

        with patch.object(audio_merger, "merge_audio_files") as mock_merge, \
             patch("os.makedirs") as mock_makedirs, \
             patch("os.unlink"):

            mock_merge.return_value = 11.5

            audio_merger.merge_from_s3(
                audio_manifest=sample_audio_manifest,
                s3_client=mock_s3_client,
                job_id="job-123",
                local_dir="/fake/dir",
            )

            # Verify directory was created
            mock_makedirs.assert_called_once_with("/fake/dir", exist_ok=True)


class TestDurationCalculation:
    """Tests for duration calculation."""

    def test_duration_matches_sum_of_segments(self, audio_merger):
        """Test that total duration matches sum of individual segments."""
        audio_paths = [
            "/fake/audio1.mp3",
            "/fake/audio2.mp3",
            "/fake/audio3.mp3",
        ]

        with patch("src.renderer.audio_merger.AudioSegment") as mock_audio_segment, \
             patch("os.path.getsize", return_value=1024 * 1024):

            # Segments with specific durations
            mock_segment1 = MagicMock()
            mock_segment1.__len__.return_value = 2500  # 2.5s

            mock_segment2 = MagicMock()
            mock_segment2.__len__.return_value = 3500  # 3.5s

            mock_segment3 = MagicMock()
            mock_segment3.__len__.return_value = 4000  # 4.0s

            # Combined should be sum
            mock_combined = MagicMock()
            mock_combined.__len__.return_value = 10000  # 10.0s total
            mock_combined.export = MagicMock()

            mock_segment1.__add__.return_value = mock_combined
            mock_segment1.__iadd__ = lambda self, other: mock_combined
            mock_combined.__add__.return_value = mock_combined
            mock_combined.__iadd__ = lambda self, other: mock_combined

            mock_audio_segment.from_mp3.side_effect = [
                mock_segment1,
                mock_segment2,
                mock_segment3,
            ]

            duration = audio_merger.merge_audio_files(
                audio_paths=audio_paths,
                output_path="/fake/output.mp3",
                use_ffmpeg=False,
            )

            # Total should be 10.0 seconds
            assert duration == 10.0

    def test_duration_with_ffmpeg(self, audio_merger):
        """Test duration calculation with FFmpeg."""
        audio_paths = ["/fake/audio1.mp3", "/fake/audio2.mp3"]

        with patch("src.renderer.audio_merger.subprocess.run") as mock_subprocess, \
             patch("builtins.open", mock_open()), \
             patch("os.path.getsize", return_value=1024 * 1024), \
             patch("os.unlink"):

            # Mock ffprobe to return specific duration
            mock_result = MagicMock()
            mock_result.stdout = "25.75\n"  # 25.75 seconds
            mock_subprocess.return_value = mock_result

            duration = audio_merger.merge_audio_files(
                audio_paths=audio_paths,
                output_path="/fake/output.mp3",
                use_ffmpeg=True,
            )

            # Verify ffprobe was used to get duration
            second_call = mock_subprocess.call_args_list[1]
            assert "ffprobe" in second_call[0][0]

            # Verify duration
            assert duration == 25.75


class TestOutputFormat:
    """Tests for output format validation."""

    def test_mp3_output_is_valid(self, audio_merger):
        """Test that MP3 output format is correct."""
        audio_paths = ["/fake/audio1.mp3"]

        with patch("src.renderer.audio_merger.AudioSegment") as mock_audio_segment, \
             patch("os.path.getsize", return_value=1024 * 1024):

            mock_segment = MagicMock()
            mock_segment.__len__ = MagicMock(return_value=1000)
            mock_segment.export = MagicMock()

            mock_audio_segment.from_mp3.return_value = mock_segment

            audio_merger.merge_audio_files(
                audio_paths=audio_paths,
                output_path="/fake/output.mp3",
                use_ffmpeg=False,
            )

            # Verify export format
            export_call = mock_segment.export.call_args
            assert export_call[1]["format"] == "mp3"

    def test_defaults_to_mp3_for_unknown_format(self, audio_merger):
        """Test that unknown formats default to MP3."""
        audio_paths = ["/fake/audio1.mp3"]

        with patch("src.renderer.audio_merger.AudioSegment") as mock_audio_segment, \
             patch("os.path.getsize", return_value=1024 * 1024):

            mock_segment = MagicMock()
            mock_segment.__len__ = MagicMock(return_value=1000)
            mock_segment.export = MagicMock()

            mock_audio_segment.from_mp3.return_value = mock_segment

            audio_merger.merge_audio_files(
                audio_paths=audio_paths,
                output_path="/fake/output.xyz",  # Unknown format
                use_ffmpeg=False,
            )

            # Should default to mp3
            export_call = mock_segment.export.call_args
            assert export_call[1]["format"] == "mp3"


class TestProgressLogging:
    """Tests for progress logging."""

    def test_logs_progress_for_many_segments(self, audio_merger):
        """Test that progress is logged when processing many segments."""
        # Create 25 audio paths
        audio_paths = [f"/fake/audio{i}.mp3" for i in range(25)]

        with patch("src.renderer.audio_merger.AudioSegment") as mock_audio_segment, \
             patch("os.path.getsize", return_value=1024 * 1024):

            mock_segment = MagicMock()
            mock_segment.__len__.return_value = 1000

            mock_combined = MagicMock()
            mock_combined.__len__.return_value = 25000
            mock_combined.export = MagicMock()

            mock_segment.__add__.return_value = mock_combined
            mock_segment.__iadd__ = lambda self, other: mock_combined
            mock_combined.__add__.return_value = mock_combined
            mock_combined.__iadd__ = lambda self, other: mock_combined

            mock_audio_segment.from_mp3.return_value = mock_segment

            # Should process without errors and log progress
            duration = audio_merger.merge_audio_files(
                audio_paths=audio_paths,
                output_path="/fake/output.mp3",
                use_ffmpeg=False,
            )

            # Verify all files were loaded
            assert mock_audio_segment.from_mp3.call_count == 25

            # Verify duration
            assert duration == 25.0
