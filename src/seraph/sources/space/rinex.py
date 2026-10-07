from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RinexHeader:
    version: str
    file_type: str
    satellite_system: str
    program: str = ""
    marker_name: str = ""


def parse_header(text: str) -> RinexHeader:
    first = next((line for line in text.splitlines() if "RINEX VERSION / TYPE" in line), "")
    if not first:
        raise ValueError("RINEX header marker not found")
    version = first[:9].strip()
    file_type = first[20:21].strip()
    system = first[40:41].strip()
    if not version.startswith("4."):
        raise ValueError("SERAPH GNSS adapter requires RINEX 4.x")
    program_line = next((line for line in text.splitlines() if "PGM / RUN BY / DATE" in line), "")
    marker_line = next((line for line in text.splitlines() if "MARKER NAME" in line), "")
    return RinexHeader(
        version, file_type, system, program_line[:20].strip(), marker_line[:60].strip()
    )
