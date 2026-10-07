from __future__ import annotations

from dataclasses import dataclass
from math import isfinite


@dataclass(frozen=True, slots=True)
class TradeFlow:
    exporter: str
    importer: str
    sector: str
    value_usd: float

    def validate(self) -> None:
        if self.value_usd < 0 or not isfinite(self.value_usd):
            raise ValueError("trade value must be non-negative and finite")
        if not self.exporter or not self.importer or not self.sector:
            raise ValueError("trade identifiers must not be blank")


@dataclass(frozen=True, slots=True)
class TradeMatrix:
    exporters: tuple[str, ...]
    importers: tuple[str, ...]
    values: tuple[tuple[float, ...], ...]

    def validate(self) -> None:
        if len(self.values) != len(self.exporters) or any(
            len(r) != len(self.importers) for r in self.values
        ):
            raise ValueError("trade matrix dimensions mismatch")
        if any(v < 0 for r in self.values for v in r):
            raise ValueError("trade values must be non-negative")

    def total(self) -> float:
        return sum(sum(r) for r in self.values)

    def exporter_totals(self) -> dict[str, float]:
        return {e: sum(self.values[i]) for i, e in enumerate(self.exporters)}

    def importer_totals(self) -> dict[str, float]:
        return {
            im: sum(self.values[i][j] for i in range(len(self.exporters)))
            for j, im in enumerate(self.importers)
        }

    def exporter_hhi(self) -> float:
        total = self.total()
        if total <= 0:
            return 0.0
        shares = [v / total for v in self.exporter_totals().values()]
        return sum(s * s for s in shares)
