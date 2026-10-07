from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime


@dataclass(frozen=True, slots=True)
class OrbitRecord:
    object_id: str
    epoch: datetime
    x_km: float
    y_km: float
    z_km: float
    vx_km_s: float
    vy_km_s: float
    vz_km_s: float
    source_format: str = "CCSDS-OMM-KVN"


def parse_omm_kvn(text: str) -> OrbitRecord:
    values: dict[str, str] = {}
    for line in text.splitlines():
        if "=" not in line:
            continue
        k, v = (part.strip() for part in line.split("=", 1))
        values[k] = v
    required = ("OBJECT_ID", "EPOCH", "X", "Y", "Z", "X_DOT", "Y_DOT", "Z_DOT")
    missing = [k for k in required if k not in values]
    if missing:
        raise ValueError(f"OMM KVN missing required keys: {missing}")

    epoch = datetime.fromisoformat(values["EPOCH"]).astimezone(UTC)
    return OrbitRecord(
        object_id=values["OBJECT_ID"],
        epoch=epoch,
        x_km=float(values["X"]),
        y_km=float(values["Y"]),
        z_km=float(values["Z"]),
        vx_km_s=float(values["X_DOT"]),
        vy_km_s=float(values["Y_DOT"]),
        vz_km_s=float(values["Z_DOT"]),
    )
