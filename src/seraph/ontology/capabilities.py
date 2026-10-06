from pydantic import BaseModel, ConfigDict, Field


class Capability(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)
    capability_id: str = Field(min_length=1, max_length=256)
    name: str = Field(min_length=1, max_length=256)
    nominal_capacity: float = Field(gt=0)
    unit: str = Field(min_length=1, max_length=64)
    owner_entity_id: str = Field(min_length=1, max_length=256)
    properties: dict[str, str] = {}
