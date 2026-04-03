"""任务运行时编排模块。

这个模块是后端真正的调度中心，负责把“创建任务”转换成一系列后台动作：
1. 启动后台线程处理视频。
2. 更新任务对象中的进度、日志和中间状态。
3. 持续向 SSE 队列推送前端需要的实时事件。
4. 串联切分、分析、裂变生成、重组等多个步骤。
"""

import json
import threading
from copy import deepcopy
from dataclasses import asdict
from pathlib import Path
from typing import Any

from .config import BASE_PUBLIC_URL, DATA_ROOT
from .fission_service import (
    WAN_SIZE,
    build_variant_output_path,
    create_original_copy_variant,
    generate_segment_variants,
    generate_variant_video,
)
from .media_utils import build_media_url, save_uploaded_files
from .models import TaskState, TaskStore, make_log
from .regrouping import export_regrouped_videos
from .scene_pipeline import process_single_video


def clear_regrouped_videos(task: TaskState, video_index: int) -> None:
    video_result = task.video_results[video_index]
    video_result["regrouped_videos"] = []


def enqueue_event(task: TaskState, event_name: str, payload: dict[str, Any]) -> None:
    """把一个事件写入任务队列，供 SSE 接口实时消费。"""

    task.event_queue.put({"event": event_name, "data": payload})


def build_stream_snapshot(task: TaskState) -> dict[str, Any]:
    """构造任务完整快照，用于前端初始化页面状态。"""

    return {
        "taskId": task.task_id,
        "taskStatus": task.status,
        "completedVideos": task.completed_videos,
        "totalVideos": task.total_videos,
        "videoResults": task.video_results,
        "taskLogs": task.task_logs,
    }


def stream_task_events(task: TaskState):
    """不断从事件队列中读取事件并按 SSE 格式输出。"""

    yield f"event: task_snapshot\ndata: {json.dumps(build_stream_snapshot(task))}\n\n"
    while True:
        event = task.event_queue.get()
        yield f"event: {event['event']}\ndata: {json.dumps(event['data'])}\n\n"


def create_task_with_uploads(store: TaskStore, upload_files, upload_directory: Path):
    """创建任务并保存上传文件，返回任务对象和落盘路径列表。"""

    task = store.create_task(total_videos=len(upload_files))
    task.task_logs.append(make_log("info", f"Task {task.task_id} created."))
    saved_video_paths = save_uploaded_files(upload_files, upload_directory)
    return task, saved_video_paths


def start_processing_task(store: TaskStore, task_id: str, saved_video_paths, task_directory: Path) -> None:
    """启动后台线程处理整批视频。"""

    thread = threading.Thread(
        target=process_task_videos,
        args=(store, task_id, saved_video_paths, task_directory),
        daemon=True,
    )
    thread.start()


