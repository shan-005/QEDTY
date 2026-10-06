from dataclasses import dataclass


@dataclass(frozen=True)
class InfrastructureAsset:
    asset_id: str
    asset_type: str
    region_id: str
    criticality: float
    capacity: float
    unit: str
    evidence_id: str
