"""Tests for scene builder."""

import pytest

from src.common.models import AudioManifest, AudioSegment
from src.renderer.scene_builder import Scene, SceneBuilder


@pytest.fixture
def scene_builder():
    """Create a SceneBuilder instance."""
    return SceneBuilder()


@pytest.fixture
def sample_panel_manifest():
    """Create a sample panel manifest."""
    return {
        "job_id": "job-123",
        "manga_id": "manga-456",
        "manga_title": "One Piece",
        "total_panels": 10,
        "chapters": [
            {
                "chapter_id": "ch-001",
                "chapter_number": "1",
                "panel_keys": [
                    "jobs/job-123/panels/0000_0000.jpg",
                    "jobs/job-123/panels/0000_0001.jpg",
                    "jobs/job-123/panels/0000_0002.jpg",
                    "jobs/job-123/panels/0000_0003.jpg",
                    "jobs/job-123/panels/0000_0004.jpg",
                ],
            },
            {
                "chapter_id": "ch-002",
                "chapter_number": "2",
                "panel_keys": [
                    "jobs/job-123/panels/0001_0000.jpg",
                    "jobs/job-123/panels/0001_0001.jpg",
                    "jobs/job-123/panels/0001_0002.jpg",
                    "jobs/job-123/panels/0001_0003.jpg",
                    "jobs/job-123/panels/0001_0004.jpg",
                ],
            },
        ],
    }


@pytest.fixture
def sample_audio_manifest():
    """Create a sample audio manifest with 10 panels over 60 seconds."""
    return AudioManifest(
        job_id="job-123",
        segments=[
            AudioSegment(
                index=0,
                s3_key="jobs/job-123/audio/0000.mp3",
                duration_seconds=30.0,
                chapter="1",
                panel_start=0,
                panel_end=4,  # 5 panels
            ),
            AudioSegment(
                index=1,
                s3_key="jobs/job-123/audio/0001.mp3",
                duration_seconds=30.0,
                chapter="2",
                panel_start=5,
                panel_end=9,  # 5 panels
            ),
        ],
        total_duration_seconds=60.0,
    )


class TestSceneDataClass:
    """Tests for Scene data class."""

    def test_scene_has_required_fields(self):
        """Test that Scene has all required fields."""
        scene = Scene(
            panel_s3_key="jobs/job-123/panels/0000_0000.jpg",
            start_time=0.0,
            end_time=5.0,
            transition_duration=0.5,
        )

        assert scene.panel_s3_key == "jobs/job-123/panels/0000_0000.jpg"
        assert scene.start_time == 0.0
        assert scene.end_time == 5.0
        assert scene.transition_duration == 0.5

    def test_scene_default_transition_duration(self):
        """Test that Scene has default transition duration."""
        scene = Scene(
            panel_s3_key="jobs/job-123/panels/0000_0000.jpg",
            start_time=0.0,
            end_time=5.0,
        )

        assert scene.transition_duration == 0.5


class TestSceneBuilderInitialization:
    """Tests for SceneBuilder initialization."""

    def test_initializes_successfully(self):
        """Test that SceneBuilder initializes."""
        builder = SceneBuilder()
        assert builder is not None


class TestCalculatePanelDuration:
    """Tests for calculate_panel_duration method."""

    def test_calculates_duration_for_single_panel(self, scene_builder):
        """Test duration calculation for a single panel."""
        duration = scene_builder.calculate_panel_duration(
            segment_duration=30.0,
            num_panels=1,
        )

        # Single panel should show for entire segment
        assert duration == 30.0

    def test_calculates_duration_for_multiple_panels(self, scene_builder):
        """Test duration calculation for multiple panels."""
        duration = scene_builder.calculate_panel_duration(
            segment_duration=30.0,
            num_panels=5,
        )

        # 30 seconds / 5 panels = 6 seconds per panel
        assert duration == 6.0

    def test_enforces_minimum_duration(self, scene_builder):
        """Test that minimum 2 second duration is enforced."""
        duration = scene_builder.calculate_panel_duration(
            segment_duration=5.0,
            num_panels=10,  # Would be 0.5s per panel
        )

        # Should enforce minimum of 2 seconds
        assert duration == 2.0

    def test_handles_zero_panels(self, scene_builder):
        """Test handling of zero panels."""
        duration = scene_builder.calculate_panel_duration(
            segment_duration=30.0,
            num_panels=0,
        )

        assert duration == 0.0

    def test_duration_scales_with_segment_duration(self, scene_builder):
        """Test that duration scales with segment duration."""
        duration_short = scene_builder.calculate_panel_duration(
            segment_duration=10.0,
            num_panels=5,
        )
        duration_long = scene_builder.calculate_panel_duration(
            segment_duration=20.0,
            num_panels=5,
        )

        assert duration_short == 2.0  # 10/5 = 2
        assert duration_long == 4.0  # 20/5 = 4


