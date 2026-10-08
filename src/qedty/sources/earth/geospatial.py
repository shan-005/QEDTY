from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from qedty.spatial.models import BoundingBox, Point


@dataclass(frozen=True, slots=True)
class HazardFootprint:
    hazard_id: str
    bbox: BoundingBox
    severity: float
    observed_at: str
    evidence_id: str
    source_uri: str = ""
    collection_id: str = ""

    def __post_init__(self) -> None:
        if not self.hazard_id.strip() or not self.evidence_id.strip():
            raise ValueError("hazard_id and evidence_id are required")
        if not 0 <= self.severity <= 1:
            raise ValueError("severity must be in [0,1]")

    def contains(self, p: Point) -> bool:
        lon = p.longitude
        lat = p.latitude
        return (
            lat >= self.bbox.south
            and lat <= self.bbox.north
            and (
                (self.bbox.west <= lon <= self.bbox.east)
                if self.bbox.west <= self.bbox.east
                else (lon >= self.bbox.west or lon <= self.bbox.east)
            )
        )

    def to_ogc_feature(self) -> dict[str, object]:
        return {
            "type": "Feature",
            "id": self.hazard_id,
            "properties": {
                "severity": self.severity,
                "observed_at": self.observed_at,
                "evidence_id": self.evidence_id,
            },
            "bbox": [self.bbox.west, self.bbox.south, self.bbox.east, self.bbox.north],
        }
