from __future__ import annotations
from dataclasses import dataclass
from typing import Generic, TypeVar
T=TypeVar("T")
@dataclass(frozen=True,slots=True)
class ContractResult(Generic[T]):
    value:T
    epistemic_state:str
    evidence_ids:tuple[str,...]=()
    provenance_ids:tuple[str,...]=()
    assumptions:tuple[str,...]=()
