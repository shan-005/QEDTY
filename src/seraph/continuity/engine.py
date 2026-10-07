from __future__ import annotations

import itertools
from datetime import timedelta
from math import isfinite
from typing import TYPE_CHECKING

from seraph.core.time import hours

from .models import ContinuityPoint, ContinuityResult
from .recovery import exponential_recovery
from .thresholds import validate_threshold

if TYPE_CHECKING:
    from seraph.propagation.models import PropagationEvent
    from seraph.scenarios.shocks import Shock


class ContinuityEngine:
    """Turn propagated impairment into an auditable service trajectory.

    The engine intentionally models a trajectory, not a probability distribution.
    Recovery behavior is an explicit assumption supplied by the caller.
    """

    def simulate(
        self,
        entity_id: str,
        shock: Shock,
        events: tuple[PropagationEvent, ...],
        *,
        threshold: float = 0.30,
        baseline_capacity: float = 1.0,
        recovery_rate: float | None = None,
        recovery_horizon_hours: float = 0.0,
    ) -> ContinuityResult:
        validate_threshold(threshold)
        if not 0 <= baseline_capacity <= 1 or not isfinite(baseline_capacity):
            raise ValueError("baseline_capacity must be finite and in [0,1]")
        if recovery_rate is not None and recovery_rate <= 0:
            raise ValueError("recovery_rate must be positive")
        if recovery_horizon_hours < 0:
            raise ValueError("recovery_horizon_hours must be non-negative")

        shock_n = shock.normalized()
        candidates = tuple(e for e in events if e.entity_id == entity_id)
        impairment = max((e.impairment for e in candidates), default=0.0)
        impaired_capacity = baseline_capacity * (1.0 - impairment)
        start = shock_n.starts_at
        shock_end = shock_n.ends_at
        points: list[ContinuityPoint] = [
            ContinuityPoint(
                timestamp=start,
                capacity_fraction=impaired_capacity,
                phase="response" if impairment > 0 else "baseline",
                note="shock impact" if impairment > 0 else None,
            ),
            ContinuityPoint(
                timestamp=shock_end, capacity_fraction=impaired_capacity, phase="response"
            ),
        ]
        horizon_end = shock_end
        full_recovery: float | None = 0.0 if impaired_capacity >= baseline_capacity else None
        if (
            recovery_rate is not None
            and recovery_horizon_hours > 0
            and impaired_capacity < baseline_capacity
        ):
            horizon_end = shock_end + timedelta(hours=recovery_horizon_hours)
            rec = exponential_recovery(
                impaired_capacity, baseline_capacity, shock_end, horizon_end, recovery_rate, steps=8
            )
            points.extend(
                ContinuityPoint(
                    timestamp=t, capacity_fraction=max(0.0, min(1.0, v)), phase="recovery"
                )
                for t, v in rec[1:]
            )
            full_recovery = recovery_horizon_hours if rec[-1][1] >= baseline_capacity else None
        ordered = tuple(sorted(points, key=lambda p: (p.timestamp, p.phase)))
        capacity_area = 0.0
        deficit_area = 0.0
        below_hours = 0.0
        threshold_time: float | None = 0.0 if ordered[0].capacity_fraction >= threshold else None
        for left, right in itertools.pairwise(ordered):
            dt = hours(left.timestamp, right.timestamp)
            c0, c1 = left.capacity_fraction, right.capacity_fraction
            avg = (c0 + c1) / 2
            capacity_area += avg * dt
            deficit_area += max(0.0, baseline_capacity - avg) * dt
            if c0 < threshold and c1 < threshold:
                below_hours += dt
            elif c0 < threshold <= c1 and c1 != c0:
                frac = (threshold - c0) / (c1 - c0)
                below_hours += dt * max(0.0, min(1.0, frac))
            elif c1 < threshold <= c0 and c1 != c0:
                frac = (c0 - threshold) / (c0 - c1)
                below_hours += dt * max(0.0, min(1.0, frac))
            if threshold_time is None and c0 < threshold <= c1 and c1 != c0:
                frac = (threshold - c0) / (c1 - c0)
                threshold_time = hours(start, left.timestamp) + dt * max(0.0, min(1.0, frac))
        duration = hours(start, horizon_end)
        resilience_index = (
            1.0
            if duration <= 0 or baseline_capacity <= 0
            else max(0.0, min(1.0, 1.0 - deficit_area / (duration * baseline_capacity)))
        )
        return ContinuityResult(
            entity_id=entity_id,
            points=ordered,
            minimum_capacity_fraction=min(p.capacity_fraction for p in ordered),
            time_below_threshold_hours=below_hours,
            capacity_hours=capacity_area,
            threshold=threshold,
            baseline_capacity_fraction=baseline_capacity,
            deficit_hours=deficit_area,
            resilience_index=resilience_index,
            time_to_threshold_hours=threshold_time,
            time_to_full_recovery_hours=full_recovery,
            fully_recovered=full_recovery is not None,
            shock_ids=(shock_n.shock_id,),
            status="modeled",
        )
