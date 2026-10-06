from __future__ import annotations
from .models import EvidenceRecord
class EvidenceRegistry:
    def __init__(self): self._items:dict[str,EvidenceRecord]={}
    def add(self,x:EvidenceRecord)->None:
        prev=self._items.get(x.evidence_id)
        if prev and prev!=x: raise ValueError(f"evidence collision: {x.evidence_id}")
        self._items[x.evidence_id]=x
    def get(self,evidence_id:str)->EvidenceRecord:return self._items[evidence_id]
    def all(self)->tuple[EvidenceRecord,...]:return tuple(self._items[k] for k in sorted(self._items))
