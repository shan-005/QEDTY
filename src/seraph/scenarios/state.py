from __future__ import annotations
from dataclasses import dataclass,field
@dataclass
class ScenarioState:
    capacities:dict[str,float]=field(default_factory=dict); attributes:dict[str,dict[str,object]]=field(default_factory=dict)
    def copy(self)->"ScenarioState":return ScenarioState(dict(self.capacities),{k:dict(v) for k,v in self.attributes.items()})
