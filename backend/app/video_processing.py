import json
import os
import random
import shutil
import subprocess
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from queue import Queue
from threading import Lock
from typing import Dict, List, Optional, Tuple
from urllib.parse import quote
from uuid import uuid4

from scenedetect import ContentDetector, SceneManager, open_video
from scenedetect.video_splitter import split_video_ffmpeg


MIN_GROUP_DURATION_SECONDS = 6.0
MAX_GROUP_DURATION_SECONDS = 14.0
MAX_GROUPING_SOLUTIONS = 2376


@dataclass
class LogEntry:
    timestamp: str
    level: str
    video_name: Optional[str]
    message: str


@dataclass
class VideoProcessResult:
    video_name: str
    status: str
    error_message: Optional[str] = None
    original_scenes: List[dict] = field(default_factory=list)
    merged_segments: List[dict] = field(default_factory=list)
    chosen_grouping_plan: List[List[int]] = field(default_factory=list)
    summary: dict = field(default_factory=dict)
    logs: List[dict] = field(default_factory=list)


@dataclass
class TaskState:
    task_id: str
    total_videos: int
    completed_videos: int = 0
    status: str = "processing"
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    task_logs: List[dict] = field(default_factory=list)
    video_results: List[dict] = field(default_factory=list)
    event_queue: Queue = field(default_factory=Queue)


class TaskStore:
    """Thread-safe in-memory task registry for this demo."""

    def __init__(self) -> None:
        self._tasks: Dict[str, TaskState] = {}
        self._lock = Lock()

    def create_task(self, total_videos: int) -> TaskState:
        with self._lock:
            task_id = str(uuid4())
            task = TaskState(task_id=task_id, total_videos=total_videos)
            self._tasks[task_id] = task
            return task

    def get_task(self, task_id: str) -> Optional[TaskState]:
        with self._lock:
            return self._tasks.get(task_id)


def make_log(level: str, message: str, video_name: Optional[str] = None) -> dict:
    return asdict(LogEntry(
        timestamp=datetime.utcnow().isoformat(),
        level=level,
        video_name=video_name,
        message=message,
    ))


def build_media_url(base_public_url: str, data_root: Path, file_path: Path) -> str:
    """
    Build a browser-playable URL from a real file path under backend/data.

    The Flask media route serves files from DATA_ROOT, so preview URLs must keep the
    `tasks/<task_id>/...` prefix. Without that prefix the browser requests the wrong path
    and the merged preview clip returns 404 even though the file actually exists on disk.
    """

    relative_path = file_path.relative_to(data_root).as_posix()
    return f"{base_public_url}/media/{quote(relative_path, safe='/')}"


def detect_and_split_original_scenes(
    source_video_path: Path,
    scene_output_directory: Path,
    base_public_url: str,
    video_name: str,
    append_log,
) -> List[dict]:
    """Detect scenes and use PySceneDetect's ffmpeg splitter to create real scene files."""
    append_log("info", f"Starting scene detection for video: {video_name}")
    data_root = scene_output_directory.parents[3]

    video_stream = open_video(str(source_video_path))
    scene_manager = SceneManager()
    scene_manager.add_detector(ContentDetector())
    scene_manager.detect_scenes(video=video_stream)
    detected_scenes = scene_manager.get_scene_list(start_in_scene=True)

    if not detected_scenes:
        raise RuntimeError("No scenes were detected by PySceneDetect.")

    scene_output_directory.mkdir(parents=True, exist_ok=True)
    append_log("info", f"Detected {len(detected_scenes)} scenes. Starting built-in split operation.")

    split_video_ffmpeg(
        input_video_path=str(source_video_path),
        scene_list=detected_scenes,
        output_dir=scene_output_directory,
        show_progress=False,
    )

    exported_scene_files = sorted(scene_output_directory.glob("*.mp4"))
    if len(exported_scene_files) != len(detected_scenes):
        raise RuntimeError(
            f"Split result mismatch: detected={len(detected_scenes)}, exported={len(exported_scene_files)}"
        )

    original_scenes: List[dict] = []
    for index, ((start_timecode, end_timecode), scene_file_path) in enumerate(
        zip(detected_scenes, exported_scene_files),
        start=1,
    ):
        start_seconds = start_timecode.get_seconds()
        end_seconds = end_timecode.get_seconds()
        duration_seconds = end_seconds - start_seconds
        original_scenes.append(
            {
                "scene_index": index,
                "start_seconds": start_seconds,
                "end_seconds": end_seconds,
                "duration_seconds": duration_seconds,
                "file_path": str(scene_file_path),
                "public_url": build_media_url(base_public_url, data_root, scene_file_path),
            }
        )

    append_log("success", f"Scene split finished. Exported {len(original_scenes)} original scene files.")
    return original_scenes


