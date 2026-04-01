from __future__ import annotations

import os
import uuid
from pathlib import Path

from flask import Blueprint, current_app, jsonify, request
from werkzeug.utils import secure_filename

from app.services.task_processor import create_batch_task, start_task_background_processing
from app.services.task_store import task_store

api_blueprint = Blueprint("api", __name__)

ALLOWED_VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv", ".webm"}


def _is_video_filename(filename: str) -> bool:
    return Path(filename).suffix.lower() in ALLOWED_VIDEO_EXTENSIONS


@api_blueprint.post("/tasks")
def create_task_api():
    """Create task and return taskId immediately for polling mode."""
    files = request.files.getlist("videos")
    if not files:
        return jsonify({"message": "No files uploaded"}), 400

    upload_folder = current_app.config["UPLOAD_FOLDER"]
    saved_videos: list[tuple[str, str]] = []

    for uploaded_file in files:
        if uploaded_file.filename is None or uploaded_file.filename == "":
            continue
        if not _is_video_filename(uploaded_file.filename):
            continue

        safe_name = secure_filename(uploaded_file.filename)
        random_name = f"{uuid.uuid4()}-{safe_name}"
        target_path = os.path.join(upload_folder, random_name)
        uploaded_file.save(target_path)
        saved_videos.append((safe_name, target_path))

    if not saved_videos:
        return jsonify({"message": "No valid video files found"}), 400

    task_record = create_batch_task(saved_videos, current_app.config["TASK_FOLDER"])
    base_media_url = request.host_url.rstrip("/") + "/media"
    start_task_background_processing(task_record.taskId, current_app.config["TASK_FOLDER"], base_media_url)

    return jsonify({"taskId": task_record.taskId, "overallStatus": task_record.overallStatus})


@api_blueprint.get("/tasks/<task_id>")
def get_task_api(task_id: str):
    """Return current task snapshot for frontend polling incremental updates."""
    task_record = task_store.get_task(task_id)
    if task_record is None:
        return jsonify({"message": "Task not found"}), 404
    return jsonify(task_record.to_dict())
