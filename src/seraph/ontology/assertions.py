from __future__ import annotations
from datetime import datetime
from pydantic import BaseModel,ConfigDict,Field
from seraph.core.enums import EpistemicStatus
from seraph.core.time import ensure_utc
class Assertion(BaseModel):
    model_config=ConfigDict(frozen=True,extra="forbid",strict=True)
    assertion_id:str=Field(min_length=1,max_length=256)
    subject_id:str; predicate:str; object_id:str|None=None; value:object|None=None
    asserted_at:datetime; valid_from:datetime|None=None; valid_to:datetime|None=None
    epistemic_status:EpistemicStatus; confidence:float=Field(default=1,ge=0,le=1); evidence_ids:tuple[str,...]=(); provenance_ids:tuple[str,...]=()
