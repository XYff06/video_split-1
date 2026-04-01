from pathlib import Path

from flask import Blueprint, jsonify, request, send_from_directory

from app.services.video_processing_service import VideoProcessingService

api_blueprint = Blueprint("api", __name__)

video_processing_service: VideoProcessingService | None = None
processed_directory: Path | None = None


@api_blueprint.route("/health", methods=["GET"])
def health_check():
    return jsonify({"status": "ok", "message": "Video split demo backend is running."})


@api_blueprint.route("/process-videos", methods=["POST"])
def process_videos():
    """
    接收多个视频并逐个处理。

    做了什么：遍历 files 字段中的上传文件，对每个视频独立调用处理服务。
    为什么这样做：即使某个视频失败，其他视频仍可继续处理。
    结果：返回成功结果、失败结果和完整处理日志。
    """
    if video_processing_service is None:
        return jsonify({"message": "服务尚未初始化"}), 500

    uploaded_files = request.files.getlist("files")
    if not uploaded_files:
        return jsonify({"message": "未收到任何文件"}), 400

    successful_videos = []
    failed_videos = []
    processing_logs = []

    for uploaded_file in uploaded_files:
        if not uploaded_file.mimetype.startswith("video/"):
            processing_logs.append(
                {"level": "warning", "message": f"已忽略非视频文件: {uploaded_file.filename}"},
            )
            continue

        processing_result = video_processing_service.process_uploaded_video(uploaded_file)
        processing_logs.extend(
            [
                {
                    "level": one_log["level"],
                    "message": f"[{processing_result['video_name']}] {one_log['message']}",
                }
                for one_log in processing_result.get("logs", [])
            ]
        )

        if processing_result["status"] == "success":
            successful_videos.append(processing_result)
        else:
            failed_videos.append(
                {
                    "video_name": processing_result["video_name"],
                    "error_message": processing_result["message"],
                }
            )

    return jsonify(
        {
            "successful_videos": successful_videos,
            "failed_videos": failed_videos,
            "processing_logs": processing_logs,
        }
    )


@api_blueprint.route("/media/<path:relative_path>", methods=["GET"])
def serve_processed_media(relative_path: str):
    """提供处理后视频文件的静态访问。"""
    if processed_directory is None:
        return jsonify({"message": "媒体目录未初始化"}), 500
    return send_from_directory(processed_directory, relative_path)


def configure_routes(service: VideoProcessingService, processed_dir: Path) -> None:
    global video_processing_service, processed_directory
    video_processing_service = service
    processed_directory = processed_dir