class TestBuildScenes:
    """Tests for build_scenes method."""

    def test_builds_scenes_for_10_panels_over_60_seconds(
        self,
        scene_builder,
        sample_panel_manifest,
        sample_audio_manifest,
    ):
        """Test building scenes for 10 panels over 60 seconds."""
        scenes = scene_builder.build_scenes(
            panel_manifest=sample_panel_manifest,
            audio_manifest=sample_audio_manifest,
        )

        # Should create 10 scenes (one per panel)
        assert len(scenes) == 10

        # Each scene should be ~6 seconds (60s / 10 panels)
        for scene in scenes:
            duration = scene.end_time - scene.start_time
            assert 5.5 <= duration <= 6.5  # Allow small variance

        # Total duration should match audio duration (±1 second)
        total_duration = scenes[-1].end_time
        assert abs(total_duration - 60.0) <= 1.0

    def test_builds_scenes_with_correct_panel_keys(
        self,
        scene_builder,
        sample_panel_manifest,
        sample_audio_manifest,
    ):
        """Test that scenes have correct panel S3 keys."""
        scenes = scene_builder.build_scenes(
            panel_manifest=sample_panel_manifest,
            audio_manifest=sample_audio_manifest,
        )

        # Verify panel keys are in correct order
        expected_keys = [
            "jobs/job-123/panels/0000_0000.jpg",
            "jobs/job-123/panels/0000_0001.jpg",
            "jobs/job-123/panels/0000_0002.jpg",
            "jobs/job-123/panels/0000_0003.jpg",
            "jobs/job-123/panels/0000_0004.jpg",
            "jobs/job-123/panels/0001_0000.jpg",
            "jobs/job-123/panels/0001_0001.jpg",
            "jobs/job-123/panels/0001_0002.jpg",
            "jobs/job-123/panels/0001_0003.jpg",
            "jobs/job-123/panels/0001_0004.jpg",
        ]

        for i, scene in enumerate(scenes):
            assert scene.panel_s3_key == expected_keys[i]

    def test_builds_scenes_with_correct_timing(
        self,
        scene_builder,
        sample_panel_manifest,
        sample_audio_manifest,
    ):
        """Test that scenes have correct start and end times."""
        scenes = scene_builder.build_scenes(
            panel_manifest=sample_panel_manifest,
            audio_manifest=sample_audio_manifest,
        )

        # First scene should start at 0
        assert scenes[0].start_time == 0.0

        # Each scene's start should be previous scene's end
        for i in range(1, len(scenes)):
            assert scenes[i].start_time == scenes[i - 1].end_time

        # Last scene's end should be close to total audio duration
        assert abs(scenes[-1].end_time - 60.0) <= 1.0

    def test_single_panel_over_30_seconds(self, scene_builder):
        """Test scene for a single panel over 30 seconds."""
        panel_manifest = {
            "chapters": [
                {
                    "chapter_id": "ch-001",
                    "panel_keys": ["jobs/job-123/panels/0000_0000.jpg"],
                },
            ],
        }

        audio_manifest = AudioManifest(
            job_id="job-123",
            segments=[
                AudioSegment(
                    index=0,
                    s3_key="jobs/job-123/audio/0000.mp3",
                    duration_seconds=30.0,
                    chapter="1",
                    panel_start=0,
                    panel_end=0,  # Single panel
                ),
            ],
            total_duration_seconds=30.0,
        )

        scenes = scene_builder.build_scenes(
            panel_manifest=panel_manifest,
            audio_manifest=audio_manifest,
        )

        # Should create 1 scene
        assert len(scenes) == 1

        # Scene should show for entire 30 seconds
        assert scenes[0].start_time == 0.0
        assert scenes[0].end_time == 30.0
        assert scenes[0].panel_s3_key == "jobs/job-123/panels/0000_0000.jpg"

    def test_many_panels_with_minimum_duration(self, scene_builder):
        """Test 100 panels over 60 seconds (would be too fast)."""
        # Create 100 panel keys
        panel_keys = [f"jobs/job-123/panels/{i:04d}.jpg" for i in range(100)]

        panel_manifest = {
            "chapters": [
                {
                    "chapter_id": "ch-001",
                    "panel_keys": panel_keys,
                },
            ],
        }

        # 100 panels over 60 seconds = 0.6s per panel
        # But minimum is 2s, so only 30 panels can fit
        audio_manifest = AudioManifest(
            job_id="job-123",
            segments=[
                AudioSegment(
                    index=0,
                    s3_key="jobs/job-123/audio/0000.mp3",
                    duration_seconds=60.0,
                    chapter="1",
                    panel_start=0,
                    panel_end=99,  # 100 panels
                ),
            ],
            total_duration_seconds=60.0,
        )

        scenes = scene_builder.build_scenes(
            panel_manifest=panel_manifest,
            audio_manifest=audio_manifest,
        )

        # Should create 30 scenes (60s / 2s minimum per panel)
        assert len(scenes) == 30

        # Each scene should be exactly 2 seconds
        for scene in scenes:
            duration = scene.end_time - scene.start_time
            assert abs(duration - 2.0) < 0.01

        # Total duration should match audio duration
        total_duration = scenes[-1].end_time
        assert abs(total_duration - 60.0) <= 1.0

    def test_total_duration_matches_audio_duration(
        self,
        scene_builder,
        sample_panel_manifest,
        sample_audio_manifest,
    ):
        """Test that total scene duration matches audio duration."""
        scenes = scene_builder.build_scenes(
            panel_manifest=sample_panel_manifest,
            audio_manifest=sample_audio_manifest,
        )

        total_scene_duration = scenes[-1].end_time if scenes else 0.0
        audio_duration = sample_audio_manifest.total_duration_seconds

        # Duration difference should be within 1 second
        assert abs(total_scene_duration - audio_duration) <= 1.0

    def test_handles_empty_panel_manifest(self, scene_builder):
        """Test handling of empty panel manifest."""
        panel_manifest = {"chapters": []}

        audio_manifest = AudioManifest(
            job_id="job-123",
            segments=[
                AudioSegment(
                    index=0,
                    s3_key="jobs/job-123/audio/0000.mp3",
                    duration_seconds=30.0,
                    chapter="1",
                    panel_start=0,
                    panel_end=4,
                ),
            ],
            total_duration_seconds=30.0,
        )

        scenes = scene_builder.build_scenes(
            panel_manifest=panel_manifest,
            audio_manifest=audio_manifest,
        )

        # Should return empty list
        assert len(scenes) == 0

    def test_handles_empty_audio_manifest(self, scene_builder, sample_panel_manifest):
        """Test handling of empty audio manifest."""
        audio_manifest = AudioManifest(
            job_id="job-123",
            segments=[],
            total_duration_seconds=0.0,
        )

        scenes = scene_builder.build_scenes(
            panel_manifest=sample_panel_manifest,
            audio_manifest=audio_manifest,
        )

        # Should return empty list
        assert len(scenes) == 0

    def test_transitions_accounted_for(
        self,
        scene_builder,
        sample_panel_manifest,
        sample_audio_manifest,
    ):
        """Test that transition duration is set for all scenes."""
        scenes = scene_builder.build_scenes(
            panel_manifest=sample_panel_manifest,
            audio_manifest=sample_audio_manifest,
        )

        # All scenes should have transition_duration set
        for scene in scenes:
            assert scene.transition_duration == 0.5

    def test_scenes_are_sequential(
        self,
        scene_builder,
        sample_panel_manifest,
        sample_audio_manifest,
    ):
        """Test that scenes are sequential with no gaps or overlaps."""
        scenes = scene_builder.build_scenes(
            panel_manifest=sample_panel_manifest,
            audio_manifest=sample_audio_manifest,
        )

        # Check that each scene starts exactly when previous one ends
        for i in range(1, len(scenes)):
            assert scenes[i].start_time == scenes[i - 1].end_time

        # Check that scenes are ordered by start time
        for i in range(1, len(scenes)):
            assert scenes[i].start_time > scenes[i - 1].start_time

    def test_multiple_segments_different_durations(self, scene_builder):
        """Test building scenes from multiple segments with different durations."""
        panel_manifest = {
            "chapters": [
                {
                    "chapter_id": "ch-001",
                    "panel_keys": [
                        f"jobs/job-123/panels/{i:04d}.jpg" for i in range(10)
                    ],
                },
            ],
        }

        audio_manifest = AudioManifest(
            job_id="job-123",
            segments=[
                AudioSegment(
                    index=0,
                    s3_key="jobs/job-123/audio/0000.mp3",
                    duration_seconds=10.0,
                    chapter="1",
                    panel_start=0,
                    panel_end=2,  # 3 panels
                ),
                AudioSegment(
                    index=1,
                    s3_key="jobs/job-123/audio/0001.mp3",
                    duration_seconds=20.0,
                    chapter="1",
                    panel_start=3,
                    panel_end=5,  # 3 panels
                ),
                AudioSegment(
                    index=2,
                    s3_key="jobs/job-123/audio/0002.mp3",
                    duration_seconds=30.0,
                    chapter="1",
                    panel_start=6,
                    panel_end=9,  # 4 panels
                ),
            ],
            total_duration_seconds=60.0,
        )

        scenes = scene_builder.build_scenes(
            panel_manifest=panel_manifest,
            audio_manifest=audio_manifest,
        )

        # Should create 10 scenes total
        assert len(scenes) == 10

        # First 3 scenes: 10s / 3 = 3.33s each
        assert abs((scenes[2].end_time - scenes[0].start_time) - 10.0) < 0.1

        # Next 3 scenes: 20s / 3 = 6.67s each
        assert abs((scenes[5].end_time - scenes[3].start_time) - 20.0) < 0.1

        # Last 4 scenes: 30s / 4 = 7.5s each
        assert abs((scenes[9].end_time - scenes[6].start_time) - 30.0) < 0.1

        # Total duration should be 60 seconds
        assert abs(scenes[-1].end_time - 60.0) <= 1.0

    def test_avg_panel_duration_logged(
        self,
        scene_builder,
        sample_panel_manifest,
        sample_audio_manifest,
    ):
        """Test that average panel duration is calculated correctly."""
        scenes = scene_builder.build_scenes(
            panel_manifest=sample_panel_manifest,
            audio_manifest=sample_audio_manifest,
        )

        # Calculate average duration
        total_duration = scenes[-1].end_time
        avg_duration = total_duration / len(scenes)

        # For 10 panels over 60 seconds, average should be 6 seconds
        assert abs(avg_duration - 6.0) < 0.1


