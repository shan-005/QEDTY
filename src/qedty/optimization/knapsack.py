"""Bounded integer 0/1 knapsack semantic reference for cross-language tests."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

MAX_KNAPSACK_CAPACITY = 1_000_000
MAX_KNAPSACK_ITEMS = 128
MAX_KNAPSACK_ID_BYTES = 128
MAX_KNAPSACK_STATE_ID_ENTRIES = 200_000


@dataclass(frozen=True, slots=True)
class KnapsackItem:
    id: str
    weight: int
    value: float


@dataclass(frozen=True, slots=True)
class KnapsackResult:
    selected_ids: tuple[str, ...]
    total_weight: int
    total_value: float


def _better(candidate: KnapsackResult, current: KnapsackResult) -> bool:
    return candidate.total_value > current.total_value or (
        candidate.total_value == current.total_value
        and candidate.selected_ids < current.selected_ids
    )


def integer_knapsack(items: Sequence[KnapsackItem], capacity: int) -> KnapsackResult:
    """Exact 0/1 DP with explicit limits and deterministic selected-ID ties."""
    if isinstance(capacity, bool) or not isinstance(capacity, int) or capacity < 0:
        raise ValueError("capacity must be a non-negative integer")
    ordered = tuple(items)
    state_id_budget = (capacity + 1) * max(len(ordered), 1)
    if (
        capacity > MAX_KNAPSACK_CAPACITY
        or len(ordered) > MAX_KNAPSACK_ITEMS
        or state_id_budget > MAX_KNAPSACK_STATE_ID_ENTRIES
    ):
        raise ValueError("knapsack resource bounds exceeded")
    seen: set[str] = set()
    for item in ordered:
        if (
            not isinstance(item.id, str)
            or not item.id.strip()
            or len(item.id.encode("utf-8")) > MAX_KNAPSACK_ID_BYTES
            or isinstance(item.weight, bool)
            or not isinstance(item.weight, int)
            or item.weight <= 0
            or isinstance(item.value, bool)
            or not isinstance(item.value, (int, float))
            or not math.isfinite(float(item.value))
            or item.value < 0.0
            or item.id in seen
        ):
            raise ValueError(
                "item identifiers must be unique/nonblank; weight must be positive and value finite/non-negative"
            )
        seen.add(item.id)
    ordered = tuple(sorted(ordered, key=lambda item: item.id))
    empty = KnapsackResult((), 0, 0.0)
    dp = [empty for _ in range(capacity + 1)]
    for item in ordered:
        if item.weight > capacity:
            continue
        for current_capacity in range(capacity, item.weight - 1, -1):
            previous = dp[current_capacity - item.weight]
            selected = tuple(sorted((*previous.selected_ids, item.id)))
            candidate_value = previous.total_value + float(item.value)
            if not math.isfinite(candidate_value):
                raise ValueError("knapsack total value must be finite")
            candidate = KnapsackResult(
                selected,
                previous.total_weight + item.weight,
                candidate_value,
            )
            if _better(candidate, dp[current_capacity]):
                dp[current_capacity] = candidate
    best = empty
    for candidate in dp:
        if _better(candidate, best):
            best = candidate
    return best