def process_task_videos(store: TaskStore, task_id: str, saved_video_paths, task_directory: Path) -> None:
    """按顺序处理一个任务中的所有视频。

    这是整个任务生命周期里最关键的编排函数：
    1. 给每个视频先注册一份“处理中”的占位结果。
    2. 调用 `process_single_video` 执行切分、分组、分析。
    3. 把中间状态和最终结果写回任务对象。
    4. 每到关键节点都推送事件给前端。
    """

    task = store.get_task(task_id)
    if not task:
        return

    # 任务输出目录会存放原场景片段、合并片段、生成视频等全部产物。
    task_directory.mkdir(parents=True, exist_ok=True)
    task.task_logs.append(make_log("info", f"Task {task_id} processing started."))

    for video_path in saved_video_paths:
        video_name = video_path.name
        # 先写入一个占位结果，前端就能立刻看到“这个视频已经开始处理”。
        task.task_logs.append(make_log("info", f"Start processing video: {video_name}", video_name=video_name))
        task.video_results.append(
            {
                "video_name": video_name,
                "status": "processing",
                "error_message": None,
                "original_scenes": [],
                "merged_segments": [],
                "chosen_grouping_plan": [],
                "summary": {},
                "logs": [],
                "analysis_status": "processing",
                "fission_size": None,
                "use_global_fission_size": True,
                "regrouped_videos": [],
            }
        )
        video_result_index = len(task.video_results) - 1

        enqueue_event(
            task,
            "video_processing_started",
            {
                "taskId": task.task_id,
                "videoIndex": video_result_index,
                "videoName": video_name,
                "taskStatus": task.status,
                "videoResult": deepcopy(task.video_results[video_result_index]),
                "taskLogs": task.task_logs,
            },
        )

        def handle_segments_ready(merged_segments):
            # 合并片段一旦准备好，就立刻同步给前端，减少等待感。
            task.video_results[video_result_index]["merged_segments"] = deepcopy(merged_segments)
            enqueue_event(
                task,
                "segments_ready",
                {
                    "taskId": task.task_id,
                    "videoIndex": video_result_index,
                    "videoName": video_name,
                    "mergedSegments": deepcopy(merged_segments),
                    "taskStatus": task.status,
                    "taskLogs": task.task_logs,
                },
            )

        def handle_segment_analysis(segment_index, segment_payload):
            # 某个片段分析完成后，只更新对应下标，避免整视频结果频繁全量回传。
            task.video_results[video_result_index]["merged_segments"][segment_index] = deepcopy(segment_payload)
            enqueue_event(
                task,
                "segment_analysis",
                {
                    "taskId": task.task_id,
                    "videoIndex": video_result_index,
                    "videoName": video_name,
                    "segmentIndex": segment_index,
                    "segment": deepcopy(segment_payload),
                    "taskStatus": task.status,
                    "taskLogs": task.task_logs,
                },
            )

        # 真正的单视频处理链路在 `scene_pipeline.py` 中完成。
        result = process_single_video(
            source_video_path=video_path,
            task_root_directory=task_directory,
            base_public_url=BASE_PUBLIC_URL,
            video_name=video_name,
            task_log_sink=task.task_logs,
            on_segments_ready=handle_segments_ready,
            on_segment_analysis=handle_segment_analysis,
        )

        # dataclass 先转成 dict，再补回运行时字段，例如裂变尺寸和重组结果。
        result_payload = asdict(result)
        result_payload["fission_size"] = task.video_results[video_result_index].get("fission_size")
        result_payload["use_global_fission_size"] = task.video_results[video_result_index].get("use_global_fission_size", True)
        result_payload["regrouped_videos"] = task.video_results[video_result_index].get("regrouped_videos", [])
        task.video_results[video_result_index] = result_payload
        task.completed_videos += 1
        task.status = "completed" if task.completed_videos == task.total_videos else "processing"

        enqueue_event(
            task,
            "video_result",
            {
                "taskId": task.task_id,
                "videoName": result.video_name,
                "videoStatus": result.status,
                "videoResult": result_payload,
                "videoLogs": result.logs,
                "completedVideos": task.completed_videos,
                "totalVideos": task.total_videos,
                "taskStatus": task.status,
                "taskLogs": task.task_logs,
            },
        )

    # 所有视频都处理完成后，再发送一次任务级完成事件。
    task.task_logs.append(make_log("success", f"Task {task_id} completed."))
    enqueue_event(
        task,
        "task_completed",
        {
            "taskId": task.task_id,
            "taskStatus": task.status,
            "completedVideos": task.completed_videos,
            "totalVideos": task.total_videos,
            "videoResults": task.video_results,
            "taskLogs": task.task_logs,
        },
    )


def update_segment_generation_state(
    task: TaskState,
    *,
    video_index: int,
    segment_index: int,
    generation_status: str | None = None,
    generation_error_message: str | None = None,
    generated_videos: list[dict] | None = None,
    fission_count: int | None = None,
    generation_prompt: str | None = None,
) -> dict:
    """更新某个片段的裂变生成状态，并返回深拷贝结果。"""

    segment = task.video_results[video_index]["merged_segments"][segment_index]
    if generation_status is not None:
        segment["generation_status"] = generation_status
    if generation_error_message is not None:
        segment["generation_error_message"] = generation_error_message
    if generated_videos is not None:
        segment["generated_videos"] = generated_videos
    if fission_count is not None:
        segment["fission_count"] = fission_count
    if generation_prompt is not None:
        segment["generation_prompt"] = generation_prompt
    return deepcopy(segment)


