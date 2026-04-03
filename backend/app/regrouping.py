"""裂变视频重组逻辑。

当某个合并片段已经生成出多个变体后，这个模块负责把这些片段变体
重新组合成多条完整视频，供前端预览不同的整片版本。
"""

import random
import shutil
import subprocess
from pathlib import Path

from .media_utils import build_media_url


def build_regroup_plans(segments: list[dict]) -> list[list[dict]]:
    """根据每个片段的可选变体，构造多套重组方案。"""

    variant_pools = []
    for segment in segments:
        # 每个片段都可能有多个 AI 生成变体。
        generated_videos = segment.get("generated_videos") or []
        if not generated_videos:
            return []
        variant_pools.append(generated_videos)

    if not variant_pools:
        return []

    regroup_count = max(len(pool) for pool in variant_pools)
    regroup_plans: list[list[dict]] = [[] for _ in range(regroup_count)]

    for pool in variant_pools:
        # 只有一个候选时，只能在所有方案中重复使用同一个片段。
        if len(pool) == 1:
            chosen_sequence = [pool[0]] * regroup_count
        else:
            # 候选足够多时，尽量打散，制造不同方案之间的差异。
            shuffled_pool = pool[:]
            random.shuffle(shuffled_pool)
            chosen_sequence = shuffled_pool[:]
            while len(chosen_sequence) < regroup_count:
                chosen_sequence.append(random.choice(pool))
            random.shuffle(chosen_sequence)

        for regroup_index in range(regroup_count):
            regroup_plans[regroup_index].append(chosen_sequence[regroup_index])

    random.shuffle(regroup_plans)
    return regroup_plans


def export_regrouped_videos(
    *,
    segments: list[dict],
    regrouped_output_directory: Path,
    data_root: Path,
    base_public_url: str,
) -> list[dict]:
    """把重组方案真正导出为 mp4 文件。"""

    # 每次手动重组都先整目录删除再重建，确保产物是全新的。
    shutil.rmtree(regrouped_output_directory, ignore_errors=True)
    regrouped_output_directory.mkdir(parents=True, exist_ok=True)

    regroup_plans = build_regroup_plans(segments)
    regrouped_videos = []

    for regroup_index, regroup_plan in enumerate(regroup_plans, start=1):
        # 每一套 `regroup_plan` 最终都会导出一条完整视频。
        concat_file_path = regrouped_output_directory / f"regroup_{regroup_index:03d}_concat.txt"
        output_path = regrouped_output_directory / f"regroup_{regroup_index:03d}.mp4"

        with concat_file_path.open("w", encoding="utf-8") as concat_file:
            for variant in regroup_plan:
                safe_path = str(Path(variant["file_path"]).resolve()).replace("'", "'\\''")
                concat_file.write(f"file '{safe_path}'\n")

        command = [
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
            str(output_path),
        ]
        result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
        concat_file_path.unlink(missing_ok=True)
        if result.returncode != 0:
            stderr_text = result.stderr.decode("utf-8", errors="replace")
            raise RuntimeError(f"ffmpeg regroup failed for regroup_{regroup_index:03d}: {stderr_text}")

        regrouped_videos.append(
            {
                "regroup_index": regroup_index,
                "file_path": str(output_path),
                "public_url": build_media_url(base_public_url, data_root, output_path),
                "source_variants": [
                    {
                        "group_index": segments[segment_index]["group_index"],
                        "variant_index": variant["variant_index"],
                        "file_path": variant["file_path"],
                    }
                    for segment_index, variant in enumerate(regroup_plan)
                ],
            }
        )

    return regrouped_videos
