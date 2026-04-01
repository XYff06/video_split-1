"""Core video processing functions used by Flask API.

This module intentionally keeps each major step independent:
1) Scene detection.
2) Random legal grouping.
3) Group export.

Every function uses explicit names and detailed comments for readability.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from random import Random
import subprocess
from typing import Any

from scenedetect import ContentDetector, SceneManager, VideoManager


MINIMUM_GROUP_DURATION_SECONDS = 6.0
MAXIMUM_GROUP_DURATION_SECONDS = 14.0
MAXIMUM_RANDOM_TRY_COUNT = 100


class GroupingFailure(Exception):
    """Raised when scene grouping cannot produce a legal solution."""


@dataclass
class SceneSegment:
    """Raw scene segment produced by PySceneDetect with full floating precision."""

    scene_index: int
    start_seconds: float
    end_seconds: float
    duration_seconds: float


def detect_scenes_with_original_precision(video_file_path: Path) -> list[SceneSegment]:
    """
    Run PySceneDetect on one video using default detector parameters.

    Important behavior aligned with requirement:
    - Keep original time precision returned by PySceneDetect.
    - Do not round start, end, or duration.
    - Preserve original order from source video timeline.
    """
    video_manager = VideoManager([str(video_file_path)])
    scene_manager = SceneManager()
    # Do not pass custom args: this keeps detector behavior at default settings.
    scene_manager.add_detector(ContentDetector())

    # Downscale factor can improve speed; we leave defaults untouched to avoid
    # modifying detection behavior beyond requested defaults.
    video_manager.start()
    scene_manager.detect_scenes(frame_source=video_manager)
    detected_scene_ranges = scene_manager.get_scene_list()

    scene_segments: list[SceneSegment] = []

    for scene_index, (start_timecode, end_timecode) in enumerate(detected_scene_ranges):
        start_seconds = start_timecode.get_seconds()
        end_seconds = end_timecode.get_seconds()
        duration_seconds = end_seconds - start_seconds

        scene_segments.append(
            SceneSegment(
                scene_index=scene_index,
                start_seconds=start_seconds,
                end_seconds=end_seconds,
                duration_seconds=duration_seconds,
            )
        )

    # PySceneDetect might return empty list for very short or special videos.
    # Fallback to one full-video segment by ffprobe duration so pipeline can continue.
    if not scene_segments:
        full_duration_seconds = probe_video_duration_seconds(video_file_path)
        scene_segments.append(
            SceneSegment(
                scene_index=0,
                start_seconds=0.0,
                end_seconds=full_duration_seconds,
                duration_seconds=full_duration_seconds,
            )
        )

    return scene_segments


def probe_video_duration_seconds(video_file_path: Path) -> float:
    """Use ffprobe to read exact duration when scene detection gives no cuts."""
    command = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        str(video_file_path),
    ]
    result = subprocess.run(command, check=True, capture_output=True, text=True)
    return float(result.stdout.strip())


def group_scene_segments_random_legal(scene_segments: list[SceneSegment]) -> list[list[SceneSegment]]:
    """
    Convert a 1D ordered scene list into a 2D ordered group list.

    Rules:
    - Group boundaries are random.
    - Segment order must remain unchanged.
    - Each group's total duration must be in [6, 14] seconds.
    - Pre-check obvious unsolved cases.
    - Try random greedy up to 100 times.
    - If still failed, use DFS with randomized branch order (bounded, no infinite retry).
    """
    if not scene_segments:
        raise GroupingFailure("No scene segments were detected.")

    for scene_segment in scene_segments:
        if scene_segment.duration_seconds > MAXIMUM_GROUP_DURATION_SECONDS:
            raise GroupingFailure(
                f"Single scene index {scene_segment.scene_index} duration "
                f"{scene_segment.duration_seconds} exceeds {MAXIMUM_GROUP_DURATION_SECONDS}."
            )

    random_generator = Random()

    for _ in range(MAXIMUM_RANDOM_TRY_COUNT):
        random_solution = attempt_random_grouping_once(scene_segments, random_generator)
        if random_solution is not None:
            return random_solution

    dfs_solution = attempt_dfs_grouping_with_random_order(scene_segments, random_generator)
    if dfs_solution is None:
        raise GroupingFailure(
            "No legal grouping solution found after 100 random attempts and DFS fallback."
        )

    return dfs_solution


def attempt_random_grouping_once(
    scene_segments: list[SceneSegment],
    random_generator: Random,
) -> list[list[SceneSegment]] | None:
    """One random pass that keeps continuity and validates each group's duration range."""
    grouped_segments: list[list[SceneSegment]] = []
    current_group: list[SceneSegment] = []
    current_group_duration = 0.0

    for scene_segment in scene_segments:
        can_add_current_segment = (
            current_group_duration + scene_segment.duration_seconds
            <= MAXIMUM_GROUP_DURATION_SECONDS
        )

        if can_add_current_segment:
            current_group.append(scene_segment)
            current_group_duration += scene_segment.duration_seconds
        else:
            # Current group cannot accept this segment, so it must be finalized.
            if current_group_duration < MINIMUM_GROUP_DURATION_SECONDS:
                return None

            grouped_segments.append(current_group)
            current_group = [scene_segment]
            current_group_duration = scene_segment.duration_seconds

        # Random split chance only when duration is already legal minimum.
        if (
            current_group_duration >= MINIMUM_GROUP_DURATION_SECONDS
            and random_generator.random() < 0.35
        ):
            grouped_segments.append(current_group)
            current_group = []
            current_group_duration = 0.0

    if current_group:
        if not (
            MINIMUM_GROUP_DURATION_SECONDS
            <= current_group_duration
            <= MAXIMUM_GROUP_DURATION_SECONDS
        ):
            return None
        grouped_segments.append(current_group)

    if not grouped_segments:
        return None

    return grouped_segments


