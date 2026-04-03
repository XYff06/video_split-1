import shutil
from pathlib import Path
from urllib.parse import quote


def build_media_url(base_public_url: str, data_root: Path, file_path: Path) -> str:
    relative_path = file_path.relative_to(data_root).as_posix()
    return f"{base_public_url}/media/{quote(relative_path, safe='/')}"


def save_uploaded_files(upload_files, upload_directory: Path):
    upload_directory.mkdir(parents=True, exist_ok=True)
    saved_paths = []
    for upload_file in upload_files:
        safe_name = Path(upload_file.filename).name
        if not safe_name:
            continue
        target_path = upload_directory / safe_name
        upload_file.save(target_path)
        saved_paths.append(target_path)
    return saved_paths


def cleanup_directory(directory_path: Path) -> None:
    if directory_path.exists():
        shutil.rmtree(directory_path)
