from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from seraph.core.hash import deterministic_id


@dataclass
class RunRecord:
    run_id: str
    started_at: datetime
    status: str


def new_run() -> RunRecord:
    now = datetime.now(UTC)
    return RunRecord(deterministic_id("run", now.isoformat()), now, "running")
