"""
Flask backend entry for the video upload and split demo.

This module exposes one main API:
- POST /api/process-videos
  Accepts multiple uploaded video files, performs scene detection,
  groups scenes into legal random groups, exports merged clips,
  and returns metadata for frontend preview.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
import traceback
import uuid

from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS

from video_processing import (
    GroupingFailure,
    detect_scenes_with_original_precision,
    export_grouped_video_segments,
    group_scene_segments_random_legal,
)


# Root directory where this backend file is located.
BACKEND_ROOT_DIRECTORY = Path(__file__).resolve().parent
# Directory for uploaded original videos.
UPLOADED_VIDEO_DIRECTORY = BACKEND_ROOT_DIRECTORY / "storage" / "uploads"
# Directory for exported merged clips.
EXPORTED_CLIP_DIRECTORY = BACKEND_ROOT_DIRECTORY / "storage" / "exports"

# Create directories at startup so runtime has a stable filesystem layout.
UPLOADED_VIDEO_DIRECTORY.mkdir(parents=True, exist_ok=True)
EXPORTED_CLIP_DIRECTORY.mkdir(parents=True, exist_ok=True)


app = Flask(__name__)
# Allow cross-origin requests so Vue dev server (typically localhost:5173)
# can call Flask server (typically localhost:5000) during local development.
CORS(app)


@dataclass
class ProcessedVideoResult:
    """Structured response payload for a single processed input video."""

    original_file_name: str
    uploaded_file_path: str
    grouped_segments: list[dict[str, Any]]


@app.get("/api/health")
def health_check() -> Any:
    """Simple readiness endpoint used for local smoke checks."""
    return jsonify({"status": "ok"})


@app.route("/exports/<path:export_relative_path>")
def serve_exported_video(export_relative_path: str) -> Any:
    """Serve exported clips so frontend can preview split results in a <video> element."""
    return send_from_directory(EXPORTED_CLIP_DIRECTORY, export_relative_path)


@app.post("/api/process-videos")
def process_videos() -> Any:
    """
    Receive and process all uploaded videos in one request.

    Workflow for each video:
    1) Save upload to disk.
    2) Detect raw scene segments with PySceneDetect default detector settings.
    3) Randomly group consecutive segments into valid groups (6-14 seconds).
    4) Export each group into an actual merged clip file.
    5) Return metadata for frontend preview.
    """
    uploaded_files = request.files.getlist("videos")

    if not uploaded_files:
        return jsonify({"success": False, "error": "No video files were provided."}), 400

    all_processed_results: list[ProcessedVideoResult] = []

    for uploaded_video in uploaded_files:
        if not uploaded_video.filename:
            continue

        # Add random suffix to avoid collisions when different uploads have same name.
        unique_identifier = uuid.uuid4().hex
        saved_file_name = f"{unique_identifier}_{uploaded_video.filename}"
        saved_file_path = UPLOADED_VIDEO_DIRECTORY / saved_file_name
        uploaded_video.save(saved_file_path)

        try:
            raw_scene_segments = detect_scenes_with_original_precision(saved_file_path)
            grouped_scene_segments = group_scene_segments_random_legal(raw_scene_segments)

            export_folder_name = f"{saved_file_path.stem}_exports"
            export_output_directory = EXPORTED_CLIP_DIRECTORY / export_folder_name
            export_output_directory.mkdir(parents=True, exist_ok=True)

            exported_grouped_segments = export_grouped_video_segments(
                source_video_path=saved_file_path,
                grouped_segments=grouped_scene_segments,
                export_output_directory=export_output_directory,
            )

            all_processed_results.append(
                ProcessedVideoResult(
                    original_file_name=uploaded_video.filename,
                    uploaded_file_path=str(saved_file_path),
                    grouped_segments=exported_grouped_segments,
                )
            )

        except GroupingFailure as grouping_failure:
            return (
                jsonify(
                    {
                        "success": False,
                        "error": f"Grouping failed for file '{uploaded_video.filename}': {str(grouping_failure)}",
                    }
                ),
                422,
            )
        except Exception as unknown_error:  # noqa: BLE001
            traceback.print_exc()
            return (
                jsonify(
                    {
                        "success": False,
                        "error": f"Unexpected processing error for '{uploaded_video.filename}': {str(unknown_error)}",
                    }
                ),
                500,
            )

    return jsonify(
        {
            "success": True,
            "videos": [video_result.__dict__ for video_result in all_processed_results],
        }
    )


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
