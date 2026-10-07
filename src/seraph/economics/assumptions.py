from __future__ import annotations

from dataclasses import dataclass, field

from seraph.core.hash import sha256_hex


@dataclass(frozen=True, slots=True)
class Assumption:
    name: str
    value: str
    source: str | None = None
    confidence: float | None = None

    def validate(self) -> None:
        if not self.name.strip():
            raise ValueError("assumption name must not be blank")
        if self.confidence is not None and not 0 <= self.confidence <= 1:
            raise ValueError("confidence must be in [0,1]")


@dataclass(frozen=True, slots=True)
class AssumptionSet:
    assumptions: tuple[Assumption, ...] = field(default_factory=tuple)

    def validate(self) -> None:
        names = set()
        for a in self.assumptions:
            a.validate()
            if a.name in names:
                raise ValueError("duplicate assumption name")
            names.add(a.name)

    @property
    def digest(self) -> str:
        self.validate()
        return sha256_hex(
            [
                a.__dict__
                if hasattr(a, "__dict__")
                else {
                    "name": a.name,
                    "value": a.value,
                    "source": a.source,
                    "confidence": a.confidence,
                }
                for a in self.assumptions
            ]
        )
