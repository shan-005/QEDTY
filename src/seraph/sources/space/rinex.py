from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RinexHeader:
    version: str
    file_type: str
    satellite_system: str


def parse_header(text: str) -> RinexHeader:
    first = next((line for line in text.splitlines() if "RINEX VERSION / TYPE" in line), "")
    if not first:
        raise ValueError("RINEX header marker not found")
    version = first[:9].strip()
    file_type = first[20:21].strip()
    system = first[40:41].strip()
    if not version.startswith("4."):
        raise ValueError("SERAPH GNSS adapter requires RINEX 4.x")
    return RinexHeader(version, file_type, system)
