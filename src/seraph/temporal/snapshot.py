from __future__ import annotations
from datetime import datetime
from pydantic import BaseModel,ConfigDict
from seraph.core.time import ensure_utc
class SnapshotMeta(BaseModel):
    model_config=ConfigDict(frozen=True,extra="forbid",strict=True)
    snapshot_id:str; captured_at:datetime; world_digest:str; schema_version:str
    def normalized(self)->"SnapshotMeta": return self.model_copy(update={"captured_at":ensure_utc(self.captured_at)})
