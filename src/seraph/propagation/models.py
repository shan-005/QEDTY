from __future__ import annotations
from datetime import datetime
from pydantic import BaseModel,ConfigDict,Field
from seraph.core.enums import EpistemicStatus
class PropagationEvent(BaseModel):
    model_config=ConfigDict(frozen=True,extra="forbid",strict=True)
    entity_id:str; impairment:float=Field(ge=0,le=1); depth:int=Field(ge=0); path_entity_ids:tuple[str,...]; path_relationship_ids:tuple[str,...]; effective_at:datetime; status:EpistemicStatus
