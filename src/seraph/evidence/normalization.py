from __future__ import annotations
from dataclasses import dataclass
from typing import Any
@dataclass(frozen=True,slots=True)
class NormalizedRecord:
    source_name:str; record_id:str; attributes:dict[str,Any]
def normalize_record(source_name:str,record_id:str,attributes:dict[str,Any])->NormalizedRecord:
    clean={str(k):v for k,v in attributes.items() if str(k).strip()}
    return NormalizedRecord(source_name,record_id,clean)
