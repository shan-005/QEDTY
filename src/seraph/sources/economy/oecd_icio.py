from __future__ import annotations

from dataclasses import dataclass
from math import isfinite


@dataclass(frozen=True, slots=True)
class ICIOFlow:
    reporter: str
    partner: str
    industry: str
    value_usd: float
    vintage: str
    source_uri: str
    unit: str = "USD"
    measure: str = "intermediate_flow"
    evidence_id: str = ""

    def __post_init__(self) -> None:
        if not isfinite(self.value_usd) or self.value_usd < 0:
            raise ValueError("ICIO flow must be finite and non-negative")
        if not self.reporter or not self.partner or not self.industry:
            raise ValueError("reporter, partner and industry are required")

    def normalized(self) -> dict[str, object]:
        return {
            "reporter": self.reporter.upper(),
            "partner": self.partner.upper(),
            "industry": self.industry,
            "value_usd": self.value_usd,
            "vintage": self.vintage,
            "source_uri": self.source_uri,
            "unit": self.unit,
            "measure": self.measure,
            "evidence_id": self.evidence_id,
        }
