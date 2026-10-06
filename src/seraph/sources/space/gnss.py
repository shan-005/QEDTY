from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class GnssObservation:
    station_id: str
    satellite_id: str
    epoch_seconds: float
    observables: dict[str, float]

    def validate(self) -> None:
        if self.epoch_seconds < 0:
            raise ValueError("epoch must be non-negative")
        if not self.satellite_id:
            raise ValueError("satellite_id empty")
