import os
import shutil
import time
from pathlib import Path

import requests
from dotenv import load_dotenv

from .media_utils import build_media_url


load_dotenv()

WAN_BASE_URL = os.getenv("DASHSCOPE_BASE_HTTP_API_URL", "https://dashscope.aliyuncs.com/api/v1")
WAN_MODEL = os.getenv("WAN_MODEL")
WAN_SIZE = os.getenv("WAN_SIZE", "1280*720")
WAN_DURATION = int(os.getenv("WAN_DURATION", "5"))
WAN_REQUEST_TIMEOUT = int(os.getenv("WAN_REQUEST_TIMEOUT", "120"))
WAN_POLL_INTERVAL_SECONDS = int(os.getenv("WAN_POLL_INTERVAL_SECONDS", "15"))
WAN_MAX_WAIT_SECONDS = int(os.getenv("WAN_MAX_WAIT_SECONDS", "1800"))


class WanTextToVideoClient:
    def __init__(self, api_key: str, base_url: str = WAN_BASE_URL, request_timeout: int = WAN_REQUEST_TIMEOUT):
        if not api_key:
            raise ValueError("缺少 DASHSCOPE_API_KEY")
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
        prompt: str,
        model: str = WAN_MODEL,
        size: str = WAN_SIZE,
        duration: int = WAN_DURATION,
        seed: int | None = None,
    ) -> dict:
        if not prompt or not prompt.strip():
            raise ValueError("prompt 不能为空")

        request_body = {
            "model": model,
            "input": {"prompt": prompt.strip()},
            "parameters": {
                "size": size,
                "duration": duration,
            },
        }
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
                f"创建任务失败 code={response_data.get('code')} message={response_data.get('message')}"
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
                f"查询任务失败 code={response_data.get('code')} message={response_data.get('message')}"
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
                    f"任务失败 task_status={task_status} code={output.get('code')} message={output.get('message')}"
                )
            if time.time() - start_time > max_wait_seconds:
                raise TimeoutError("等待任务完成超时")
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


def generate_segment_variants(
    *,
    segment: dict,
    generation_prompt: str,
    fission_count: int,
    generated_output_directory: Path,
    data_root: Path,
    base_public_url: str,
    append_log,
) -> list[dict]:
    generated_output_directory.mkdir(parents=True, exist_ok=True)
    group_prefix = f"group_{segment['group_index']:03d}"
    generated_videos = []

    if fission_count == 0:
        target_path = generated_output_directory / f"{group_prefix}_000.mp4"
        shutil.copy2(segment["export_file_path"], target_path)
        generated_videos.append(
            {
                "variant_index": 0,
                "source": "copied_original",
                "file_path": str(target_path),
                "public_url": build_media_url(base_public_url, data_root, target_path),
            }
        )
        append_log("success", f"{group_prefix} 裂变数量为 0，已复制原片段。")
        return generated_videos

    if not can_run_fission_generation():
        raise RuntimeError("缺少 DASHSCOPE_API_KEY，无法执行裂变生成。")

    client = WanTextToVideoClient(api_key=os.getenv("DASHSCOPE_API_KEY"))
    for variant_index in range(1, fission_count + 1):
        output_path = generated_output_directory / f"{group_prefix}_{variant_index:03d}.mp4"
        append_log("info", f"{group_prefix} 开始裂变生成第 {variant_index} 个视频。")
        create_result = client.create_text_to_video_task(prompt=generation_prompt)
        task_id = (create_result.get("output") or {}).get("task_id")
        if not task_id:
            raise RuntimeError(f"创建任务成功但没有拿到 task_id: {create_result}")

        final_result = client.wait_until_finished(task_id=task_id)
        video_url = (final_result.get("output") or {}).get("video_url")
        if not video_url:
            raise RuntimeError(f"裂变任务成功但没有拿到 video_url: {final_result}")

        saved_file_path = client.download_video(video_url, output_path)
        generated_videos.append(
            {
                "variant_index": variant_index,
                "source": "wan_t2v",
                "file_path": str(saved_file_path),
                "public_url": build_media_url(base_public_url, data_root, saved_file_path),
            }
        )
        append_log("success", f"{group_prefix} 第 {variant_index} 个裂变视频已下载完成。")

    return generated_videos
