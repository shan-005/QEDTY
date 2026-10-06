from __future__ import annotations
from pathlib import Path
import hashlib,os
class EvidenceFileStore:
    def __init__(self,root:str|Path): self.root=Path(root); self.root.mkdir(parents=True,exist_ok=True)
    def put(self,payload:bytes)->str:
        digest=hashlib.sha256(payload).hexdigest(); target=self.root/digest[:2]/digest[2:]
        target.parent.mkdir(parents=True,exist_ok=True)
        if target.exists() and target.read_bytes()!=payload: raise ValueError("content-addressed collision")
        if not target.exists():
            tmp=target.with_suffix(".tmp"); tmp.write_bytes(payload); os.replace(tmp,target)
        return digest
    def get(self,digest:str)->bytes:
        target=self.root/digest[:2]/digest[2:]
        payload=target.read_bytes()
        if hashlib.sha256(payload).hexdigest()!=digest: raise ValueError("evidence digest mismatch")
        return payload
