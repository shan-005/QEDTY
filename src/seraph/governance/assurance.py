from dataclasses import dataclass
@dataclass(frozen=True)
class AssuranceRecord:
    scope:str; passed:bool; evidence:tuple[str,...]; limitations:tuple[str,...]
