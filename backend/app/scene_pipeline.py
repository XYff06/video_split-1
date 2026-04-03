"""单视频处理流水线。

这里封装的是“一个视频从原始文件到可用片段结果”的完整过程：
1. 场景检测并切出原始小片段。
2. 搜索满足时长约束的连续分组方案。
3. 选择一套方案并把多个小片段合并成最终片段。
4. 可选地调用多模态模型为每个片段生成提示词分析。
"""

import random
import subprocess
from pathlib import Path

from scenedetect import ContentDetector, SceneManager, open_video
from scenedetect.video_splitter import split_video_ffmpeg

from .media_utils import build_media_url
from .models import VideoProcessResult
from .prompt_analysis import analyze_segment_prompt, can_run_prompt_analysis


MIN_GROUP_DURATION_SECONDS = 6.0
MAX_GROUP_DURATION_SECONDS = 14.0
MAX_GROUPING_SOLUTIONS = 2376


def detect_and_split_original_scenes(
    source_video_path: Path,
    scene_output_directory: Path,
    base_public_url: str,
    video_name: str,
    append_log,
) -> list[dict]:
    """执行场景检测，并把原视频切成最细粒度的原始片段。"""

    append_log("info", f"Starting scene detection for video: {video_name}")
    data_root = scene_output_directory.parents[3]

    # 这里使用 PySceneDetect 根据画面变化自动识别场景边界。
    video_stream = open_video(str(source_video_path))
    scene_manager = SceneManager()
    scene_manager.add_detector(ContentDetector())
    scene_manager.detect_scenes(video=video_stream)
    detected_scenes = scene_manager.get_scene_list(start_in_scene=True)

    if not detected_scenes:
        raise RuntimeError("No scenes were detected by PySceneDetect.")

    scene_output_directory.mkdir(parents=True, exist_ok=True)
    append_log("info", f"Detected {len(detected_scenes)} scenes. Starting built-in split operation.")

    # 识别出场景后，再交给 PySceneDetect 内置的 ffmpeg splitter 真正导出文件。
    split_video_ffmpeg(
        input_video_path=str(source_video_path),
        scene_list=detected_scenes,
        output_dir=scene_output_directory,
        show_progress=False,
    )

    exported_scene_files = sorted(scene_output_directory.glob("*.mp4"))
    if len(exported_scene_files) != len(detected_scenes):
        raise RuntimeError(
            f"Split result mismatch: detected={len(detected_scenes)}, exported={len(exported_scene_files)}"
        )

    original_scenes = []
    for index, ((start_timecode, end_timecode), scene_file_path) in enumerate(
        zip(detected_scenes, exported_scene_files),
        start=1,
    ):
        start_seconds = start_timecode.get_seconds()
        end_seconds = end_timecode.get_seconds()
        duration_seconds = end_seconds - start_seconds
        # 每个原始场景都保留时间范围、磁盘路径和可访问 URL，后续分组和预览都要用到。
        original_scenes.append(
            {
                "scene_index": index,
                "start_seconds": start_seconds,
                "end_seconds": end_seconds,
                "duration_seconds": duration_seconds,
                "file_path": str(scene_file_path),
                "public_url": build_media_url(base_public_url, data_root, scene_file_path),
            }
        )

    append_log("success", f"Scene split finished. Exported {len(original_scenes)} original scene files.")
    return original_scenes


