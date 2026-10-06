from __future__ import annotations
from dataclasses import dataclass,field
from datetime import datetime
@dataclass
class Timeline:
    _points:dict[datetime,object]=field(default_factory=dict)
    def put(self,at:datetime,value:object)->None:self._points[at]=value
    def at_or_before(self,at:datetime)->object|None:
        keys=[k for k in self._points if k<=at]
        return self._points[max(keys)] if keys else None
    def ordered(self)->tuple[tuple[datetime,object],...]:return tuple(sorted(self._points.items()))
