"""媒体文件相关的通用工具函数。

这些函数不负责业务流程，只负责几个基础能力：
1. 生成前端可访问的媒体 URL。
2. 保存上传文件。
3. 清理任务目录。
"""

import shutil
from pathlib import Path
from urllib.parse import quote


def build_media_url(base_public_url: str, data_root: Path, file_path: Path) -> str:
    """把 data 目录下的真实文件路径转换成浏览器可访问地址。"""

    relative_path = file_path.relative_to(data_root).as_posix()
    return f"{base_public_url}/media/{quote(relative_path, safe='/')}"


def save_uploaded_files(upload_files, upload_directory: Path):
    """把上传文件落盘到指定目录。"""

    upload_directory.mkdir(parents=True, exist_ok=True)
    saved_paths = []
    for upload_file in upload_files:
        # 只保留纯文件名，避免客户端传入路径信息。
        safe_name = Path(upload_file.filename).name
        if not safe_name:
            continue
        target_path = upload_directory / safe_name
        upload_file.save(target_path)
        saved_paths.append(target_path)
    return saved_paths


def cleanup_directory(directory_path: Path) -> None:
    """递归删除目录及其内容。"""

    if directory_path.exists():
        shutil.rmtree(directory_path)