def search_valid_continuous_groupings(original_scenes: List[dict], append_log) -> Tuple[List[List[List[int]]], bool]:
    append_log("info", "DFS grouping search started.")
    durations = [scene["duration_seconds"] for scene in original_scenes]

    if any(duration > MAX_GROUP_DURATION_SECONDS for duration in durations):
        raise RuntimeError("At least one original scene is longer than 14 seconds, no valid grouping exists.")

    total_duration = sum(durations)
    min_groups = int(total_duration // MAX_GROUP_DURATION_SECONDS)
    max_groups = int(total_duration // MIN_GROUP_DURATION_SECONDS) + 1
    if min_groups > max_groups:
        raise RuntimeError("Total duration cannot be partitioned into contiguous groups of 6-14 seconds.")

    n = len(durations)
    suffix_sum = [0.0] * (n + 1)
    for i in range(n - 1, -1, -1):
        suffix_sum[i] = suffix_sum[i + 1] + durations[i]

    solutions: List[List[List[int]]] = []
    hit_limit = False

    def dfs(start_index: int, plan: List[List[int]]) -> None:
        nonlocal hit_limit
        if hit_limit:
            return
        if start_index == n:
            solutions.append([group[:] for group in plan])
            if len(solutions) >= MAX_GROUPING_SOLUTIONS:
                hit_limit = True
            return

        remaining_duration = suffix_sum[start_index]
        if remaining_duration < MIN_GROUP_DURATION_SECONDS:
            return

        current_duration = 0.0
        current_group: List[int] = []
        for end_index in range(start_index, n):
            current_duration += durations[end_index]
            current_group.append(end_index + 1)

            if current_duration > MAX_GROUP_DURATION_SECONDS:
                break

            if current_duration >= MIN_GROUP_DURATION_SECONDS:
                next_start = end_index + 1
                remaining = suffix_sum[next_start]
                if 0 < remaining < MIN_GROUP_DURATION_SECONDS:
                    continue
                plan.append(current_group[:])
                dfs(next_start, plan)
                plan.pop()
                if hit_limit:
                    return

    dfs(0, [])
    if not solutions:
        raise RuntimeError("Current scene list cannot be partitioned into contiguous groups between 6 and 14 seconds.")

    append_log("success", f"DFS grouping search completed with {len(solutions)} valid solutions.")
    if hit_limit:
        append_log("warning", f"Reached solution cap: {MAX_GROUPING_SOLUTIONS}. Search stopped early.")

    return solutions, hit_limit


def choose_final_grouping_plan(all_grouping_plans: List[List[List[int]]], append_log) -> List[List[int]]:
    shuffled_plans = all_grouping_plans[:]
    random.shuffle(shuffled_plans)
    chosen_plan = random.choice(shuffled_plans)
    append_log("info", f"Selected final grouping plan: {chosen_plan}")
    return chosen_plan


def merge_grouped_scene_files(
    chosen_grouping_plan: List[List[int]],
    original_scenes: List[dict],
    merged_output_directory: Path,
    base_public_url: str,
    append_log,
) -> List[dict]:
    merged_output_directory.mkdir(parents=True, exist_ok=True)
    merged_segments: List[dict] = []
    data_root = merged_output_directory.parents[3]

    for group_index, scene_indices in enumerate(chosen_grouping_plan, start=1):
        selected_scenes = [original_scenes[idx - 1] for idx in scene_indices]
        concat_file_path = merged_output_directory / f"group_{group_index:03d}_concat.txt"
        merged_file_path = merged_output_directory / f"group_{group_index:03d}.mp4"

        with concat_file_path.open("w", encoding="utf-8") as concat_file:
            for scene in selected_scenes:
                safe_path = scene["file_path"].replace("'", "'\\''")
                concat_file.write(f"file '{safe_path}'\n")

        ffmpeg_command = [
            "ffmpeg",
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(concat_file_path),
            "-c",
            "copy",
            str(merged_file_path),
        ]
        command_result = subprocess.run(
            ffmpeg_command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        if command_result.returncode != 0:
            stderr_text = command_result.stderr.decode("utf-8", errors="replace")
            raise RuntimeError(f"ffmpeg merge failed for group {group_index}: {stderr_text}")

        concat_file_path.unlink(missing_ok=True)

        start_seconds = selected_scenes[0]["start_seconds"]
        end_seconds = selected_scenes[-1]["end_seconds"]
        duration_seconds = end_seconds - start_seconds
        merged_segments.append(
            {
                "group_index": group_index,
                "start_seconds": start_seconds,
                "end_seconds": end_seconds,
                "duration_seconds": duration_seconds,
                "source_scene_index_range": [scene_indices[0], scene_indices[-1]],
                "source_scene_files": [scene["file_path"] for scene in selected_scenes],
                "export_file_path": str(merged_file_path),
                "export_public_url": build_media_url(base_public_url, data_root, merged_file_path),
            }
        )

    append_log("success", f"Merged grouped scenes into {len(merged_segments)} final segments.")
    return merged_segments


def process_single_video(
    source_video_path: Path,
    task_root_directory: Path,
    base_public_url: str,
    video_name: str,
    task_log_sink: List[dict],
) -> VideoProcessResult:
    video_logs: List[dict] = []

    def append_video_log(level: str, message: str):
        entry = make_log(level, message, video_name)
        video_logs.append(entry)
        task_log_sink.append(entry)

    try:
        scene_directory = task_root_directory / "original_scenes" / source_video_path.stem
        merged_directory = task_root_directory / "merged_segments" / source_video_path.stem

        original_scenes = detect_and_split_original_scenes(
            source_video_path=source_video_path,
            scene_output_directory=scene_directory,
            base_public_url=base_public_url,
            video_name=video_name,
            append_log=append_video_log,
        )

        all_groupings, _ = search_valid_continuous_groupings(original_scenes, append_video_log)
        chosen_plan = choose_final_grouping_plan(all_groupings, append_video_log)
        merged_segments = merge_grouped_scene_files(
            chosen_grouping_plan=chosen_plan,
            original_scenes=original_scenes,
            merged_output_directory=merged_directory,
            base_public_url=base_public_url,
            append_log=append_video_log,
        )

        summary = {
            "original_scene_count": len(original_scenes),
            "merged_segment_count": len(merged_segments),
            "total_original_duration_seconds": sum(scene["duration_seconds"] for scene in original_scenes),
            "total_merged_duration_seconds": sum(segment["duration_seconds"] for segment in merged_segments),
        }
        append_video_log("success", "Video processing completed successfully.")

        return VideoProcessResult(
            video_name=video_name,
            status="success",
            original_scenes=original_scenes,
            merged_segments=merged_segments,
            chosen_grouping_plan=chosen_plan,
            summary=summary,
            logs=video_logs,
        )

    except Exception as error:
        append_video_log("error", f"Video processing failed: {error}")
        return VideoProcessResult(
            video_name=video_name,
            status="failed",
            error_message=str(error),
            logs=video_logs,
            summary={"original_scene_count": 0, "merged_segment_count": 0},
        )


def save_uploaded_files(upload_files, upload_directory: Path) -> List[Path]:
    upload_directory.mkdir(parents=True, exist_ok=True)
    saved_paths: List[Path] = []
    for upload_file in upload_files:
        safe_name = Path(upload_file.filename).name
        if not safe_name:
            continue
        target_path = upload_directory / safe_name
        upload_file.save(target_path)
        saved_paths.append(target_path)
    return saved_paths


def cleanup_directory(directory_path: Path) -> None:
    if directory_path.exists():
        shutil.rmtree(directory_path)
