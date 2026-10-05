from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class DataQuality(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    completeness: float = Field(default=1.0, ge=0.0, le=1.0)
    timeliness: float = Field(default=1.0, ge=0.0, le=1.0)
    spatial_accuracy: float = Field(default=1.0, ge=0.0, le=1.0)
    semantic_accuracy: float = Field(default=1.0, ge=0.0, le=1.0)
    lineage_strength: float = Field(default=1.0, ge=0.0, le=1.0)

    @property
    def composite(self) -> float:
        values = (self.completeness, self.timeliness, self.spatial_accuracy, self.semantic_accuracy, self.lineage_strength)
        return sum(values) / len(values)
