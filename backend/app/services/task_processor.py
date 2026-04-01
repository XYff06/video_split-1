from __future__ import annotations

import os
import threading
import traceback
import uuid
from pathlib import Path

from app.models.task_models import BatchTaskRecord, VideoTaskRecord
from app.services.task_store import task_store
from app.services.video_pipeline import (
    run_continuity_fix,
    run_grouping_with_dfs,
    run_merge_and_export,
    run_scene_detection_and_split,
    write_debug_snapshot,
)


def create_batch_task(video_files: list[tuple[str, str]], task_folder: str) -> BatchTaskRecord:
    """Create a new batch task record with per-video independent state."""
    task_id = str(uuid.uuid4())
    videos: list[VideoTaskRecord] = []

    for order_index, (file_name, source_file_path) in enumerate(video_files, start=1):
        videos.append(
            VideoTaskRecord(
                videoId=f"video-{order_index}",
                orderIndex=order_index,
                fileName=file_name,
                sourceFilePath=source_file_path,
            )
        )

    task_record = BatchTaskRecord(
        taskId=task_id,
        overallStatus="processing",
        totalVideoCount=len(videos),
        finishedVideoCount=0,
        successVideoCount=0,
        failedVideoCount=0,
        currentProcessingVideoId=None,
        videos=videos,
    )
    task_store.create_task(task_record)
    os.makedirs(os.path.join(task_folder, task_id), exist_ok=True)
    return task_record


def start_task_background_processing(task_id: str, task_folder: str, base_media_url: str) -> None:
    """Run serial processing in one background thread.

    Why serial: demo requirement asks one-by-one processing for clear logs and UX.
    """
    thread = threading.Thread(
        target=_process_task_worker,
        args=(task_id, task_folder, base_media_url),
        daemon=True,
    )
    thread.start()


def _process_task_worker(task_id: str, task_folder: str, base_media_url: str) -> None:
    task = task_store.get_task(task_id)
    if task is None:
        return

    task_workspace = os.path.join(task_folder, task_id)

    for video_record in task.videos:
        try:
            task.currentProcessingVideoId = video_record.videoId
            video_record.status = "processing"
            video_record.stage = "scene_detecting"
            video_record.progressText = "Running scene detection"
            video_record.append_log("info", "scene_detecting", "Video entered processing queue")

            original_segments = run_scene_detection_and_split(video_record, task_workspace, base_media_url)

            video_record.stage = "continuity_fixing"
            video_record.progressText = "Running continuity fix"
            candidate_segments = run_continuity_fix(video_record, original_segments)

            video_record.stage = "grouping"
            video_record.progressText = "Running DFS grouping"
            grouping_plan, used_fallback = run_grouping_with_dfs(video_record, candidate_segments)

            if grouping_plan is None:
                raise RuntimeError("Failed to build grouping plan")

            video_record.stage = "merging"
            video_record.progressText = "Merging final business segments"
            final_segments = run_merge_and_export(video_record, task_workspace, grouping_plan, base_media_url)

            video_record.stage = "finished"
            video_record.status = "success"
            video_record.progressText = "Completed"
            video_record.result = {
                "originalSegments": original_segments,
                "candidateBusinessSegments": candidate_segments,
                "finalBusinessSegments": final_segments,
                "usedFallbackPlan": used_fallback,
                "summary": {
                    "beforeContinuityCount": len(original_segments),
                    "afterContinuityCount": len(candidate_segments),
                    "finalSegmentCount": len(final_segments),
                },
            }
            video_record.append_log("success", "finished", "Video processing completed successfully")

            write_debug_snapshot(
                task_workspace,
                f"{video_record.videoId}-debug.json",
                {
                    "video": video_record.fileName,
                    "result": video_record.result,
                },
            )

            task.successVideoCount += 1
        except Exception as error:  # noqa: BLE001
            video_record.status = "failed"
            video_record.stage = "failed"
            video_record.progressText = "Failed"
            video_record.errorMessage = str(error)
            video_record.append_log("error", "failed", f"Video processing failed: {error}")
            video_record.append_log("error", "failed", traceback.format_exc())
            task.failedVideoCount += 1
        finally:
            task.finishedVideoCount += 1

    task.currentProcessingVideoId = None
    task.overallStatus = "finished"
