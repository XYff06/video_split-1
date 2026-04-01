import json
import threading
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict

from flask import Flask, Response, jsonify, request, send_from_directory
from flask_cors import CORS

from .video_processing import (
    TaskStore,
    cleanup_directory,
    make_log,
    process_single_video,
    save_uploaded_files,
)


BACKEND_ROOT = Path(__file__).resolve().parent.parent
DATA_ROOT = BACKEND_ROOT / "data"
UPLOAD_ROOT = DATA_ROOT / "uploads"
TASK_OUTPUT_ROOT = DATA_ROOT / "tasks"
BASE_PUBLIC_URL = "http://127.0.0.1:5000"

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "http://127.0.0.1:5173"}})

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
    task_directory = TASK_OUTPUT_ROOT / task.task_id
    upload_directory = UPLOAD_ROOT / task.task_id

    task.task_logs.append(make_log("info", f"Task {task.task_id} created."))
    saved_video_paths = save_uploaded_files(upload_files, upload_directory)

    if not saved_video_paths:
        return jsonify({"error": "上传文件为空或不是合法视频文件。"}), 400

    task.task_logs.append(make_log("info", f"Saved {len(saved_video_paths)} video files."))

    processing_thread = threading.Thread(
        target=process_task_videos,
        args=(task.task_id, saved_video_paths, task_directory),
        daemon=True,
    )
    processing_thread.start()

    return jsonify(
        {
            "taskId": task.task_id,
            "totalVideos": len(saved_video_paths),
            "status": task.status,
            "message": "任务创建成功，请连接 SSE 流持续接收增量结果。",
        }
    )


def process_task_videos(task_id: str, saved_video_paths, task_directory: Path) -> None:
    task = store.get_task(task_id)
    if not task:
        return

    task_directory.mkdir(parents=True, exist_ok=True)
    task.task_logs.append(make_log("info", f"Task {task_id} processing started."))

    for video_path in saved_video_paths:
        video_name = video_path.name
        task.task_logs.append(make_log("info", f"Start processing video: {video_name}", video_name=video_name))

        result = process_single_video(
            source_video_path=video_path,
            task_root_directory=task_directory,
            base_public_url=BASE_PUBLIC_URL,
            video_name=video_name,
            task_log_sink=task.task_logs,
        )

        result_payload = asdict(result)
        task.video_results.append(result_payload)
        task.completed_videos += 1
        task.status = "completed" if task.completed_videos == task.total_videos else "processing"

        event_payload: Dict[str, Any] = {
            "taskId": task.task_id,
            "videoName": result.video_name,
            "videoStatus": result.status,
            "videoResult": result_payload,
            "videoLogs": result.logs,
            "completedVideos": task.completed_videos,
            "totalVideos": task.total_videos,
            "taskStatus": task.status,
            "taskLogs": task.task_logs,
        }
        task.event_queue.put({"event": "video_result", "data": event_payload})

    task.task_logs.append(make_log("success", f"Task {task_id} completed."))
    task.event_queue.put(
        {
            "event": "task_completed",
            "data": {
                "taskId": task.task_id,
                "taskStatus": task.status,
                "completedVideos": task.completed_videos,
                "totalVideos": task.total_videos,
                "videoResults": task.video_results,
                "taskLogs": task.task_logs,
            },
        }
    )


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


@app.delete("/api/tasks/<task_id>")
def delete_task_artifacts(task_id: str) -> Any:
    cleanup_directory(UPLOAD_ROOT / task_id)
    cleanup_directory(TASK_OUTPUT_ROOT / task_id)
    return jsonify({"message": "任务输出文件已删除。"})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True, threaded=True)
