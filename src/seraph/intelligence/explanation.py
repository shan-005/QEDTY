from __future__ import annotations
from dataclasses import dataclass
@dataclass(frozen=True)
class Explanation:
    statement:str; inputs:tuple[str,...]; method:str; caveats:tuple[str,...]
def explain(statement:str,inputs:list[str],method:str,caveats:list[str])->Explanation:return Explanation(statement,tuple(sorted(inputs)),method,tuple(caveats))
