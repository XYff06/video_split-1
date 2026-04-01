"""Application configuration for the Flask backend demo."""

from pathlib import Path

# Define backend root so every other path is stable regardless of where command runs.
BACKEND_ROOT_PATH = Path(__file__).resolve().parent.parent
UPLOAD_DIRECTORY_PATH = BACKEND_ROOT_PATH / "uploads"
PROCESSED_OUTPUT_DIRECTORY_PATH = BACKEND_ROOT_PATH / "processed"
PROCESS_LOG_DIRECTORY_PATH = BACKEND_ROOT_PATH / "logs"

# Supported file extensions used as a second line of defense after MIME type checks.
ALLOWED_VIDEO_EXTENSIONS = {".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v"}

# Group duration boundaries from the requirement.
MINIMUM_GROUP_DURATION_SECONDS = 6.0
MAXIMUM_GROUP_DURATION_SECONDS = 14.0

# Limits to prevent unbounded compute.
MAXIMUM_RANDOM_GROUP_ATTEMPTS = 100
MAXIMUM_DFS_SOLUTION_COLLECTION = 1000
