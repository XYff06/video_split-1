from __future__ import annotations

import threading
from typing import Callable

from app.models.task_models import BatchTaskRecord, VideoTaskRecord


class InMemoryTaskStore:
    """A simple thread-safe task store.

    What: Keeps all batch/video processing progress available for polling.
    Why: Frontend polls GET /api/tasks/<task_id> and must see incremental updates.
    Result: We can update per-video logs/results live while background worker runs.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._tasks: dict[str, BatchTaskRecord] = {}

    def create_task(self, task: BatchTaskRecord) -> None:
        with self._lock:
            self._tasks[task.taskId] = task

    def get_task(self, task_id: str) -> BatchTaskRecord | None:
        with self._lock:
            return self._tasks.get(task_id)

    def update_task(self, task_id: str, updater: Callable[[BatchTaskRecord], None]) -> None:
        with self._lock:
            task = self._tasks.get(task_id)
            if task is None:
                return
            updater(task)

    def get_video(self, task_id: str, video_id: str) -> VideoTaskRecord | None:
        with self._lock:
            task = self._tasks.get(task_id)
            if not task:
                return None
            for video in task.videos:
                if video.videoId == video_id:
                    return video
            return None


task_store = InMemoryTaskStore()
