from __future__ import annotations
from dataclasses import dataclass,field
from typing import Any
@dataclass
class PipelineContext:
    run_id:str; artifacts:dict[str,Any]=field(default_factory=dict); warnings:list[str]=field(default_factory=list)
