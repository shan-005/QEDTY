from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class GraphSchemaVersion(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    name: str = Field(default="seraph-temporal-world-graph")
    major: int = Field(default=1, ge=1)
    minor: int = Field(default=0, ge=0)
    patch: int = Field(default=0, ge=0)

    @property
    def version(self) -> str:
        return f"{self.major}.{self.minor}.{self.patch}"

    @property
    def key(self) -> str:
        return f"{self.name}@{self.version}"
