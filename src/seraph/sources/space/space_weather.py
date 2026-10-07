from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SpaceWeatherIndex:
    name: str
    value: float
    unit: str
    observed_at: str
    source_evidence_id: str
    source_uri: str = ""
    quality: str = "unknown"
