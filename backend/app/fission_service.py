import math
import os
import shutil
import time
from pathlib import Path

import requests
from dotenv import load_dotenv

from .media_utils import build_media_url


load_dotenv()

WAN_BASE_URL = os.getenv("DASHSCOPE_BASE_HTTP_API_URL", "https://dashscope.aliyuncs.com/api/v1")
WAN_MODEL = os.getenv("WAN_MODEL", "wan2.6-t2v")
WAN_SIZE = os.getenv("WAN_SIZE", "1920*1080")
WAN_PROMPT_EXTEND = os.getenv("WAN_PROMPT_EXTEND", "true").lower() == "true"
WAN_WATERMARK = os.getenv("WAN_WATERMARK", "false").lower() == "true"
WAN_NEGATIVE_PROMPT = os.getenv("WAN_NEGATIVE_PROMPT")
WAN_REQUEST_TIMEOUT = int(os.getenv("WAN_REQUEST_TIMEOUT", "120"))
WAN_POLL_INTERVAL_SECONDS = int(os.getenv("WAN_POLL_INTERVAL_SECONDS", "15"))
WAN_MAX_WAIT_SECONDS = int(os.getenv("WAN_MAX_WAIT_SECONDS", "1800"))


class WanTextToVideoClient:
    def __init__(self, api_key: str, base_url: str = WAN_BASE_URL, request_timeout: int = WAN_REQUEST_TIMEOUT):
        if not api_key:
            raise ValueError("Missing DASHSCOPE_API_KEY")
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.request_timeout = request_timeout

    def _build_headers(self, enable_async: bool = False) -> dict:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        if enable_async:
            headers["X-DashScope-Async"] = "enable"
        return headers

    def create_text_to_video_task(
        self,
        *,
        prompt: str,
        model: str = WAN_MODEL,
        size: str = WAN_SIZE,
        duration: int,
        prompt_extend: bool = WAN_PROMPT_EXTEND,
        watermark: bool = WAN_WATERMARK,
        negative_prompt: str | None = WAN_NEGATIVE_PROMPT,
        shot_type: str = "multi",
    ) -> dict:
        if not prompt or not prompt.strip():
            raise ValueError("prompt cannot be empty")

        request_body = {
            "model": model,
            "input": {"prompt": prompt.strip()},
            "parameters": {
                "size": size,
                "duration": duration,
                "prompt_extend": prompt_extend,
                "watermark": watermark,
                "shot_type": shot_type,
            },
        }
        if negative_prompt:
            request_body["input"]["negative_prompt"] = negative_prompt

        response = requests.post(
            f"{self.base_url}/services/aigc/video-generation/video-synthesis",
            headers=self._build_headers(enable_async=True),
            json=request_body,
            timeout=self.request_timeout,
        )
        response.raise_for_status()
        response_data = response.json()
        if response_data.get("code"):
            raise RuntimeError(
                f"Create task failed code={response_data.get('code')} message={response_data.get('message')}"
            )
        return response_data

    def fetch_task_result(self, task_id: str) -> dict:
        response = requests.get(
            f"{self.base_url}/tasks/{task_id}",
            headers=self._build_headers(enable_async=False),
            timeout=self.request_timeout,
        )
        response.raise_for_status()
        response_data = response.json()
        if response_data.get("code"):
            raise RuntimeError(
                f"Fetch task failed code={response_data.get('code')} message={response_data.get('message')}"
            )
        return response_data

    def wait_until_finished(
        self,
        task_id: str,
        poll_interval_seconds: int = WAN_POLL_INTERVAL_SECONDS,
        max_wait_seconds: int = WAN_MAX_WAIT_SECONDS,
    ) -> dict:
        start_time = time.time()
        while True:
            result = self.fetch_task_result(task_id)
            output = result.get("output") or {}
            task_status = output.get("task_status")

            if task_status == "SUCCEEDED":
                return result
            if task_status in {"FAILED", "CANCELED", "UNKNOWN"}:
                raise RuntimeError(
                    f"Task failed status={task_status} code={output.get('code')} message={output.get('message')}"
                )
            if time.time() - start_time > max_wait_seconds:
                raise TimeoutError("Timed out while waiting for video generation")
            time.sleep(poll_interval_seconds)

    @staticmethod
    def download_video(video_url: str, save_path: str | Path) -> Path:
        save_path = Path(save_path).resolve()
        save_path.parent.mkdir(parents=True, exist_ok=True)

        with requests.get(video_url, stream=True, timeout=300) as response:
            response.raise_for_status()
            with save_path.open("wb") as output_file:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        output_file.write(chunk)

        return save_path