def search_valid_continuous_groupings(original_scenes: list[dict], append_log):
    """搜索所有满足时长要求的连续分组方案。"""

    append_log("info", "DFS grouping search started.")
    durations = [scene["duration_seconds"] for scene in original_scenes]

    if any(duration > MAX_GROUP_DURATION_SECONDS for duration in durations):
        raise RuntimeError("At least one original scene is longer than 14 seconds, no valid grouping exists.")

    total_duration = sum(durations)
    min_groups = int(total_duration // MAX_GROUP_DURATION_SECONDS)
    max_groups = int(total_duration // MIN_GROUP_DURATION_SECONDS) + 1
    if min_groups > max_groups:
        raise RuntimeError("Total duration cannot be partitioned into contiguous groups of 6-14 seconds.")

    # `suffix_sum` 用来快速估算“从当前位置到结尾还剩多少总时长”，
    # 这样 DFS 可以更早剪枝，减少无意义搜索。
    n = len(durations)
    suffix_sum = [0.0] * (n + 1)
    for i in range(n - 1, -1, -1):
        suffix_sum[i] = suffix_sum[i + 1] + durations[i]

    solutions = []
    hit_limit = False

    def dfs(start_index: int, plan: list[list[int]]) -> None:
        # DFS 的含义是：从第 `start_index` 个原始场景开始，递归尝试后续所有合法分组。
        nonlocal hit_limit
        if hit_limit:
            return
        if start_index == n:
            solutions.append([group[:] for group in plan])
            if len(solutions) >= MAX_GROUPING_SOLUTIONS:
                hit_limit = True
            return

        remaining_duration = suffix_sum[start_index]
        if remaining_duration < MIN_GROUP_DURATION_SECONDS:
            return

        current_duration = 0.0
        current_group = []
        for end_index in range(start_index, n):
            current_duration += durations[end_index]
            current_group.append(end_index + 1)

            if current_duration > MAX_GROUP_DURATION_SECONDS:
                break

            if current_duration >= MIN_GROUP_DURATION_SECONDS:
                next_start = end_index + 1
                remaining = suffix_sum[next_start]
                if 0 < remaining < MIN_GROUP_DURATION_SECONDS:
                    continue
                plan.append(current_group[:])
                dfs(next_start, plan)
                plan.pop()
                if hit_limit:
                    return

    dfs(0, [])
    if not solutions:
        raise RuntimeError("Current scene list cannot be partitioned into contiguous groups between 6 and 14 seconds.")

    append_log("success", f"DFS grouping search completed with {len(solutions)} valid solutions.")
    if hit_limit:
        append_log("warning", f"Reached solution cap: {MAX_GROUPING_SOLUTIONS}. Search stopped early.")

    return solutions, hit_limit


def choose_final_grouping_plan(all_grouping_plans: list[list[list[int]]], append_log) -> list[list[int]]:
    """从所有合法分组方案中随机选出一套最终方案。"""

    shuffled_plans = all_grouping_plans[:]
    random.shuffle(shuffled_plans)
    chosen_plan = random.choice(shuffled_plans)
    append_log("info", f"Selected final grouping plan: {chosen_plan}")
    return chosen_plan


def merge_grouped_scene_files(
    chosen_grouping_plan: list[list[int]],
    original_scenes: list[dict],
    merged_output_directory: Path,
    base_public_url: str,
    append_log,
) -> list[dict]:
    """把选中的连续场景组合并成最终可用片段。"""

    merged_output_directory.mkdir(parents=True, exist_ok=True)
    merged_segments = []
    data_root = merged_output_directory.parents[3]

    for group_index, scene_indices in enumerate(chosen_grouping_plan, start=1):
        selected_scenes = [original_scenes[idx - 1] for idx in scene_indices]
        concat_file_path = merged_output_directory / f"group_{group_index:03d}_concat.txt"
        merged_file_path = merged_output_directory / f"group_{group_index:03d}.mp4"

        # 先写出 ffmpeg concat 清单文件，告诉 ffmpeg 应该按什么顺序拼接源片段。
        with concat_file_path.open("w", encoding="utf-8") as concat_file:
            for scene in selected_scenes:
                safe_path = scene["file_path"].replace("'", "'\\''")
                concat_file.write(f"file '{safe_path}'\n")

        # 使用 `-c copy` 做无重新编码拼接，速度更快，也尽量避免画质损失。
        ffmpeg_command = [
            "ffmpeg",
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(concat_file_path),
            "-c",
            "copy",
            str(merged_file_path),
        ]
        command_result = subprocess.run(
            ffmpeg_command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        if command_result.returncode != 0:
            stderr_text = command_result.stderr.decode("utf-8", errors="replace")
            raise RuntimeError(f"ffmpeg merge failed for group {group_index}: {stderr_text}")

        concat_file_path.unlink(missing_ok=True)

        start_seconds = selected_scenes[0]["start_seconds"]
        end_seconds = selected_scenes[-1]["end_seconds"]
        duration_seconds = end_seconds - start_seconds
        # 每个合并片段除了导出文件路径外，还会额外记录分析和生成所需的运行时字段。
        merged_segments.append(
            {
                "group_index": group_index,
                "start_seconds": start_seconds,
                "end_seconds": end_seconds,
                "duration_seconds": duration_seconds,
                "source_scene_index_range": [scene_indices[0], scene_indices[-1]],
                "source_scene_files": [scene["file_path"] for scene in selected_scenes],
                "export_file_path": str(merged_file_path),
                "export_public_url": build_media_url(base_public_url, data_root, merged_file_path),
                "analysis_status": "pending",
                "analysis": None,
                "analysis_error_message": None,
                "fission_count": 1,
                "generated_videos": [],
                "generation_status": "idle",
                "generation_error_message": None,
                "generation_prompt": "",
            }
        )

    append_log("success", f"Merged grouped scenes into {len(merged_segments)} final segments.")
    return merged_segments


def process_single_video(
    source_video_path: Path,
    task_root_directory: Path,
    base_public_url: str,
    video_name: str,
    task_log_sink: list[dict],
    on_segments_ready=None,
    on_segment_analysis=None,
) -> VideoProcessResult:
    """执行单个视频的完整处理流水线。"""

    video_logs = []

    def append_video_log(level: str, message: str):
        from .models import make_log

        entry = make_log(level, message, video_name)
        video_logs.append(entry)
        task_log_sink.append(entry)

    try:
        # 一个视频的所有中间产物都会放在当前任务目录下的独立子目录中。
        scene_directory = task_root_directory / "original_scenes" / source_video_path.stem
        merged_directory = task_root_directory / "merged_segments" / source_video_path.stem

        original_scenes = detect_and_split_original_scenes(
            source_video_path=source_video_path,
            scene_output_directory=scene_directory,
            base_public_url=base_public_url,
            video_name=video_name,
            append_log=append_video_log,
        )

        all_groupings, _ = search_valid_continuous_groupings(original_scenes, append_video_log)
        chosen_plan = choose_final_grouping_plan(all_groupings, append_video_log)
        merged_segments = merge_grouped_scene_files(
            chosen_grouping_plan=chosen_plan,
            original_scenes=original_scenes,
            merged_output_directory=merged_directory,
            base_public_url=base_public_url,
            append_log=append_video_log,
        )

        if callable(on_segments_ready):
            # 允许上层在“片段已经可预览”这个时间点提前通知前端。
            on_segments_ready(merged_segments)

        analysis_status = "completed"
        if not can_run_prompt_analysis():
            # 没配好多模态分析能力时，不让整个视频处理失败，而是标记为跳过。
            analysis_status = "skipped"
            append_video_log("warning", "未配置 DashScope 视频理解能力，已跳过片段提示词生成。")
            for segment in merged_segments:
                segment["analysis_status"] = "skipped"
                segment["analysis_error_message"] = "DashScope 未配置，已跳过生成。"
                if callable(on_segment_analysis):
                    on_segment_analysis(segment["group_index"] - 1, segment)
        else:
            for segment_index, segment in enumerate(merged_segments):
                # 每个片段分别分析，这样即使某一个失败，也不会拖垮整支视频。
                try:
                    segment["analysis"] = analyze_segment_prompt(segment, append_video_log)
                    segment["analysis_status"] = "completed"
                except Exception as error:
                    analysis_status = "partial_failed"
                    segment["analysis_status"] = "failed"
                    segment["analysis_error_message"] = str(error)
                    append_video_log("error", f"片段 group_{segment['group_index']:03d} 提示词生成失败: {error}")
                if callable(on_segment_analysis):
                    on_segment_analysis(segment_index, segment)

        # 汇总信息主要给前端做统计展示，例如原始场景数、合并片段数、总时长等。
        summary = {
            "original_scene_count": len(original_scenes),
            "merged_segment_count": len(merged_segments),
            "total_original_duration_seconds": sum(scene["duration_seconds"] for scene in original_scenes),
            "total_merged_duration_seconds": sum(segment["duration_seconds"] for segment in merged_segments),
        }
        append_video_log("success", "Video processing completed successfully.")

        return VideoProcessResult(
            video_name=video_name,
            status="success",
            original_scenes=original_scenes,
            merged_segments=merged_segments,
            chosen_grouping_plan=chosen_plan,
            summary=summary,
            logs=video_logs,
            analysis_status=analysis_status,
        )
    except Exception as error:
        append_video_log("error", f"Video processing failed: {error}")
        return VideoProcessResult(
            video_name=video_name,
            status="failed",
            error_message=str(error),
            logs=video_logs,
            summary={"original_scene_count": 0, "merged_segment_count": 0},
        )
