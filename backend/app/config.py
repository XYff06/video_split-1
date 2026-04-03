from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parent.parent
DATA_ROOT = BACKEND_ROOT / "data"
UPLOAD_ROOT = DATA_ROOT / "uploads"
TASK_OUTPUT_ROOT = DATA_ROOT / "tasks"
BASE_PUBLIC_URL = "http://127.0.0.1:5000"
