from dataclasses import dataclass


@dataclass(frozen=True)
class SpaceWeatherIndex:
    name: str
    value: float
    unit: str
    observed_at: str
    source_evidence_id: str
