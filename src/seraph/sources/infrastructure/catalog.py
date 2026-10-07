from __future__ import annotations

from dataclasses import dataclass
from math import isfinite


@dataclass(frozen=True, slots=True)
class InfrastructureAsset:
    asset_id: str
    asset_type: str
    region_id: str
    criticality: float
    capacity: float
    unit: str
    evidence_id: str
    source_id: str = ""
    observed_at: str = ""
    status: str = "active"

    def __post_init__(self) -> None:
        if not self.asset_id.strip() or not self.asset_type.strip():
            raise ValueError("asset_id and asset_type are required")
        if not isfinite(self.criticality) or not 0 <= self.criticality <= 1:
            raise ValueError("criticality must be in [0,1]")
        if not isfinite(self.capacity) or self.capacity < 0:
            raise ValueError("capacity must be finite and non-negative")
