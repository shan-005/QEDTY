from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class Point(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)


class BoundingBox(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)
    west: float = Field(ge=-180, le=180)
    south: float = Field(ge=-90, le=90)
    east: float = Field(ge=-180, le=180)
    north: float = Field(ge=-90, le=90)


class Geometry(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)
    type: str
    coordinates: Any
    bbox: tuple[float, ...] | None = None
    crs: str = "EPSG:4326"