def emit_segment_generation_event(task: TaskState, video_index: int, segment_index: int) -> None:
    """推送单个片段裂变生成状态更新事件。"""

    enqueue_event(
        task,
        "segment_generation_update",
        {
            "taskId": task.task_id,
            "videoIndex": video_index,
            "segmentIndex": segment_index,
            "segment": deepcopy(task.video_results[video_index]["merged_segments"][segment_index]),
            "taskStatus": task.status,
            "taskLogs": task.task_logs,
        },
    )


def emit_regrouped_videos_event(task: TaskState, video_index: int) -> None:
    """推送某个视频的整片重组结果更新事件。"""

    enqueue_event(
        task,
        "video_regrouped",
        {
            "taskId": task.task_id,
            "videoIndex": video_index,
            "videoResult": deepcopy(task.video_results[video_index]),
            "taskStatus": task.status,
            "taskLogs": task.task_logs,
        },
    )


def rebuild_regrouped_videos(task: TaskState, video_index: int) -> list[dict]:
    """根据当前片段变体，重新导出整片重组视频。"""

    video_result = task.video_results[video_index]
    merged_segments = video_result.get("merged_segments") or []
    if not merged_segments:
        video_result["regrouped_videos"] = []
        return []

    task_root = Path(merged_segments[0]["export_file_path"]).parents[2]
    regrouped_output_directory = task_root / "regrouped_videos" / Path(video_result["video_name"]).stem
    regrouped_videos = export_regrouped_videos(
        segments=merged_segments,
        regrouped_output_directory=regrouped_output_directory,
        data_root=DATA_ROOT,
        base_public_url=BASE_PUBLIC_URL,
    )
    video_result["regrouped_videos"] = regrouped_videos
    return regrouped_videos


def start_fission_generation(store: TaskStore, task_id: str, video_specs: list[dict]) -> None:
    """启动后台线程执行裂变生成。"""

    thread = threading.Thread(
        target=run_fission_generation,
        args=(store, task_id, video_specs),
        daemon=True,
    )
    thread.start()


