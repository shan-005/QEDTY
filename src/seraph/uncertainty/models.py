from pydantic import BaseModel, ConfigDict, Field, model_validator


class Interval(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)
    lower: float
    estimate: float
    upper: float
    confidence_level: float = Field(default=0.9, gt=0, lt=1)
    method: str = "scenario-envelope"

    @model_validator(mode="after")
    def ordered(self):
        if not self.lower <= self.estimate <= self.upper:
            raise ValueError("lower <= estimate <= upper required")
        return self
