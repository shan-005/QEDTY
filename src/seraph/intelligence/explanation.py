from __future__ import annotations

from dataclasses import dataclass

from seraph.core.hash import sha256_hex


@dataclass(frozen=True, slots=True)
class ExplanationFactor:
    feature: str
    contribution: float
    direction: str
    evidence_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.feature.strip():
            raise ValueError("feature must not be blank")
        if self.direction not in {"increases", "decreases", "neutral"}:
            raise ValueError("invalid factor direction")


@dataclass(frozen=True, slots=True)
class Explanation:
    statement: str
    inputs: tuple[str, ...]
    method: str
    caveats: tuple[str, ...]
    factors: tuple[ExplanationFactor, ...] = ()
    confidence: float = 1.0

    def __post_init__(self) -> None:
        if not self.statement.strip() or not self.method.strip():
            raise ValueError("statement and method must not be blank")
        if not 0 <= self.confidence <= 1:
            raise ValueError("confidence must be in [0,1]")

    @property
    def digest(self) -> str:
        return sha256_hex(self)


def explain(
    statement: str,
    inputs: list[str],
    method: str,
    caveats: list[str],
    *,
    factors: list[ExplanationFactor] | None = None,
    confidence: float = 1.0,
) -> Explanation:
    ordered = tuple(sorted(inputs))
    fs = tuple(sorted(factors or (), key=lambda x: (-abs(x.contribution), x.feature)))
    return Explanation(statement, ordered, method, tuple(caveats), fs, confidence)
