from __future__ import annotations
import hashlib
from datetime import UTC,datetime
from .models import EvidenceRecord
from .licensing import DEFAULT_UNKNOWN
from seraph.core.hash import deterministic_id
class EvidenceAcquirer:
    def record_bytes(self,source_name:str,source_uri:str,payload:bytes,*,content_type:str="application/octet-stream",metadata:dict[str,str]|None=None)->EvidenceRecord:
        digest=hashlib.sha256(payload).hexdigest(); now=datetime.now(UTC)
        return EvidenceRecord(evidence_id=deterministic_id("evidence",source_uri,digest,None),source_name=source_name,source_uri=source_uri,retrieved_at=now,content_sha256=digest,content_type=content_type,payload_size_bytes=len(payload),license_policy=DEFAULT_UNKNOWN, metadata=metadata or {})
