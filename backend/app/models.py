from dataclasses import asdict, dataclass, field
from datetime import datetime
from queue import Queue
from threading import Lock
from typing import Dict, List, Optional
from uuid import uuid4


@dataclass
class LogEntry:
    timestamp: str
    level: str
    video_name: Optional[str]
    message: str


@dataclass
class VideoProcessResult:
    video_name: str
    status: str
    error_message: Optional[str] = None
    original_scenes: List[dict] = field(default_factory=list)
    merged_segments: List[dict] = field(default_factory=list)
    chosen_grouping_plan: List[List[int]] = field(default_factory=list)
    summary: dict = field(default_factory=dict)
    logs: List[dict] = field(default_factory=list)
    analysis_status: str = "idle"


@dataclass
class TaskState:
    task_id: str
    total_videos: int
    completed_videos: int = 0
    status: str = "processing"
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    task_logs: List[dict] = field(default_factory=list)
    video_results: List[dict] = field(default_factory=list)
    event_queue: Queue = field(default_factory=Queue)


class TaskStore:
    def __init__(self) -> None:
        self._tasks: Dict[str, TaskState] = {}
        self._lock = Lock()

    def create_task(self, total_videos: int) -> TaskState:
        with self._lock:
            task_id = str(uuid4())
            task = TaskState(task_id=task_id, total_videos=total_videos)
            self._tasks[task_id] = task
            return task

    def get_task(self, task_id: str) -> Optional[TaskState]:
        with self._lock:
            return self._tasks.get(task_id)


def make_log(level: str, message: str, video_name: Optional[str] = None) -> dict:
    return asdict(
        LogEntry(
            timestamp=datetime.utcnow().isoformat(),
            level=level,
            video_name=video_name,
            message=message,
        )
    )
