from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

from qedty.core.hash import deterministic_id


@dataclass(slots=True)
class RunRecord:
    run_id: str
    started_at: datetime
    status: str
    ended_at: datetime | None = None
    task_results: dict[str, str] = field(default_factory=dict)
    warnings: tuple[str, ...] = ()

    def finish(self, status: str = "succeeded") -> None:
        if status not in {"succeeded", "failed", "cancelled"}:
            raise ValueError("invalid terminal status")
        self.status = status
        self.ended_at = datetime.now(UTC)


def new_run(run_key: str | None = None) -> RunRecord:
    now = datetime.now(UTC)
    key = run_key or now.isoformat()
    return RunRecord(deterministic_id("run", key), now, "running")
