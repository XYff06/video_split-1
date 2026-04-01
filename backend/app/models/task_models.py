from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Any


def utc_now_iso() -> str:
    return datetime.utcnow().isoformat(timespec="seconds") + "Z"


@dataclass
class VideoLogEntry:
    time: str
    level: str
    stage: str
    message: str


@dataclass
class VideoTaskRecord:
    videoId: str
    orderIndex: int
    fileName: str
    sourceFilePath: str
    status: str = "pending"
    stage: str = "waiting"
    progressText: str = "Waiting to start"
    logs: list[VideoLogEntry] = field(default_factory=list)
    result: dict[str, Any] | None = None
    errorMessage: str | None = None

    def append_log(self, level: str, stage: str, message: str) -> None:
        self.logs.append(VideoLogEntry(time=utc_now_iso(), level=level, stage=stage, message=message))


@dataclass
class BatchTaskRecord:
    taskId: str
    overallStatus: str
    totalVideoCount: int
    finishedVideoCount: int
    successVideoCount: int
    failedVideoCount: int
    currentProcessingVideoId: str | None
    videos: list[VideoTaskRecord]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