def run_fission_generation(store: TaskStore, task_id: str, video_specs: list[dict]) -> None:
    """按视频和片段规格批量执行裂变生成。"""

    task = store.get_task(task_id)
    if not task:
        return

    task.task_logs.append(make_log("info", "Fission generation started."))
    enqueue_event(
        task,
        "fission_batch_started",
        {"taskId": task.task_id, "taskStatus": task.status, "taskLogs": task.task_logs},
    )

    for video_spec in video_specs:
        video_index = video_spec["videoIndex"]
        video_result = task.video_results[video_index]
        if not video_result.get("merged_segments"):
            continue
        video_size = video_spec.get("videoSize") or video_result.get("fission_size") or WAN_SIZE
        video_result["fission_size"] = video_spec.get("videoSize") or video_result.get("fission_size")
        video_result["use_global_fission_size"] = not bool(video_result["fission_size"])
        clear_regrouped_videos(task, video_index)
        video_stem = Path(video_result["video_name"]).stem
        task_root = Path(video_result["merged_segments"][0]["export_file_path"]).parents[2]
        generated_output_directory = task_root / "generated_segments" / video_stem

        for segment_spec in video_spec["segments"]:
            segment_index = segment_spec["segmentIndex"]
            fission_count = int(segment_spec["fissionCount"])
            generation_prompt = segment_spec["generationPrompt"].strip()

            # 生成前先把状态改成 processing，让前端能立刻感知“已开始生成”。
            update_segment_generation_state(
                task,
                video_index=video_index,
                segment_index=segment_index,
                generation_status="processing",
                generation_error_message=None,
                generated_videos=[],
                fission_count=fission_count,
                generation_prompt=generation_prompt,
            )
            emit_segment_generation_event(task, video_index, segment_index)

            segment = task.video_results[video_index]["merged_segments"][segment_index]

            def append_log(level: str, message: str):
                # 裂变生成过程中的日志同时挂到任务级和视频级，方便两处展示。
                entry = make_log(level, message, video_result["video_name"])
                task.task_logs.append(entry)
                task.video_results[video_index].setdefault("logs", []).append(entry)

            try:
                generated_videos = generate_segment_variants(
                    segment=segment,
                    generation_prompt=generation_prompt,
                    fission_count=fission_count,
                    size=video_size,
                    generated_output_directory=generated_output_directory,
                    data_root=DATA_ROOT,
                    base_public_url=BASE_PUBLIC_URL,
                    append_log=append_log,
                )
                update_segment_generation_state(
                    task,
                    video_index=video_index,
                    segment_index=segment_index,
                    generation_status="completed",
                    generation_error_message=None,
                    generated_videos=generated_videos,
                    fission_count=fission_count,
                    generation_prompt=generation_prompt,
                )
            except Exception as error:
                append_log("error", f"片段 group_{segment['group_index']:03d} 裂变失败: {error}")
                update_segment_generation_state(
                    task,
                    video_index=video_index,
                    segment_index=segment_index,
                    generation_status="failed",
                    generation_error_message=str(error),
                    generated_videos=[],
                    fission_count=fission_count,
                    generation_prompt=generation_prompt,
                )

            emit_segment_generation_event(task, video_index, segment_index)

    task.task_logs.append(make_log("success", "Fission generation finished."))
    enqueue_event(
        task,
        "fission_batch_completed",
        {"taskId": task.task_id, "taskStatus": task.status, "taskLogs": task.task_logs},
    )


def update_video_generation_size(store: TaskStore, task_id: str, video_index: int, size: str | None) -> dict | None:
    """更新某个视频默认裂变尺寸。"""

    task = store.get_task(task_id)
    if not task:
        return None
    video_result = task.video_results[video_index]
    video_result["fission_size"] = size
    video_result["use_global_fission_size"] = not bool(size)
    return deepcopy(video_result)


def add_segment_variant(store: TaskStore, task_id: str, video_index: int, segment_index: int) -> dict | None:
    """给片段新增一个变体，并在完成后重建整片重组结果。"""

    task = store.get_task(task_id)
    if not task:
        return None

    video_result = task.video_results[video_index]
    segment = video_result["merged_segments"][segment_index]
    video_stem = Path(video_result["video_name"]).stem
    task_root = Path(segment["export_file_path"]).parents[2]
    generated_output_directory = task_root / "generated_segments" / video_stem
    video_size = video_result.get("fission_size") or WAN_SIZE
    generated_videos = list(segment.get("generated_videos") or [])

    def append_log(level: str, message: str):
        entry = make_log(level, message, video_result["video_name"])
        task.task_logs.append(entry)
        video_result.setdefault("logs", []).append(entry)

    # 如果当前只剩“原片复制版”占位变体，新增真实变体前先把它删掉。
    if len(generated_videos) == 1 and generated_videos[0]["variant_index"] == 0:
        stale_path = Path(generated_videos[0]["file_path"])
        stale_path.unlink(missing_ok=True)
        generated_videos = []

    next_variant_index = max([variant["variant_index"] for variant in generated_videos], default=0) + 1
    new_variant = generate_variant_video(
        segment=segment,
        generation_prompt=segment.get("generation_prompt") or "",
        variant_index=next_variant_index,
        output_path=build_variant_output_path(generated_output_directory, segment["group_index"], next_variant_index),
        size=video_size,
        data_root=DATA_ROOT,
        base_public_url=BASE_PUBLIC_URL,
        append_log=append_log,
    )
    generated_videos.append(new_variant)

    segment["generated_videos"] = generated_videos
    segment["generation_status"] = "completed"
    segment["fission_count"] = len(generated_videos)
    clear_regrouped_videos(task, video_index)
    return deepcopy(segment)


