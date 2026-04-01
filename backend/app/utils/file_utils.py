import shutil
from pathlib import Path
from uuid import uuid4


def ensure_directory_exists(directory_path: Path) -> None:
    """创建目录（若已存在则跳过），用于确保后续文件写入不失败。"""
    directory_path.mkdir(parents=True, exist_ok=True)


def clear_directory_if_exists(directory_path: Path) -> None:
    """清理目录内容，目的是让每次演示任务有干净输出。"""
    if directory_path.exists() and directory_path.is_dir():
        shutil.rmtree(directory_path)


def generate_safe_task_directory(base_directory: Path, original_file_name: str) -> Path:
    """
    生成唯一任务目录。

    做了什么：把原文件名和随机 UUID 拼成目录名。
    为什么这样做：避免多视频同名冲突、避免并发任务覆盖。
    结果：每个视频都落到独立目录，便于定位和清理。
    """
    safe_file_stem = Path(original_file_name).stem.replace(" ", "_")
    unique_suffix = uuid4().hex[:10]
    task_directory = base_directory / f"{safe_file_stem}_{unique_suffix}"
    ensure_directory_exists(task_directory)
    return task_directory
