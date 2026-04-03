"""Flask 应用入口。

这个文件主要承担控制层职责：
1. 创建 Flask 应用并配置跨域。
2. 定义任务创建、SSE 订阅、媒体访问、裂变生成等接口。
3. 把 HTTP 请求转交给 `task_runtime.py` 中的后台处理逻辑。
"""

import io
import json
import threading
import zipfile
from copy import deepcopy
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict

from flask import Flask, Response, jsonify, request, send_file, send_from_directory
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
# 允许本地前端开发服务器访问当前后端接口。
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
# 当前进程中的任务状态统一保存在这个内存仓库里。
store = TaskStore()


def _safe_zip_stem(raw_name: str, fallback: str) -> str:
    """把视频名转换成适合作为 zip 名称的安全文本。"""

    candidate = Path(raw_name or "").stem.strip()
    return candidate or fallback


def _collect_regroup_files(task, video_indexes: list[int]) -> list[tuple[Path, str]]:
    """按当前任务状态收集需要写入 zip 的重组视频文件。"""

    collected_files: list[tuple[Path, str]] = []

    for video_index in video_indexes:
        if video_index < 0 or video_index >= len(task.video_results):
            continue

        video_result = task.video_results[video_index]
        video_folder = _safe_zip_stem(video_result.get("video_name", ""), f"video_{video_index + 1:03d}")

        for regroup_video in video_result.get("regrouped_videos") or []:
            file_path = Path(regroup_video.get("file_path") or "")
            if not file_path.is_file():
                continue

            archive_name = f"{video_folder}/{file_path.name}"
            collected_files.append((file_path, archive_name))

    return collected_files


def _build_regroup_download_response(task, video_indexes: list[int], download_name: str):
    """把指定视频的重组结果打包成 zip 并直接返回下载响应。"""

    regroup_files = _collect_regroup_files(task, video_indexes)
    if not regroup_files:
        return jsonify({"error": "当前没有可下载的重组视频。"}), 400

    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for file_path, archive_name in regroup_files:
            archive.write(file_path, archive_name)

    zip_buffer.seek(0)
    return send_file(
        zip_buffer,
        mimetype="application/zip",
        as_attachment=True,
        download_name=download_name,
    )


@app.get("/health")
def health() -> Any:
    """健康检查接口，用于确认服务是否正常启动。"""

    return jsonify({"status": "ok"})


