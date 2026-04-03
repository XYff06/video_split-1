import json
import threading
from copy import deepcopy
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict

from flask import Flask, Response, jsonify, request, send_from_directory
from flask_cors import CORS

from .config import DATA_ROOT, TASK_OUTPUT_ROOT, UPLOAD_ROOT
from .media_utils import cleanup_directory, save_uploaded_files
from .models import TaskStore, make_log
from .task_runtime import (
    add_segment_variant,
    delete_segment_variant,
    redo_segment_variant,
    regenerate_video_regroup,
    run_fission_generation,
    start_processing_task,
    stream_task_events,
    update_video_generation_size,
)


app = Flask(__name__)
CORS(
    app,
    resources={
        r"/*": {
            "origins": [
                "http://127.0.0.1:5173",
                "http://127.0.0.1:4173",
                "http://localhost:5173",
                "http://localhost:4173",
            ]
        }
    },
)
store = TaskStore()


@app.get("/health")
def health() -> Any:
    return jsonify({"status": "ok"})


@app.post("/api/tasks")
def create_task() -> Any:
    upload_files = request.files.getlist("videos")
    if not upload_files:
        return jsonify({"error": "没有接收到任何视频文件。"}), 400

    task = store.create_task(total_videos=len(upload_files))
    upload_directory = UPLOAD_ROOT / task.task_id

    task.task_logs.append(make_log("info", f"Task {task.task_id} created."))
    saved_video_paths = save_uploaded_files(upload_files, upload_directory)

    if not saved_video_paths:
        return jsonify({"error": "上传文件为空或不是合法视频文件。"}), 400

    task.task_logs.append(make_log("info", f"Saved {len(saved_video_paths)} video files."))

    task_directory = TASK_OUTPUT_ROOT / task.task_id
    start_processing_task(store, task.task_id, saved_video_paths, task_directory)

    return jsonify(
        {
            "taskId": task.task_id,
            "totalVideos": len(saved_video_paths),
            "status": task.status,
            "message": "任务创建成功，请连接 SSE 流持续接收增量结果。",
        }
    )


def process_task_videos(task_id: str, saved_video_paths, task_directory: Path) -> None:
    """
    Legacy shim retained temporarily so existing imports or references do not break.
    The active processing implementation now lives in `task_runtime.py`.
    """
    start_processing_task(store, task_id, saved_video_paths, task_directory)


@app.get("/api/tasks/<task_id>/stream")
def stream_task(task_id: str) -> Any:
    task = store.get_task(task_id)
    if not task:
        return jsonify({"error": "未找到对应任务。"}), 404

    def event_generator():
        initial_payload = {
            "taskId": task.task_id,
            "taskStatus": task.status,
            "completedVideos": task.completed_videos,
            "totalVideos": task.total_videos,
            "videoResults": task.video_results,
            "taskLogs": task.task_logs,
        }
        yield f"event: task_snapshot\ndata: {json.dumps(initial_payload)}\n\n"

        while True:
            event = task.event_queue.get()
            yield f"event: {event['event']}\ndata: {json.dumps(event['data'])}\n\n"
            if event["event"] == "task_completed":
                break

    return Response(event_generator(), mimetype="text/event-stream")


@app.get("/media/<path:relative_path>")
def serve_media(relative_path: str) -> Any:
    return send_from_directory(DATA_ROOT, relative_path)


@app.post("/api/tasks/<task_id>/fission/current-video")
def generate_current_video_fissions(task_id: str) -> Any:
    task = store.get_task(task_id)
    if not task:
        return jsonify({"error": "未找到对应任务。"}), 404

    payload = request.get_json(silent=True) or {}
    video_index = payload.get("videoIndex")
    segments = payload.get("segments") or []
    video_size = payload.get("videoSize")
    if video_index is None or not isinstance(segments, list):
        return jsonify({"error": "缺少当前视频裂变参数。"}), 400

    run_fission_generation(store, task_id, [{"videoIndex": int(video_index), "segments": segments, "videoSize": video_size}])
    return jsonify(
        {
            "message": "当前视频裂变任务已完成。",
            "videoResults": task.video_results,
            "taskLogs": task.task_logs,
        }
    )


