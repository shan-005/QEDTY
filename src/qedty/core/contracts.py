from __future__ import annotations

import contextlib
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Any, TypeVar

from .enums import EpistemicStatus
from .hash import canonicalize
from .time import ensure_utc, to_rfc3339

if TYPE_CHECKING:
    from collections.abc import Callable
    from datetime import datetime

T = TypeVar("T")
U = TypeVar("U")


@dataclass(frozen=True, slots=True)
class ContractResult[T]:
    """Evidence/provenance-bearing envelope for a scientific/domain result."""

    value: T
    epistemic_state: EpistemicStatus | str
    evidence_ids: tuple[str, ...] = ()
    provenance_ids: tuple[str, ...] = ()
    assumptions: tuple[str, ...] = ()
    model_id: str | None = None
    model_version: str | None = None
    valid_at: datetime | None = None
    uncertainty: object | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        raw_status: object = self.epistemic_state

        if isinstance(raw_status, EpistemicStatus):
            normalized: EpistemicStatus | str = raw_status
        elif type(raw_status) is str:
            normalized = raw_status.strip()
            if not normalized:
                raise ValueError("epistemic_state must not be blank") from None
            with contextlib.suppress(ValueError):
                normalized = EpistemicStatus(normalized)
        else:
            raise TypeError("epistemic_state must be a string or EpistemicStatus")

        object.__setattr__(self, "epistemic_state", normalized)
        object.__setattr__(self, "evidence_ids", _unique_sorted(self.evidence_ids))
        object.__setattr__(
            self,
            "provenance_ids",
            _unique_sorted(self.provenance_ids),
        )
        object.__setattr__(
            self,
            "assumptions",
            _unique_sorted(self.assumptions),
        )

        if self.valid_at is not None:
            object.__setattr__(self, "valid_at", ensure_utc(self.valid_at))

        object.__setattr__(self, "metadata", dict(self.metadata))

    @property
    def epistemic_status(self) -> EpistemicStatus | str:
        """Compatibility alias for callers using the longer spelling."""
        return self.epistemic_state

    def map(self, transform: Callable[[T], U]) -> ContractResult[U]:
        """Transform only the value while preserving contract metadata."""
        return ContractResult(
            value=transform(self.value),
            epistemic_state=self.epistemic_state,
            evidence_ids=self.evidence_ids,
            provenance_ids=self.provenance_ids,
            assumptions=self.assumptions,
            model_id=self.model_id,
            model_version=self.model_version,
            valid_at=self.valid_at,
            uncertainty=self.uncertainty,
            metadata=self.metadata,
        )

    def with_evidence(self, *evidence_ids: str) -> ContractResult[T]:
        return ContractResult(
            value=self.value,
            epistemic_state=self.epistemic_state,
            evidence_ids=(*self.evidence_ids, *evidence_ids),
            provenance_ids=self.provenance_ids,
            assumptions=self.assumptions,
            model_id=self.model_id,
            model_version=self.model_version,
            valid_at=self.valid_at,
            uncertainty=self.uncertainty,
            metadata=self.metadata,
        )

    def with_assumptions(self, *assumptions: str) -> ContractResult[T]:
        return ContractResult(
            value=self.value,
            epistemic_state=self.epistemic_state,
            evidence_ids=self.evidence_ids,
            provenance_ids=self.provenance_ids,
            assumptions=(*self.assumptions, *assumptions),
            model_id=self.model_id,
            model_version=self.model_version,
            valid_at=self.valid_at,
            uncertainty=self.uncertainty,
            metadata=self.metadata,
        )

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "value": canonicalize(self.value),
            "epistemic_state": (
                self.epistemic_state.value
                if isinstance(self.epistemic_state, EpistemicStatus)
                else self.epistemic_state
            ),
            "evidence_ids": list(self.evidence_ids),
            "provenance_ids": list(self.provenance_ids),
            "assumptions": list(self.assumptions),
            "metadata": canonicalize(self.metadata),
        }

        if self.model_id is not None:
            result["model_id"] = self.model_id

        if self.model_version is not None:
            result["model_version"] = self.model_version

        if self.valid_at is not None:
            result["valid_at"] = to_rfc3339(self.valid_at)

        if self.uncertainty is not None:
            result["uncertainty"] = canonicalize(self.uncertainty)

        return result


def _unique_sorted(values: tuple[str, ...]) -> tuple[str, ...]:
    cleaned = {value.strip() for value in values if value.strip()}
    return tuple(sorted(cleaned))