@app.post("/api/tasks")
def create_task() -> Any:
    """创建新任务并启动后台视频处理线程。"""

    upload_files = request.files.getlist("videos")
    if not upload_files:
        return jsonify({"error": "没有接收到任何视频文件。"}), 400

    task = store.create_task(total_videos=len(upload_files))
    upload_directory = UPLOAD_ROOT / task.task_id

    # 先记录任务创建日志，再保存上传文件，方便前端展示完整轨迹。
    task.task_logs.append(make_log("info", f"Task {task.task_id} created."))
    saved_video_paths = save_uploaded_files(upload_files, upload_directory)

    if not saved_video_paths:
        return jsonify({"error": "上传文件为空或不是合法视频文件。"}), 400

    task.task_logs.append(make_log("info", f"Saved {len(saved_video_paths)} video files."))

    task_directory = TASK_OUTPUT_ROOT / task.task_id
    # 实际视频处理放到后台线程里做，避免当前请求阻塞太久。
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
    兼容旧调用路径的过渡函数。

    当前真正的视频处理实现已经迁移到 `task_runtime.py`，
    这里保留包装函数是为了避免旧引用立即失效。
    """
    start_processing_task(store, task_id, saved_video_paths, task_directory)


@app.get("/api/tasks/<task_id>/stream")
def stream_task(task_id: str) -> Any:
    """通过 SSE 持续推送任务进度和结果变化。"""

    task = store.get_task(task_id)
    if not task:
        return jsonify({"error": "未找到对应任务。"}), 404

    def event_generator():
        # 首先推送一份完整快照，确保前端刷新后也能恢复任务上下文。
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
            # 阻塞等待后台线程写入新事件，再把增量状态实时推送给前端。
            event = task.event_queue.get()
            yield f"event: {event['event']}\ndata: {json.dumps(event['data'])}\n\n"
            if event["event"] == "task_completed":
                # 任务整体完成后结束当前 SSE 流。
                break

    return Response(event_generator(), mimetype="text/event-stream")


@app.get("/media/<path:relative_path>")
def serve_media(relative_path: str) -> Any:
    """提供 `backend/data` 目录下媒体文件的静态访问。"""

    return send_from_directory(DATA_ROOT, relative_path)


@app.post("/api/tasks/<task_id>/fission/current-video")
def generate_current_video_fissions(task_id: str) -> Any:
    """只针对当前选中的某个视频执行裂变生成。"""

    task = store.get_task(task_id)
    if not task:
        return jsonify({"error": "未找到对应任务。"}), 404

    payload = request.get_json(silent=True) or {}
    video_index = payload.get("videoIndex")
    segments = payload.get("segments") or []
    video_size = payload.get("videoSize")
    if video_index is None or not isinstance(segments, list):
        return jsonify({"error": "缺少当前视频裂变参数。"}), 400

    # 复用批量裂变逻辑，只是这里把参数包装成“单视频列表”。
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
    """对任务中的多个视频批量执行裂变生成。"""

    task = store.get_task(task_id)
    if not task:
        return jsonify({"error": "未找到对应任务。"}), 404

    payload = request.get_json(silent=True) or {}
    videos = payload.get("videos") or []
    global_size = payload.get("globalSize")
    if not isinstance(videos, list) or not videos:
        return jsonify({"error": "缺少全部视频裂变参数。"}), 400

    for video in videos:
        # 某个视频没有单独指定尺寸时，自动继承全局尺寸设置。
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
    """更新某个视频默认的裂变生成尺寸。"""

    task = store.get_task(task_id)
    if not task:
        return jsonify({"error": "Task not found."}), 404

    payload = request.get_json(silent=True) or {}
    use_global = bool(payload.get("useGlobal"))
    size = None if use_global else payload.get("size")
    if not use_global and not size:
        return jsonify({"error": "Missing size."}), 400

    video_result = update_video_generation_size(store, task_id, video_index, size)
    return jsonify({"videoResult": video_result, "videoResults": task.video_results, "taskLogs": task.task_logs})


@app.post("/api/tasks/<task_id>/videos/<int:video_index>/segments/<int:segment_index>/variants")
def add_fission_variant(task_id: str, video_index: int, segment_index: int) -> Any:
    """给某个片段额外追加一个新的裂变变体。"""

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
    """删除某个片段下指定序号的裂变变体。"""

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
    """重新生成某个片段的指定变体。"""

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
    """基于当前片段变体，重新导出该视频的整片重组结果。"""

    task = store.get_task(task_id)
    if not task:
        return jsonify({"error": "Task not found."}), 404

    try:
        video_result = regenerate_video_regroup(store, task_id, video_index)
    except Exception as error:
        return jsonify({"error": str(error)}), 400

    return jsonify({"videoResult": video_result, "videoResults": task.video_results, "taskLogs": task.task_logs})


@app.get("/api/tasks/<task_id>/videos/<int:video_index>/regroup/download")
def download_current_video_regroups(task_id: str, video_index: int) -> Any:
    """下载当前视频的全部重组结果 zip。"""

    task = store.get_task(task_id)
    if not task:
        return jsonify({"error": "Task not found."}), 404

    if video_index < 0 or video_index >= len(task.video_results):
        return jsonify({"error": "Video not found."}), 404

    video_result = task.video_results[video_index]
    video_stem = _safe_zip_stem(video_result.get("video_name", ""), f"video_{video_index + 1:03d}")
    return _build_regroup_download_response(task, [video_index], f"{task_id}_{video_stem}_regroups.zip")


@app.get("/api/tasks/<task_id>/regroup/download")
def download_all_video_regroups(task_id: str) -> Any:
    """下载当前任务下全部视频的重组结果 zip。"""

    task = store.get_task(task_id)
    if not task:
        return jsonify({"error": "Task not found."}), 404

    video_indexes = list(range(len(task.video_results)))
    return _build_regroup_download_response(task, video_indexes, f"{task_id}_all_regroups.zip")


@app.delete("/api/tasks/<task_id>")
def delete_task_artifacts(task_id: str) -> Any:
    """删除某个任务在磁盘上的上传文件和处理产物。"""

    cleanup_directory(UPLOAD_ROOT / task_id)
    cleanup_directory(TASK_OUTPUT_ROOT / task_id)
    return jsonify({"message": "任务输出文件已删除。"})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True, threaded=True)