def can_run_fission_generation() -> bool:
    return bool(os.getenv("DASHSCOPE_API_KEY"))


def build_variant_payload(
    *,
    variant_index: int,
    source: str,
    file_path: Path,
    data_root: Path,
    base_public_url: str,
) -> dict:
    resolved_path = file_path.resolve()
    return {
        "variant_index": variant_index,
        "source": source,
        "file_path": str(resolved_path),
        "public_url": build_media_url(base_public_url, data_root, resolved_path),
    }


def build_variant_output_path(generated_output_directory: Path, group_index: int, variant_index: int) -> Path:
    return generated_output_directory / f"group_{group_index:03d}_{variant_index:03d}.mp4"


def create_original_copy_variant(
    *,
    segment: dict,
    output_path: Path,
    data_root: Path,
    base_public_url: str,
) -> dict:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(segment["export_file_path"], output_path)
    return build_variant_payload(
        variant_index=0,
        source="copied_original",
        file_path=output_path,
        data_root=data_root,
        base_public_url=base_public_url,
    )


def generate_variant_video(
    *,
    segment: dict,
    generation_prompt: str,
    variant_index: int,
    output_path: Path,
    size: str,
    data_root: Path,
    base_public_url: str,
    append_log,
) -> dict:
    if not can_run_fission_generation():
        raise RuntimeError("Missing DASHSCOPE_API_KEY, unable to run fission generation")

    client = WanTextToVideoClient(api_key=os.getenv("DASHSCOPE_API_KEY"))
    duration = max(1, math.ceil(float(segment.get("duration_seconds") or 0)))
    group_prefix = f"group_{segment['group_index']:03d}"
    append_log("info", f"{group_prefix} start generating variant {variant_index:03d}")

    create_result = client.create_text_to_video_task(
        prompt=generation_prompt,
        size=size,
        duration=duration,
        shot_type="multi",
    )
    task_id = (create_result.get("output") or {}).get("task_id")
    if not task_id:
        raise RuntimeError(f"Task created without task_id: {create_result}")

    final_result = client.wait_until_finished(task_id=task_id)
    video_url = (final_result.get("output") or {}).get("video_url")
    if not video_url:
        raise RuntimeError(f"Generation succeeded without video_url: {final_result}")

    saved_file_path = client.download_video(video_url, output_path)
    append_log("success", f"{group_prefix} variant {variant_index:03d} downloaded")

    return build_variant_payload(
        variant_index=variant_index,
        source="wan_t2v",
        file_path=saved_file_path,
        data_root=data_root,
        base_public_url=base_public_url,
    )


def generate_segment_variants(
    *,
    segment: dict,
    generation_prompt: str,
    fission_count: int,
    size: str,
    generated_output_directory: Path,
    data_root: Path,
    base_public_url: str,
    append_log,
) -> list[dict]:
    generated_output_directory.mkdir(parents=True, exist_ok=True)
    group_index = segment["group_index"]

    for stale_file in generated_output_directory.glob(f"group_{group_index:03d}_*.mp4"):
        stale_file.unlink()

    if fission_count == 0:
        original_copy = create_original_copy_variant(
            segment=segment,
            output_path=build_variant_output_path(generated_output_directory, group_index, 0),
            data_root=data_root,
            base_public_url=base_public_url,
        )
        append_log("success", f"group_{group_index:03d} copied original segment")
        return [original_copy]

    generated_videos = []
    for variant_index in range(1, fission_count + 1):
        generated_videos.append(
            generate_variant_video(
                segment=segment,
                generation_prompt=generation_prompt,
                variant_index=variant_index,
                output_path=build_variant_output_path(generated_output_directory, group_index, variant_index),
                size=size,
                data_root=data_root,
                base_public_url=base_public_url,
                append_log=append_log,
            )
        )
    return generated_videos