def attempt_dfs_grouping_with_random_order(
    scene_segments: list[SceneSegment],
    random_generator: Random,
) -> list[list[SceneSegment]] | None:
    """Deterministic-depth DFS with randomized candidate order for better variance."""

    total_segment_count = len(scene_segments)

    def search_from_index(start_index: int) -> list[list[SceneSegment]] | None:
        if start_index >= total_segment_count:
            return []

        candidate_end_indices: list[int] = []
        running_duration = 0.0

        for end_index in range(start_index, total_segment_count):
            running_duration += scene_segments[end_index].duration_seconds

            if running_duration > MAXIMUM_GROUP_DURATION_SECONDS:
                break

            if running_duration >= MINIMUM_GROUP_DURATION_SECONDS:
                candidate_end_indices.append(end_index)

        random_generator.shuffle(candidate_end_indices)

        for end_index in candidate_end_indices:
            current_group = scene_segments[start_index : end_index + 1]
            remaining_solution = search_from_index(end_index + 1)
            if remaining_solution is not None:
                return [current_group] + remaining_solution

        return None

    return search_from_index(0)


def export_grouped_video_segments(
    source_video_path: Path,
    grouped_segments: list[list[SceneSegment]],
    export_output_directory: Path,
) -> list[dict[str, Any]]:
    """
    Export every grouped segment into an mp4 file and return metadata.

    For each group we expose:
    - group_number
    - start_seconds
    - end_seconds
    - total_duration_seconds
    - source_scene_index_range
    - exported_file_path (frontend-resolvable URL path)
    """
    exported_metadata_list: list[dict[str, Any]] = []

    for group_index, grouped_scene_list in enumerate(grouped_segments, start=1):
        group_start_seconds = grouped_scene_list[0].start_seconds
        group_end_seconds = grouped_scene_list[-1].end_seconds
        group_duration_seconds = sum(
            scene_segment.duration_seconds for scene_segment in grouped_scene_list
        )

        first_scene_index = grouped_scene_list[0].scene_index
        last_scene_index = grouped_scene_list[-1].scene_index

        export_file_name = f"group_{group_index:03d}.mp4"
        export_file_path = export_output_directory / export_file_name

        # We use stream copy for speed when possible.
        # If codec/container constraints make copy fail for some source files,
        # users can switch to re-encode command later as an enhancement.
        command = [
            "ffmpeg",
            "-y",
            "-ss",
            str(group_start_seconds),
            "-to",
            str(group_end_seconds),
            "-i",
            str(source_video_path),
            "-c",
            "copy",
            str(export_file_path),
        ]
        subprocess.run(command, check=True, capture_output=True)

        exported_metadata_list.append(
            {
                "group_number": group_index,
                "start_seconds": group_start_seconds,
                "end_seconds": group_end_seconds,
                "total_duration_seconds": group_duration_seconds,
                "source_scene_index_range": [first_scene_index, last_scene_index],
                "exported_file_path": f"/exports/{export_output_directory.name}/{export_file_name}",
            }
        )

    return exported_metadata_list
