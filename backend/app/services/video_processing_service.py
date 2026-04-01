import json
import random
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from scenedetect import SceneManager, open_video, split_video_ffmpeg
from scenedetect.detectors import ContentDetector

from app.utils.file_utils import ensure_directory_exists, generate_safe_task_directory


@dataclass
class GroupingConstraints:
    """分组时长约束，便于统一传递，避免硬编码散落。"""

    minimum_duration_seconds: float = 6.0
    maximum_duration_seconds: float = 14.0


class VideoProcessingService:
    """封装“场景检测切分 -> 连续分组 -> 合并输出”的主流程服务。"""

    def __init__(self, upload_directory: Path, processed_directory: Path, media_url_prefix: str) -> None:
        self.upload_directory = upload_directory
        self.processed_directory = processed_directory
        self.media_url_prefix = media_url_prefix
        ensure_directory_exists(self.upload_directory)
        ensure_directory_exists(self.processed_directory)

    def process_uploaded_video(self, uploaded_file_storage: Any) -> dict[str, Any]:
        """
        处理单个上传视频。

        做了什么：保存上传文件，执行两阶段处理并返回结构化结果。
        为什么这样做：将每个视频完全隔离，保证多视频任务互不影响。
        结果：成功返回片段信息；失败返回错误详情和日志。
        """
        video_name = uploaded_file_storage.filename or "unnamed_video.mp4"
        log_entries: list[dict[str, str]] = []

        try:
            task_directory = generate_safe_task_directory(self.processed_directory, video_name)
            uploaded_video_path = task_directory / video_name
            uploaded_file_storage.save(uploaded_video_path)
            log_entries.append(self._build_log("info", f"开始处理视频: {video_name}"))

            original_scene_segments = self.detect_and_split_original_scenes(
                video_file_path=uploaded_video_path,
                output_directory=task_directory,
            )
            log_entries.append(
                self._build_log("success", f"场景检测完成，共切分出 {len(original_scene_segments)} 个原始片段")
            )

            grouping_constraints = GroupingConstraints()
            grouped_scene_segments, grouping_logs = self.create_random_valid_continuous_groups(
                ordered_scene_segments=original_scene_segments,
                constraints=grouping_constraints,
            )
            log_entries.extend(grouping_logs)

            merged_segments = self.merge_grouped_scene_files(
                grouped_scene_segments=grouped_scene_segments,
                output_directory=task_directory,
            )
            log_entries.append(self._build_log("success", f"合并完成，输出 {len(merged_segments)} 个片段"))

            return {
                "video_name": video_name,
                "status": "success",
                "message": "视频处理成功",
                "original_scene_count": len(original_scene_segments),
                "merged_segment_count": len(merged_segments),
                "merged_segments": merged_segments,
                "logs": log_entries,
            }
        except Exception as processing_error:  # noqa: BLE001
            log_entries.append(self._build_log("error", f"处理失败: {processing_error}"))
            return {
                "video_name": video_name,
                "status": "failed",
                "message": str(processing_error),
                "merged_segments": [],
                "logs": log_entries,
            }

    def detect_and_split_original_scenes(self, video_file_path: Path, output_directory: Path) -> list[dict[str, Any]]:
        """
        第一步：场景检测 + PySceneDetect 内置分割。

        做了什么：
        1) 使用默认 ContentDetector 检测 scene list。
        2) 使用 split_video_ffmpeg 根据 scene list 导出真实片段文件。

        为什么这样做：严格满足“检测后必须真实切分”的要求，且不手写时间裁切逻辑。
        最终结果：返回按原顺序排列、带精确时间信息与文件 URL 的原始片段列表。
        """
        scene_output_directory = output_directory / "original_scenes"
        ensure_directory_exists(scene_output_directory)

        opened_video = open_video(str(video_file_path))
        scene_manager = SceneManager()
        scene_manager.add_detector(ContentDetector())
        scene_manager.detect_scenes(opened_video)
        detected_scene_list = scene_manager.get_scene_list()

        if not detected_scene_list:
            # 没检测到场景时，使用整段作为单片段，保证流程可继续。
            total_duration = opened_video.duration
            detected_scene_list = [(opened_video.base_timecode, total_duration)]

        split_video_ffmpeg(
            input_video_path=str(video_file_path),
            scene_list=detected_scene_list,
            output_dir=str(scene_output_directory),
            output_file_template="$VIDEO_NAME-Scene-$SCENE_NUMBER.mp4",
            show_progress=False,
            suppress_output=True,
        )

        generated_scene_files = sorted(scene_output_directory.glob("*.mp4"))

        original_scene_segments: list[dict[str, Any]] = []
        for scene_index, (start_timecode, end_timecode) in enumerate(detected_scene_list, start=1):
            segment_duration_seconds = (end_timecode - start_timecode).get_seconds()
            scene_file_path = generated_scene_files[scene_index - 1] if scene_index - 1 < len(generated_scene_files) else None

            original_scene_segments.append(
                {
                    "scene_index": scene_index,
                    "start_seconds": start_timecode.get_seconds(),
                    "end_seconds": end_timecode.get_seconds(),
                    "duration_seconds": segment_duration_seconds,
                    "file_path": str(scene_file_path) if scene_file_path else "",
                    "file_url": self._build_media_url(scene_file_path) if scene_file_path else "",
                }
            )

        return original_scene_segments

    def create_random_valid_continuous_groups(
        self,
        ordered_scene_segments: list[dict[str, Any]],
        constraints: GroupingConstraints,
    ) -> tuple[list[list[dict[str, Any]]], list[dict[str, str]]]:
        """
        第二步：随机合法分组（失败后回溯搜索）。

        做了什么：先随机最多100次切分；失败后 DFS/回溯+剪枝收集合法方案并随机选择。
        为什么这样做：优先保留随机性，同时提供确定性兜底，避免死循环和无解误判。
        结果：返回符合 6-14 秒约束的连续分组，或抛出明确无解错误。
        """
        log_entries: list[dict[str, str]] = []
        min_duration = constraints.minimum_duration_seconds
        max_duration = constraints.maximum_duration_seconds

        if any(segment["duration_seconds"] > max_duration for segment in ordered_scene_segments):
            log_entries.append(self._build_log("error", "无解预检查失败：存在单个片段时长超过 14 秒"))
            raise ValueError("当前片段列表无法分组成每组6到14秒的连续片段")

        for attempt_index in range(1, 101):
            candidate_groups = self._generate_random_continuous_grouping(ordered_scene_segments)
            if self._is_grouping_valid(candidate_groups, min_duration, max_duration):
                log_entries.append(self._build_log("success", f"随机分组在第 {attempt_index} 次尝试成功"))
                return candidate_groups, log_entries

        log_entries.append(self._build_log("warning", "随机尝试100次失败，开始DFS回溯搜索"))

        all_valid_groupings: list[list[list[dict[str, Any]]]] = []
        max_solution_collection_count = 1000

        def dfs_collect_solutions(start_index: int, current_grouping: list[list[dict[str, Any]]]) -> None:
            if len(all_valid_groupings) >= max_solution_collection_count:
                return
            if start_index == len(ordered_scene_segments):
                all_valid_groupings.append([group[:] for group in current_grouping])
                return

            accumulated_duration = 0.0
            candidate_group: list[dict[str, Any]] = []
            for next_index in range(start_index, len(ordered_scene_segments)):
                next_segment = ordered_scene_segments[next_index]
                accumulated_duration += next_segment["duration_seconds"]
                candidate_group.append(next_segment)

                if accumulated_duration > max_duration:
                    break
                if accumulated_duration >= min_duration:
                    current_grouping.append(candidate_group[:])
                    dfs_collect_solutions(next_index + 1, current_grouping)
                    current_grouping.pop()

        dfs_collect_solutions(0, [])

        if not all_valid_groupings:
            log_entries.append(self._build_log("error", "DFS搜索结束仍无解"))
            raise ValueError("当前片段列表无法分组成每组6到14秒的连续片段")

        random.shuffle(all_valid_groupings)
        selected_grouping = random.choice(all_valid_groupings)
        log_entries.append(
            self._build_log("success", f"DFS找到 {len(all_valid_groupings)} 个合法方案，已随机选择一个"),
        )
        return selected_grouping, log_entries

    def merge_grouped_scene_files(
        self,
        grouped_scene_segments: list[list[dict[str, Any]]],
        output_directory: Path,
    ) -> list[dict[str, Any]]:
        """
        第三步：按分组结果合并真实原始场景文件。

        做了什么：对每个组生成 concat 列表并调用 ffmpeg 合并。
        为什么这样做：前一步已得到合法连续分组，这一步将逻辑分组变成可播放文件。
        结果：输出完整的合并片段元数据，供前端预览与展示。
        """
        merged_output_directory = output_directory / "merged_segments"
        ensure_directory_exists(merged_output_directory)

        merged_results: list[dict[str, Any]] = []

        for group_index, one_group_segments in enumerate(grouped_scene_segments, start=1):
            merge_list_file = merged_output_directory / f"group_{group_index:03d}_concat.txt"
            merged_output_path = merged_output_directory / f"merged_group_{group_index:03d}.mp4"

            with merge_list_file.open("w", encoding="utf-8") as concat_file:
                for segment in one_group_segments:
                    concat_file.write(f"file '{segment['file_path']}'\n")

            command = [
                "ffmpeg",
                "-y",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                str(merge_list_file),
                "-c",
                "copy",
                str(merged_output_path),
            ]
            subprocess.run(command, check=True, capture_output=True)

            start_seconds = one_group_segments[0]["start_seconds"]
            end_seconds = one_group_segments[-1]["end_seconds"]
            total_duration_seconds = sum(segment["duration_seconds"] for segment in one_group_segments)

            merged_results.append(
                {
                    "group_index": group_index,
                    "start_seconds": start_seconds,
                    "end_seconds": end_seconds,
                    "duration_seconds": total_duration_seconds,
                    "original_scene_index_range": {
                        "start": one_group_segments[0]["scene_index"],
                        "end": one_group_segments[-1]["scene_index"],
                    },
                    "original_scene_file_urls": [segment["file_url"] for segment in one_group_segments],
                    "export_file_path": str(merged_output_path),
                    "export_file_url": self._build_media_url(merged_output_path),
                }
            )

            merge_list_file.unlink(missing_ok=True)

        return merged_results

    def _generate_random_continuous_grouping(
        self,
        ordered_scene_segments: list[dict[str, Any]],
    ) -> list[list[dict[str, Any]]]:
        """随机切连续边界，把一维有序列表转换为二维连续分组。"""
        if len(ordered_scene_segments) <= 1:
            return [ordered_scene_segments]

        boundaries = []
        for boundary_index in range(1, len(ordered_scene_segments)):
            if random.choice([True, False]):
                boundaries.append(boundary_index)

        grouped_segments: list[list[dict[str, Any]]] = []
        previous_boundary = 0
        for boundary in boundaries + [len(ordered_scene_segments)]:
            grouped_segments.append(ordered_scene_segments[previous_boundary:boundary])
            previous_boundary = boundary

        return grouped_segments

    @staticmethod
    def _is_grouping_valid(grouping: list[list[dict[str, Any]]], min_duration: float, max_duration: float) -> bool:
        """检查每个组的总时长是否满足区间约束。"""
        for group in grouping:
            group_duration = sum(segment["duration_seconds"] for segment in group)
            if group_duration < min_duration or group_duration > max_duration:
                return False
        return True

    def _build_media_url(self, absolute_file_path: Path) -> str:
        """把服务器绝对路径转换为前端可直接访问的 URL。"""
        relative_path = absolute_file_path.relative_to(self.processed_directory)
        return f"{self.media_url_prefix}/{relative_path.as_posix()}"

    @staticmethod
    def _build_log(level: str, message: str) -> dict[str, str]:
        return {"level": level, "message": message}


class EnhancedJSONEncoder(json.JSONEncoder):
    """兼容 Path 等对象的序列化。"""

    def default(self, obj: Any):  # noqa: ANN001
        if isinstance(obj, Path):
            return str(obj)
        return super().default(obj)
