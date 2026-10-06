from __future__ import annotations
from datetime import datetime
from pydantic import BaseModel,ConfigDict,Field,model_validator
from seraph.core.hash import deterministic_id,sha256_hex
from seraph.core.time import ensure_utc
class ProvenanceActivity(BaseModel):
    model_config=ConfigDict(frozen=True,extra="forbid",strict=True)
    provenance_id:str=Field(min_length=1,max_length=256); activity:str=Field(min_length=1,max_length=512); agent:str=Field(min_length=1,max_length=512); started_at:datetime; ended_at:datetime|None=None; used_evidence_ids:tuple[str,...]=(); generated_ids:tuple[str,...]=(); parent_ids:tuple[str,...]=(); software_version:str=Field(min_length=1,max_length=128); parameters_digest:str=Field(pattern=r"^[0-9a-f]{64}$")
    @model_validator(mode="after")
    def valid(self):
        object.__setattr__(self,"started_at",ensure_utc(self.started_at))
        if self.ended_at is not None: object.__setattr__(self,"ended_at",ensure_utc(self.ended_at))
        if self.ended_at and self.ended_at<self.started_at: raise ValueError("ended before started")
        return self
    @classmethod
    def create(cls,activity:str,agent:str,started_at:datetime,software_version:str,parameters:object,**kwargs):
        pd=sha256_hex(parameters); pid=deterministic_id("prov",activity,agent,started_at.isoformat(),pd)
        return cls(provenance_id=pid,activity=activity,agent=agent,started_at=started_at,software_version=software_version,parameters_digest=pd,**kwargs)
class ProvenanceChain:
    def __init__(self): self._items:dict[str,ProvenanceActivity]={}
    def add(self,x:ProvenanceActivity):
        if x.provenance_id in self._items and self._items[x.provenance_id]!=x: raise ValueError("provenance collision")
        for pid in x.parent_ids:
            if pid not in self._items: raise KeyError(f"unknown parent provenance: {pid}")
        self._items[x.provenance_id]=x
    def get(self,pid:str)->ProvenanceActivity:return self._items[pid]
    def ancestors(self,pid:str)->tuple[str,...]:
        seen:set[str]=set(); stack=list(self.get(pid).parent_ids)
        while stack:
            cur=stack.pop()
            if cur in seen: continue
            seen.add(cur); stack.extend(self.get(cur).parent_ids)
        return tuple(sorted(seen))
