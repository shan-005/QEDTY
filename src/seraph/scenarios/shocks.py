from datetime import datetime
from pydantic import BaseModel,ConfigDict,Field
from seraph.core.enums import EventType,EpistemicStatus
from seraph.core.time import ensure_utc
class Shock(BaseModel):
    model_config=ConfigDict(frozen=True,extra="forbid",strict=True)
    shock_id:str; name:str; event_type:EventType; source_entity_id:str; starts_at:datetime; ends_at:datetime; severity:float=Field(ge=0,le=1); epistemic_status:EpistemicStatus=EpistemicStatus.MODELED
    def normalized(self)->"Shock":return self.model_copy(update={"starts_at":ensure_utc(self.starts_at),"ends_at":ensure_utc(self.ends_at)})
