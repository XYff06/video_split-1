"""Merge grouped contiguous scene segments into exported video clips."""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List

from moviepy.editor import VideoFileClip

from app.utils.time_utils import format_seconds_to_timestamp

OriginalSegment = Dict[str, float | int | str]
SegmentGroup = List[OriginalSegment]
MergedSegmentResult = Dict[str, float | int | str]


def export_grouped_segments(
    source_video_path: Path,
    grouped_segments: List[SegmentGroup],
    output_directory_path: Path,
) -> List[MergedSegmentResult]:
    """Export each legal group to an independent mp4 file.

    We derive group start/end from first and last original segment so the merged output
    strictly respects original order and contiguous grouping boundaries.
    """

    output_directory_path.mkdir(parents=True, exist_ok=True)
    merged_results: List[MergedSegmentResult] = []

    with VideoFileClip(str(source_video_path)) as source_video_clip:
        for group_number, segment_group in enumerate(grouped_segments, start=1):
            group_start_seconds = float(segment_group[0]["start_seconds"])
            group_end_seconds = float(segment_group[-1]["end_seconds"])
            group_duration_seconds = group_end_seconds - group_start_seconds

            output_file_name = f"group_{group_number:03d}.mp4"
            output_file_path = output_directory_path / output_file_name

            clipped_video = source_video_clip.subclip(group_start_seconds, group_end_seconds)
            clipped_video.write_videofile(
                str(output_file_path),
                codec="libx264",
                audio_codec="aac",
                verbose=False,
                logger=None,
            )
            clipped_video.close()

            included_indices = [int(segment["segment_index"]) for segment in segment_group]
            merged_results.append(
                {
                    "group_number": group_number,
                    "start_seconds": group_start_seconds,
                    "end_seconds": group_end_seconds,
                    "duration_seconds": group_duration_seconds,
                    "start_timestamp": format_seconds_to_timestamp(group_start_seconds),
                    "end_timestamp": format_seconds_to_timestamp(group_end_seconds),
                    "duration_timestamp": format_seconds_to_timestamp(group_duration_seconds),
                    "included_segment_index_start": min(included_indices),
                    "included_segment_index_end": max(included_indices),
                    "export_file_path": str(output_file_path),
                    "export_file_name": output_file_name,
                }
            )

    return merged_results
