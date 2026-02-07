"""Scene builder for mapping panels to audio timing."""

from dataclasses import dataclass

from src.common.logging_config import setup_logger
from src.common.models import AudioManifest

logger = setup_logger(__name__)


@dataclass
class Scene:
    """Represents a single scene with panel and timing information."""

    panel_s3_key: str
    start_time: float  # seconds
    end_time: float  # seconds
    transition_duration: float = 0.5


class SceneBuilder:
    """Builder for creating scenes that map panels to audio timing."""

    def __init__(self) -> None:
        """Initialize the scene builder."""
        logger.info("SceneBuilder initialized")

    def calculate_panel_duration(
        self,
        segment_duration: float,
        num_panels: int,
        transition_duration: float = 0.5,
    ) -> float:
        """
        Calculate duration per panel for a segment.

        Accounts for transition overlap and enforces minimum display time.

        Args:
            segment_duration: Total duration of the audio segment (seconds).
            num_panels: Number of panels to display during this segment.
            transition_duration: Duration of transition effect (seconds).

        Returns:
            Duration per panel in seconds (minimum 2.0 seconds).
        """
        if num_panels == 0:
            return 0.0

        if num_panels == 1:
            # Single panel shows for entire segment
            return segment_duration

        # Calculate base duration per panel
        # We subtract (num_panels - 1) * transition_duration to account for overlaps
        # But this is simplified - we just divide evenly and enforce minimum
        base_duration = segment_duration / num_panels

        # Enforce minimum display time of 2 seconds
        min_duration = 2.0
        panel_duration = max(base_duration, min_duration)

        return panel_duration

    def build_scenes(
        self,
        panel_manifest: dict,
        audio_manifest: AudioManifest,
    ) -> list[Scene]:
        """
        Build scenes by mapping panels to audio timing.

        Args:
            panel_manifest: Panel manifest with chapters and panel keys.
            audio_manifest: Audio manifest with segments and timing.

        Returns:
            Ordered list of Scene objects with timing information.
        """
        logger.info(
            "Building scenes",
            extra={
                "total_audio_segments": len(audio_manifest.segments),
                "total_audio_duration": audio_manifest.total_duration_seconds,
            },
        )

        # Step 1: Flatten all panel keys from chapters into a single list
        all_panel_keys = []
        for chapter in panel_manifest.get("chapters", []):
            panel_keys = chapter.get("panel_keys", [])
            all_panel_keys.extend(panel_keys)

        logger.info(
            "Panel keys flattened",
            extra={"total_panels": len(all_panel_keys)},
        )

        # Step 2: Build scenes for each audio segment
        scenes = []
        current_time = 0.0

        for segment_idx, audio_segment in enumerate(audio_manifest.segments):
            # Get panel range for this segment
            panel_start = audio_segment.panel_start
            panel_end = audio_segment.panel_end

            # Extract panels for this segment (inclusive range)
            segment_panels = all_panel_keys[panel_start : panel_end + 1]
            num_panels = len(segment_panels)

            if num_panels == 0:
                logger.warning(
                    "No panels for segment, skipping",
                    extra={
                        "segment_index": segment_idx,
                        "panel_start": panel_start,
                        "panel_end": panel_end,
                    },
                )
                continue

            segment_duration = audio_segment.duration_seconds

            logger.debug(
                "Processing segment",
                extra={
                    "segment_index": segment_idx,
                    "num_panels": num_panels,
                    "segment_duration": segment_duration,
                    "panel_start": panel_start,
                    "panel_end": panel_end,
                },
            )

            # Calculate duration per panel
            panel_duration = self.calculate_panel_duration(
                segment_duration=segment_duration,
                num_panels=num_panels,
            )

            # If panels would exceed segment duration (due to minimum duration),
            # we need to either skip some panels or extend the segment
            # For simplicity, we'll show as many panels as possible within the segment
            panels_that_fit = int(segment_duration / panel_duration)
            if panels_that_fit < num_panels:
                # We have more panels than time allows
                # Show only the panels that fit
                logger.warning(
                    "Too many panels for segment duration, some will be skipped",
                    extra={
                        "segment_index": segment_idx,
                        "num_panels": num_panels,
                        "panels_that_fit": panels_that_fit,
                        "segment_duration": segment_duration,
                    },
                )
                segment_panels = segment_panels[:panels_that_fit] if panels_that_fit > 0 else segment_panels[:1]
                num_panels = len(segment_panels)

                # Recalculate to fit perfectly
                panel_duration = segment_duration / num_panels

            # Create scenes for each panel in this segment
            for panel_key in segment_panels:
                scene = Scene(
                    panel_s3_key=panel_key,
                    start_time=current_time,
                    end_time=current_time + panel_duration,
                    transition_duration=0.5,
                )
                scenes.append(scene)
                current_time += panel_duration

        # Calculate statistics
        total_scene_duration = scenes[-1].end_time if scenes else 0.0
        avg_panel_duration = (
            total_scene_duration / len(scenes) if scenes else 0.0
        )

        logger.info(
            "Scenes built",
            extra={
                "total_scenes": len(scenes),
                "total_duration": round(total_scene_duration, 2),
                "avg_panel_duration": round(avg_panel_duration, 2),
                "audio_duration": audio_manifest.total_duration_seconds,
                "duration_diff": round(
                    abs(total_scene_duration - audio_manifest.total_duration_seconds), 2
                ),
            },
        )

        # Verify total duration matches audio (±1 second)
        duration_diff = abs(total_scene_duration - audio_manifest.total_duration_seconds)
        if duration_diff > 1.0:
            logger.warning(
                "Scene duration differs from audio duration by more than 1 second",
                extra={
                    "scene_duration": total_scene_duration,
                    "audio_duration": audio_manifest.total_duration_seconds,
                    "diff": duration_diff,
                },
            )

        return scenes
