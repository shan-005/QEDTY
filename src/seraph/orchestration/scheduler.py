from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from .pipeline import Pipeline, Task


@dataclass(slots=True)
class ScheduleState:
    interval_seconds: float
    next_run: datetime | None = None

    def due(self, now: datetime) -> bool:
        return self.next_run is None or now >= self.next_run

    def mark(self, now: datetime) -> None:
        self.next_run = now + timedelta(seconds=self.interval_seconds)


class WorldScheduler:
    """Reference scheduler; durable workflow engines remain production adapters."""

    def __init__(self) -> None:
        self.pipeline = Pipeline([])
        self.schedule: ScheduleState | None = None

    def with_tasks(self, *tasks: Task) -> WorldScheduler:
        self.pipeline = Pipeline(list(tasks))
        return self

    def every(self, seconds: float) -> WorldScheduler:
        if seconds <= 0:
            raise ValueError("seconds must be positive")
        self.schedule = ScheduleState(seconds)
        return self

    def run(self, context: object) -> object:
        return self.pipeline.execute(context)

    def tick(self, context: object, *, now: datetime | None = None) -> object | None:
        if self.schedule is None:
            return self.run(context)
        current = now or datetime.now(UTC)
        if not self.schedule.due(current):
            return None
        result = self.run(context)
        self.schedule.mark(current)
        return result
