"""Scene detection service based on PySceneDetect with default parameters only."""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List

from scenedetect import ContentDetector, SceneManager, VideoManager

from app.utils.time_utils import format_seconds_to_timestamp


OriginalSegment = Dict[str, float | int | str]


def detect_original_segments(video_file_path: Path) -> List[OriginalSegment]:
    """Detect ordered scene segments for a single video.

    Why this approach:
    - Requirement explicitly asks for PySceneDetect and default parameters.
    - We instantiate ContentDetector() without custom thresholds.
    - We keep exact float seconds from SceneTimecode.get_seconds() with no rounding.

    Result:
    - Ordered list containing segment index, raw start/end/duration second values and
      readable timestamp strings.
    """

    video_manager = VideoManager([str(video_file_path)])
    scene_manager = SceneManager()
    scene_manager.add_detector(ContentDetector())

    # Start lifecycle and perform scene detection in a deterministic order.
    video_manager.start()
    scene_manager.detect_scenes(frame_source=video_manager)
    scene_list = scene_manager.get_scene_list()
    video_manager.release()

    if not scene_list:
        raise ValueError("PySceneDetect did not return any scene boundaries for this video.")

    original_segments: List[OriginalSegment] = []
    for segment_index, (start_timecode, end_timecode) in enumerate(scene_list, start=1):
        start_seconds = start_timecode.get_seconds()
        end_seconds = end_timecode.get_seconds()
        duration_seconds = end_seconds - start_seconds

        original_segments.append(
            {
                "segment_index": segment_index,
                "start_seconds": start_seconds,
                "end_seconds": end_seconds,
                "duration_seconds": duration_seconds,
                "start_timestamp": format_seconds_to_timestamp(start_seconds),
                "end_timestamp": format_seconds_to_timestamp(end_seconds),
                "duration_timestamp": format_seconds_to_timestamp(duration_seconds),
            }
        )

    return original_segments
