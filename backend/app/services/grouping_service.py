"""Random-first + DFS fallback grouping service for ordered scene segments."""

from __future__ import annotations

import random
from typing import Dict, List, Tuple

from app.config import (
    MAXIMUM_DFS_SOLUTION_COLLECTION,
    MAXIMUM_GROUP_DURATION_SECONDS,
    MAXIMUM_RANDOM_GROUP_ATTEMPTS,
    MINIMUM_GROUP_DURATION_SECONDS,
)

OriginalSegment = Dict[str, float | int | str]
SegmentGroup = List[OriginalSegment]


def _calculate_group_duration_seconds(segment_group: SegmentGroup) -> float:
    """Calculate precise duration for one group by summing member segment durations."""

    return float(sum(float(segment["duration_seconds"]) for segment in segment_group))


def _is_duration_legal(duration_seconds: float) -> bool:
    return MINIMUM_GROUP_DURATION_SECONDS <= duration_seconds <= MAXIMUM_GROUP_DURATION_SECONDS


def _precheck_unsolvable_reason(ordered_segments: List[OriginalSegment]) -> str | None:
    """Detect impossible scenarios quickly to avoid unnecessary search attempts."""

    for segment in ordered_segments:
        if float(segment["duration_seconds"]) > MAXIMUM_GROUP_DURATION_SECONDS:
            return (
                "At least one original segment duration exceeds maximum 14 seconds, "
                "therefore no legal contiguous grouping can be formed."
            )
    return None


def _attempt_random_contiguous_partition(ordered_segments: List[OriginalSegment]) -> List[SegmentGroup] | None:
    """Randomly cut boundaries between adjacent segments to build contiguous groups.

    This function intentionally does not use greedy merging. It first creates a random
    boundary vector for the entire ordered list, then validates each group.
    """

    if len(ordered_segments) == 1:
        only_duration = float(ordered_segments[0]["duration_seconds"])
        return [[ordered_segments[0]]] if _is_duration_legal(only_duration) else None

    random_boundaries: List[bool] = [random.choice([True, False]) for _ in range(len(ordered_segments) - 1)]
    grouped_segments: List[SegmentGroup] = []
    current_group: SegmentGroup = [ordered_segments[0]]

    for boundary_index, should_cut_here in enumerate(random_boundaries):
        next_segment = ordered_segments[boundary_index + 1]
        if should_cut_here:
            grouped_segments.append(current_group)
            current_group = [next_segment]
        else:
            current_group.append(next_segment)

    grouped_segments.append(current_group)

    for segment_group in grouped_segments:
        if not _is_duration_legal(_calculate_group_duration_seconds(segment_group)):
            return None

    return grouped_segments


def _collect_all_legal_groupings_with_dfs(ordered_segments: List[OriginalSegment]) -> List[List[SegmentGroup]]:
    """Collect legal contiguous grouping plans using DFS + pruning.

    Pruning strategy:
    - Growing group duration beyond 14 seconds: stop extending this branch.
    - Reaching list end with current group duration below 6: reject branch.
    - Cap collected solutions to protect runtime.
    """

    legal_solutions: List[List[SegmentGroup]] = []
    total_segments = len(ordered_segments)

    def depth_first_search(segment_start_index: int, partial_solution: List[SegmentGroup]) -> None:
        if len(legal_solutions) >= MAXIMUM_DFS_SOLUTION_COLLECTION:
            return
        if segment_start_index >= total_segments:
            legal_solutions.append([group.copy() for group in partial_solution])
            return

        candidate_group: SegmentGroup = []
        candidate_duration_seconds = 0.0

        for end_index in range(segment_start_index, total_segments):
            segment = ordered_segments[end_index]
            candidate_group.append(segment)
            candidate_duration_seconds += float(segment["duration_seconds"])

            if candidate_duration_seconds > MAXIMUM_GROUP_DURATION_SECONDS:
                break
            if candidate_duration_seconds < MINIMUM_GROUP_DURATION_SECONDS:
                continue

            partial_solution.append(candidate_group.copy())
            depth_first_search(end_index + 1, partial_solution)
            partial_solution.pop()

    depth_first_search(0, [])
    return legal_solutions


def build_random_legal_groups(ordered_segments: List[OriginalSegment]) -> Tuple[List[SegmentGroup] | None, str]:
    """Return legal contiguous grouping result or failure reason.

    Flow:
    1) Fast unsolvable pre-check.
    2) Up to 100 random partition attempts.
    3) DFS fallback to collect legal plans, shuffle plans, pick one randomly.
    """

    precheck_reason = _precheck_unsolvable_reason(ordered_segments)
    if precheck_reason:
        return None, precheck_reason

    for _attempt_number in range(1, MAXIMUM_RANDOM_GROUP_ATTEMPTS + 1):
        random_result = _attempt_random_contiguous_partition(ordered_segments)
        if random_result is not None:
            return random_result, "success_via_random_partition"

    legal_solutions = _collect_all_legal_groupings_with_dfs(ordered_segments)
    if not legal_solutions:
        return None, "Current ordered segments cannot be grouped into contiguous groups each lasting 6-14 seconds."

    random.shuffle(legal_solutions)
    selected_solution = random.choice(legal_solutions)
    return selected_solution, "success_via_dfs_fallback"