def delete_segment_variant(store: TaskStore, task_id: str, video_index: int, segment_index: int, variant_index: int) -> dict | None:
    """删除指定变体，并把剩余变体重新整理编号。"""

    task = store.get_task(task_id)
    if not task:
        return None

    video_result = task.video_results[video_index]
    segment = video_result["merged_segments"][segment_index]
    video_stem = Path(video_result["video_name"]).stem
    task_root = Path(segment["export_file_path"]).parents[2]
    generated_output_directory = task_root / "generated_segments" / video_stem

    generated_videos = sorted(segment.get("generated_videos") or [], key=lambda item: item["variant_index"])
    target = next((item for item in generated_videos if item["variant_index"] == variant_index), None)
    if not target:
        raise RuntimeError("Variant not found")

    Path(target["file_path"]).unlink(missing_ok=True)
    remaining = [item for item in generated_videos if item["variant_index"] != variant_index]

    if not remaining:
        segment["generated_videos"] = []
        segment["fission_count"] = 0
        segment["generation_status"] = "idle"
    else:
        normalized_videos = []
        for next_index, item in enumerate(remaining, start=1):
            # 删除中间项后，后续变体需要重新编号，避免出现跳号。
            current_path = Path(item["file_path"])
            target_path = build_variant_output_path(generated_output_directory, segment["group_index"], next_index)
            if current_path.resolve() != target_path.resolve():
                target_path.unlink(missing_ok=True)
                current_path.replace(target_path)
            normalized_videos.append(
                {
                    **item,
                    "variant_index": next_index,
                    "file_path": str(target_path.resolve()),
                    "public_url": build_media_url(BASE_PUBLIC_URL, DATA_ROOT, target_path.resolve()),
                }
            )
        segment["generated_videos"] = normalized_videos
        segment["fission_count"] = len(normalized_videos)

    clear_regrouped_videos(task, video_index)
    return deepcopy(segment)


def redo_segment_variant(store: TaskStore, task_id: str, video_index: int, segment_index: int, variant_index: int) -> dict | None:
    """重新生成某个指定变体。"""

    task = store.get_task(task_id)
    if not task:
        return None

    video_result = task.video_results[video_index]
    segment = video_result["merged_segments"][segment_index]
    generated_videos = sorted(segment.get("generated_videos") or [], key=lambda item: item["variant_index"])
    target = next((item for item in generated_videos if item["variant_index"] == variant_index), None)
    if not target:
        raise RuntimeError("Variant not found")

    Path(target["file_path"]).unlink(missing_ok=True)

    def append_log(level: str, message: str):
        entry = make_log(level, message, video_result["video_name"])
        task.task_logs.append(entry)
        video_result.setdefault("logs", []).append(entry)

    video_size = video_result.get("fission_size") or WAN_SIZE
    output_path = Path(target["file_path"])
    if variant_index == 0:
        # 0 号变体代表原片复制版，所以“重做”本质上就是重新复制原片段。
        rebuilt_variant = create_original_copy_variant(
            segment=segment,
            output_path=output_path,
            data_root=DATA_ROOT,
            base_public_url=BASE_PUBLIC_URL,
        )
    else:
        rebuilt_variant = generate_variant_video(
            segment=segment,
            generation_prompt=segment.get("generation_prompt") or "",
            variant_index=variant_index,
            output_path=output_path,
            size=video_size,
            data_root=DATA_ROOT,
            base_public_url=BASE_PUBLIC_URL,
            append_log=append_log,
        )

    segment["generated_videos"] = [rebuilt_variant if item["variant_index"] == variant_index else item for item in generated_videos]
    clear_regrouped_videos(task, video_index)
    return deepcopy(segment)


def regenerate_video_regroup(store: TaskStore, task_id: str, video_index: int) -> dict | None:
    """手动触发某个视频的整片重组。"""

    task = store.get_task(task_id)
    if not task:
        return None
    rebuild_regrouped_videos(task, video_index)
    return deepcopy(task.video_results[video_index])
