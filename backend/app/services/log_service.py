"""Simple in-memory log collector + disk writer for each processing request."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import List

from app.config import PROCESS_LOG_DIRECTORY_PATH


@dataclass
class ProcessLogCollector:
    """Collects chronological log lines for one API request.

    The same collector instance is passed to all processing services so we can return a
    complete operation trail to frontend while also saving it to a file.
    """

    lines: List[str] = field(default_factory=list)

    def add(self, message: str) -> None:
        utc_now = datetime.now(timezone.utc).isoformat()
        self.lines.append(f"[{utc_now}] {message}")

    def flush_to_file(self) -> str:
        PROCESS_LOG_DIRECTORY_PATH.mkdir(parents=True, exist_ok=True)
        file_name = f"process_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')}.log"
        log_file_path = Path(PROCESS_LOG_DIRECTORY_PATH) / file_name
        log_file_path.write_text("\n".join(self.lines), encoding="utf-8")
        return str(log_file_path)
