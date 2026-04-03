import random
import subprocess
from pathlib import Path

from .media_utils import build_media_url


def build_regroup_plans(segments: list[dict]) -> list[list[dict]]:
    variant_pools = []
    for segment in segments:
        generated_videos = segment.get("generated_videos") or []
        if not generated_videos:
            continue
        variant_pools.append(generated_videos)

    if not variant_pools:
        return []

    regroup_count = max(len(pool) for pool in variant_pools)
    regroup_plans: list[list[dict]] = [[] for _ in range(regroup_count)]

    for pool in variant_pools:
        if len(pool) == 1:
            chosen_sequence = [pool[0]] * regroup_count
        else:
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
    regrouped_output_directory.mkdir(parents=True, exist_ok=True)

    for stale_file in regrouped_output_directory.glob("*"):
        if stale_file.is_file():
            stale_file.unlink()

    regroup_plans = build_regroup_plans(segments)
    regrouped_videos = []

    for regroup_index, regroup_plan in enumerate(regroup_plans, start=1):
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
