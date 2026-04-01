"""Flask application entry for video upload/split demo."""

from __future__ import annotations

from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS

from app.config import PROCESSED_OUTPUT_DIRECTORY_PATH
from app.services.log_service import ProcessLogCollector
from app.services.video_processor_service import process_single_video_file


def create_application() -> Flask:
    application = Flask(__name__)
    CORS(application)

    @application.get("/api/health")
    def health_check():
        return jsonify({"status": "ok"})

    @application.route('/processed/<path:requested_path>', methods=['GET'])
    def serve_processed_video(requested_path: str):
        return send_from_directory(PROCESSED_OUTPUT_DIRECTORY_PATH, requested_path)

    @application.post("/api/videos/process")
    def process_uploaded_videos():
        uploaded_video_files = request.files.getlist("videos")
        if not uploaded_video_files:
            return jsonify({"message": "No uploaded files found in 'videos' field."}), 400

        process_log_collector = ProcessLogCollector()
        successful_videos = []
        failed_videos = []

        for uploaded_video in uploaded_video_files:
            per_video_result = process_single_video_file(uploaded_video, process_log_collector)
            if per_video_result.get("status") == "success":
                successful_videos.append(per_video_result)
            else:
                failed_videos.append(per_video_result)

        log_file_path = process_log_collector.flush_to_file()

        return jsonify(
            {
                "successful_videos": successful_videos,
                "failed_videos": failed_videos,
                "process_logs": process_log_collector.lines,
                "log_file_path": log_file_path,
            }
        )

    return application


application = create_application()

if __name__ == "__main__":
    application.run(debug=True, host="0.0.0.0", port=5000)
