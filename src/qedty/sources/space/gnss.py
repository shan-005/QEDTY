from __future__ import annotations

from dataclasses import dataclass
from math import isfinite


@dataclass(frozen=True, slots=True)
class GnssObservation:
    station_id: str
    satellite_id: str
    epoch_seconds: float
    observables: dict[str, float]
    receiver_id: str = ""
    constellations: tuple[str, ...] = ()

    def validate(self) -> None:
        if self.epoch_seconds < 0 or not isfinite(self.epoch_seconds):
            raise ValueError("epoch must be finite and non-negative")
        if not self.satellite_id or not self.station_id:
            raise ValueError("station_id and satellite_id must be non-empty")
        if any(not isfinite(v) for v in self.observables.values()):
            raise ValueError("GNSS observables must be finite")
