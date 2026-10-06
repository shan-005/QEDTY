from pydantic import BaseModel,ConfigDict,Field
from seraph.core.enums import EpistemicStatus
class Claim(BaseModel):
    model_config=ConfigDict(frozen=True,extra="forbid",strict=True)
    claim_id:str; statement:str=Field(min_length=1,max_length=4000); status:EpistemicStatus; evidence_ids:tuple[str,...]=(); provenance_ids:tuple[str,...]=(); limitations:tuple[str,...]=()
