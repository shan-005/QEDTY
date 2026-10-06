from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime


@dataclass(frozen=True)
class OrbitRecord:
    object_id: str
    epoch: datetime
    x_km: float
    y_km: float
    z_km: float
    vx_km_s: float
    vy_km_s: float
    vz_km_s: float


def parse_omm_kvn(text: str) -> OrbitRecord:
    # Bounded CCSDS KVN reader for required Cartesian state fields; rejects ambiguity instead of guessing.
    values = {}
    for line in text.splitlines():
        if "=" not in line:
            continue
        k, v = (part.strip() for part in line.split("=", 1))
        values[k] = v
    required = ("OBJECT_ID", "EPOCH", "X", "Y", "Z", "X_DOT", "Y_DOT", "Z_DOT")
    missing = [k for k in required if k not in values]
    if missing:
        raise ValueError(f"OMM KVN missing required keys: {missing}")
    epoch = datetime.fromisoformat(values["EPOCH"].replace("Z", "+00:00")).astimezone(UTC)
    return OrbitRecord(values["OBJECT_ID"], epoch, *[float(values[k]) for k in required[2:]])
