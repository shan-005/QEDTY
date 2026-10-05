from __future__ import annotations

from seraph.continuity.models import ContinuityPoint, ContinuityResult
from seraph.core.time import duration_hours
from seraph.shocks.models import Shock
from seraph.shocks.propagation import PropagationEvent


class ContinuityEngine:
    """Produce a piecewise-linear continuity curve from a propagation result."""

    def simulate(
        self,
        *,
        entity_id: str,
        shock: Shock,
        events: tuple[PropagationEvent, ...],
        critical_threshold: float = 0.30,
    ) -> ContinuityResult:
        if not 0.0 < critical_threshold < 1.0:
            raise ValueError("critical_threshold must be in (0, 1)")
        event = next((item for item in events if item.entity_id == entity_id), None)
        severity = 0.0 if event is None else event.severity
        capacity = max(0.0, min(1.0, 1.0 - severity))
        start, end = shock.start, shock.end
        midpoint = start + (end - start) / 2
        points = (
            ContinuityPoint(timestamp=start, capacity_fraction=1.0),
            ContinuityPoint(timestamp=midpoint, capacity_fraction=capacity),
            ContinuityPoint(timestamp=end, capacity_fraction=capacity),
        )
        area = sum(
            (left.capacity_fraction + right.capacity_fraction) / 2.0
            * duration_hours(left.timestamp, right.timestamp)
            for left, right in zip(points, points[1:])
        )
        threshold_time = duration_hours(start, midpoint) if capacity < critical_threshold else None
        return ContinuityResult(
            entity_id=entity_id,
            points=points,
            minimum_capacity_fraction=capacity,
            time_to_threshold_hours=threshold_time,
            capacity_hours=area,
        )
