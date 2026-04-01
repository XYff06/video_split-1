"""High-level per-video processing pipeline orchestration."""

from __future__ import annotations

from pathlib import Path
from typing import Dict

from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename

from app.config import ALLOWED_VIDEO_EXTENSIONS, PROCESSED_OUTPUT_DIRECTORY_PATH, UPLOAD_DIRECTORY_PATH
from app.services.grouping_service import build_random_legal_groups
from app.services.log_service import ProcessLogCollector
from app.services.scene_detect_service import detect_original_segments
from app.services.video_merge_service import export_grouped_segments


VideoProcessResult = Dict[str, object]


def _is_allowed_video_file(file_storage: FileStorage) -> bool:
    """Validate MIME type and extension to prevent obvious invalid uploads."""

    if not file_storage.mimetype.startswith("video/"):
        return False

    extension = Path(file_storage.filename or "").suffix.lower()
    return extension in ALLOWED_VIDEO_EXTENSIONS


def process_single_video_file(uploaded_file: FileStorage, log_collector: ProcessLogCollector) -> VideoProcessResult:
    """Process one uploaded video and return either success payload or detailed error."""

    original_file_name = uploaded_file.filename or "unnamed_video"
    safe_file_name = secure_filename(original_file_name)

    if not safe_file_name or not _is_allowed_video_file(uploaded_file):
        reason = "Uploaded file is not a supported video format."
        log_collector.add(f"[FAILED] {original_file_name}: {reason}")
        return {"video_name": original_file_name, "status": "failed", "error": reason}

    UPLOAD_DIRECTORY_PATH.mkdir(parents=True, exist_ok=True)
    video_upload_path = UPLOAD_DIRECTORY_PATH / safe_file_name
    uploaded_file.save(video_upload_path)
    log_collector.add(f"[START] {original_file_name}: saved to {video_upload_path}")

    try:
        original_segments = detect_original_segments(video_upload_path)
        log_collector.add(
            f"[SCENE_DETECTION] {original_file_name}: detected {len(original_segments)} ordered original segments."
        )

        grouped_segments, grouping_message = build_random_legal_groups(original_segments)
        if grouped_segments is None:
            log_collector.add(
                f"[GROUPING_FAILED] {original_file_name}: random attempts exhausted, DFS no legal grouping. reason={grouping_message}"
            )
            return {
                "video_name": original_file_name,
                "status": "failed",
                "error": grouping_message,
                "original_segments": original_segments,
            }

        log_collector.add(f"[GROUPING_SUCCESS] {original_file_name}: {grouping_message}, groups={len(grouped_segments)}")

        per_video_output_directory = PROCESSED_OUTPUT_DIRECTORY_PATH / Path(safe_file_name).stem
        merged_segments = export_grouped_segments(video_upload_path, grouped_segments, per_video_output_directory)

        log_collector.add(
            f"[SUCCESS] {original_file_name}: exported {len(merged_segments)} merged files to {per_video_output_directory}"
        )

        return {
            "video_name": original_file_name,
            "status": "success",
            "original_segments": original_segments,
            "grouped_segment_count": len(grouped_segments),
            "merged_segments": merged_segments,
        }

    except Exception as processing_exception:  # Keep request alive for other videos.
        error_text = str(processing_exception)
        log_collector.add(f"[FAILED] {original_file_name}: exception={error_text}")
        return {"video_name": original_file_name, "status": "failed", "error": error_text}
