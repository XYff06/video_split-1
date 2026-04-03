"""任务状态、日志结构和内存任务仓库。

这一层负责“后端运行时状态建模”：
1. 用数据类描述日志、单视频结果、整任务状态。
2. 用 `TaskStore` 在内存中保存任务对象。
3. 用 `make_log` 统一日志格式，方便前后端一致消费。
"""

from dataclasses import asdict, dataclass, field
from datetime import datetime
from queue import Queue
from threading import Lock
from typing import Dict, List, Optional
from uuid import uuid4


@dataclass
class LogEntry:
    """单条结构化日志。"""

    timestamp: str
    level: str
    video_name: Optional[str]
    message: str


@dataclass
class VideoProcessResult:
    """单个视频处理完成后的完整结果快照。"""

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
    """整个任务的运行时状态。

    一个任务里可能包含多个视频，因此这里既记录任务级进度，
    也保存每个视频结果和 SSE 推送所需的事件队列。
    """

    task_id: str
    total_videos: int
    completed_videos: int = 0
    status: str = "processing"
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    task_logs: List[dict] = field(default_factory=list)
    video_results: List[dict] = field(default_factory=list)
    event_queue: Queue = field(default_factory=Queue)


class TaskStore:
    """线程安全的内存任务仓库。"""

    def __init__(self) -> None:
        self._tasks: Dict[str, TaskState] = {}
        self._lock = Lock()

    def create_task(self, total_videos: int) -> TaskState:
        # 加锁保证创建任务和写入字典是一个原子过程。
        with self._lock:
            task_id = str(uuid4())
            task = TaskState(task_id=task_id, total_videos=total_videos)
            self._tasks[task_id] = task
            return task

    def get_task(self, task_id: str) -> Optional[TaskState]:
        # 读取时也统一走锁，避免和并发写操作相互干扰。
        with self._lock:
            return self._tasks.get(task_id)


def make_log(level: str, message: str, video_name: Optional[str] = None) -> dict:
    """生成统一格式的日志字典，便于直接序列化为 JSON。"""

    return asdict(
        LogEntry(
            timestamp=datetime.utcnow().isoformat(),
            level=level,
            video_name=video_name,
            message=message,
        )
    )
