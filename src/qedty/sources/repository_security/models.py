from pydantic import BaseModel, ConfigDict, Field


class SecurityObservationModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)
    observation_id: str
    path: str
    category: str
    severity: str = Field(pattern="^(critical|high|medium|low|info)$")
    evidence_ids: tuple[str, ...] = ()
    line_number: int = Field(default=0, ge=0)
    content_sha256: str = ""
