from __future__ import annotations
from seraph.core.time import hours
from seraph.propagation.models import PropagationEvent
from seraph.scenarios.shocks import Shock
from .models import ContinuityPoint,ContinuityResult
from .thresholds import validate_threshold
class ContinuityEngine:
    def simulate(self,entity_id:str,shock:Shock,events:tuple[PropagationEvent,...],*,threshold:float=0.30)->ContinuityResult:
        validate_threshold(threshold); event=next((e for e in events if e.entity_id==entity_id),None); impairment=0 if event is None else event.impairment; cap=max(0,min(1,1-impairment)); duration=hours(shock.starts_at,shock.ends_at); below=duration if cap<threshold else 0.0
        return ContinuityResult(entity_id=entity_id,points=(ContinuityPoint(timestamp=shock.starts_at,capacity_fraction=cap),ContinuityPoint(timestamp=shock.ends_at,capacity_fraction=cap)),minimum_capacity_fraction=cap,time_below_threshold_hours=below,capacity_hours=duration*cap)