class TestEdgeCases:
    """Tests for edge cases."""

    def test_segment_with_no_panels_in_range(self, scene_builder):
        """Test segment where panel range is out of bounds."""
        panel_manifest = {
            "chapters": [
                {
                    "chapter_id": "ch-001",
                    "panel_keys": [
                        "jobs/job-123/panels/0000_0000.jpg",
                        "jobs/job-123/panels/0000_0001.jpg",
                    ],
                },
            ],
        }

        audio_manifest = AudioManifest(
            job_id="job-123",
            segments=[
                AudioSegment(
                    index=0,
                    s3_key="jobs/job-123/audio/0000.mp3",
                    duration_seconds=30.0,
                    chapter="1",
                    panel_start=5,  # Out of bounds
                    panel_end=10,
                ),
            ],
            total_duration_seconds=30.0,
        )

        scenes = scene_builder.build_scenes(
            panel_manifest=panel_manifest,
            audio_manifest=audio_manifest,
        )

        # Should handle gracefully (empty list or skip segment)
        assert len(scenes) == 0

    def test_very_short_segment(self, scene_builder):
        """Test very short audio segment (< 2 seconds)."""
        panel_manifest = {
            "chapters": [
                {
                    "chapter_id": "ch-001",
                    "panel_keys": [
                        "jobs/job-123/panels/0000_0000.jpg",
                        "jobs/job-123/panels/0000_0001.jpg",
                        "jobs/job-123/panels/0000_0002.jpg",
                    ],
                },
            ],
        }

        audio_manifest = AudioManifest(
            job_id="job-123",
            segments=[
                AudioSegment(
                    index=0,
                    s3_key="jobs/job-123/audio/0000.mp3",
                    duration_seconds=1.5,  # Very short
                    chapter="1",
                    panel_start=0,
                    panel_end=2,  # 3 panels
                ),
            ],
            total_duration_seconds=1.5,
        )

        scenes = scene_builder.build_scenes(
            panel_manifest=panel_manifest,
            audio_manifest=audio_manifest,
        )

        # Should create at least 1 scene
        assert len(scenes) >= 1

        # Total duration should match audio
        if scenes:
            assert abs(scenes[-1].end_time - 1.5) <= 1.0