@app.post("/api/tasks/<task_id>/fission/all-videos")
def generate_all_video_fissions(task_id: str) -> Any:
    task = store.get_task(task_id)
    if not task:
        return jsonify({"error": "未找到对应任务。"}), 404

    payload = request.get_json(silent=True) or {}
    videos = payload.get("videos") or []
    global_size = payload.get("globalSize")
    if not isinstance(videos, list) or not videos:
        return jsonify({"error": "缺少全部视频裂变参数。"}), 400

    for video in videos:
        if global_size and not video.get("videoSize"):
            video["videoSize"] = global_size

    run_fission_generation(store, task_id, videos)
    return jsonify(
        {
            "message": "全部视频裂变任务已完成。",
            "videoResults": task.video_results,
            "taskLogs": task.task_logs,
        }
    )


@app.post("/api/tasks/<task_id>/videos/<int:video_index>/size")
def update_video_fission_size(task_id: str, video_index: int) -> Any:
    task = store.get_task(task_id)
    if not task:
        return jsonify({"error": "Task not found."}), 404

    payload = request.get_json(silent=True) or {}
    size = payload.get("size")
    if not size:
        return jsonify({"error": "Missing size."}), 400

    video_result = update_video_generation_size(store, task_id, video_index, size)
    return jsonify({"videoResult": video_result, "videoResults": task.video_results, "taskLogs": task.task_logs})


@app.post("/api/tasks/<task_id>/videos/<int:video_index>/segments/<int:segment_index>/variants")
def add_fission_variant(task_id: str, video_index: int, segment_index: int) -> Any:
    task = store.get_task(task_id)
    if not task:
        return jsonify({"error": "Task not found."}), 404

    try:
        segment = add_segment_variant(store, task_id, video_index, segment_index)
    except Exception as error:
        return jsonify({"error": str(error)}), 400

    return jsonify({"segment": segment, "videoResults": task.video_results, "taskLogs": task.task_logs})


@app.delete("/api/tasks/<task_id>/videos/<int:video_index>/segments/<int:segment_index>/variants/<int:variant_index>")
def remove_fission_variant(task_id: str, video_index: int, segment_index: int, variant_index: int) -> Any:
    task = store.get_task(task_id)
    if not task:
        return jsonify({"error": "Task not found."}), 404

    try:
        segment = delete_segment_variant(store, task_id, video_index, segment_index, variant_index)
    except Exception as error:
        return jsonify({"error": str(error)}), 400

    return jsonify({"segment": segment, "videoResults": task.video_results, "taskLogs": task.task_logs})


@app.post("/api/tasks/<task_id>/videos/<int:video_index>/segments/<int:segment_index>/variants/<int:variant_index>/redo")
def redo_fission_variant(task_id: str, video_index: int, segment_index: int, variant_index: int) -> Any:
    task = store.get_task(task_id)
    if not task:
        return jsonify({"error": "Task not found."}), 404

    try:
        segment = redo_segment_variant(store, task_id, video_index, segment_index, variant_index)
    except Exception as error:
        return jsonify({"error": str(error)}), 400

    return jsonify({"segment": segment, "videoResults": task.video_results, "taskLogs": task.task_logs})


@app.post("/api/tasks/<task_id>/videos/<int:video_index>/regroup")
def regroup_single_video(task_id: str, video_index: int) -> Any:
    task = store.get_task(task_id)
    if not task:
        return jsonify({"error": "Task not found."}), 404

    try:
        video_result = regenerate_video_regroup(store, task_id, video_index)
    except Exception as error:
        return jsonify({"error": str(error)}), 400

    return jsonify({"videoResult": video_result, "videoResults": task.video_results, "taskLogs": task.task_logs})


@app.delete("/api/tasks/<task_id>")
def delete_task_artifacts(task_id: str) -> Any:
    cleanup_directory(UPLOAD_ROOT / task_id)
    cleanup_directory(TASK_OUTPUT_ROOT / task_id)
    return jsonify({"message": "任务输出文件已删除。"})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True, threaded=True)
