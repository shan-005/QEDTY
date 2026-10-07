from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Any

from .enums import RunStatus
from .hash import canonicalize
from .time import ensure_utc, seconds, to_rfc3339

if TYPE_CHECKING:
    from datetime import datetime


@dataclass(frozen=True, slots=True)
class RunResult:
    """Execution receipt, intentionally separate from a scientific result value."""

    run_id: str
    status: RunStatus | str
    artifacts: dict[str, Any] = field(default_factory=dict)
    warnings: tuple[str, ...] = ()
    errors: tuple[str, ...] = ()
    started_at: datetime | None = None
    ended_at: datetime | None = None
    software_version: str | None = None
    model_version: str | None = None
    provenance_ids: tuple[str, ...] = ()
    metrics: dict[str, float] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.run_id.strip():
            raise ValueError("run_id must not be blank")
        status = self.status
        if isinstance(status, RunStatus):
            pass
        elif isinstance(status, str):
            try:
                status = RunStatus(status)
            except ValueError:
                status = status.strip()
                if not status:
                    raise ValueError("status must not be blank") from None
        else:
            raise TypeError("status must be a string or RunStatus")
        object.__setattr__(self, "status", status)
        start = ensure_utc(self.started_at) if self.started_at is not None else None
        end = ensure_utc(self.ended_at) if self.ended_at is not None else None
        if start is not None and end is not None and end < start:
            raise ValueError("ended_at precedes started_at")
        object.__setattr__(self, "started_at", start)
        object.__setattr__(self, "ended_at", end)
        object.__setattr__(self, "artifacts", dict(self.artifacts))
        object.__setattr__(self, "metrics", dict(self.metrics))
        object.__setattr__(self, "provenance_ids", tuple(sorted(set(self.provenance_ids))))

    @property
    def is_terminal(self) -> bool:
        return self.status in {
            RunStatus.SUCCEEDED,
            RunStatus.FAILED,
            RunStatus.PARTIAL,
            RunStatus.CANCELLED,
        }

    @property
    def succeeded(self) -> bool:
        return self.status == RunStatus.SUCCEEDED

    @property
    def failed(self) -> bool:
        return self.status == RunStatus.FAILED

    @property
    def duration_seconds(self) -> float | None:
        if self.started_at is None or self.ended_at is None:
            return None
        return seconds(self.started_at, self.ended_at)

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "run_id": self.run_id,
            "status": self.status.value if isinstance(self.status, RunStatus) else self.status,
            "artifacts": canonicalize(self.artifacts),
            "warnings": list(self.warnings),
            "errors": list(self.errors),
            "provenance_ids": list(self.provenance_ids),
            "metrics": canonicalize(self.metrics),
        }
        if self.started_at is not None:
            result["started_at"] = to_rfc3339(self.started_at)
        if self.ended_at is not None:
            result["ended_at"] = to_rfc3339(self.ended_at)
        if self.software_version is not None:
            result["software_version"] = self.software_version
        if self.model_version is not None:
            result["model_version"] = self.model_version
        duration = self.duration_seconds
        if duration is not None:
            result["duration_seconds"] = duration
        return result
