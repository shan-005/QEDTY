from __future__ import annotations
from collections import deque
from .models import PropagationEvent
from .rules import PropagationRule
from seraph.core.enums import EpistemicStatus
from seraph.graph.store import TemporalGraph
from seraph.scenarios.shocks import Shock
class PropagationEngine:
    def __init__(self,graph:TemporalGraph,rule:PropagationRule|None=None): self.graph=graph; self.rule=rule or PropagationRule(); self.rule.validate()
    def propagate(self,shock:Shock,*,transmission_reduction:dict[str,float]|None=None,capacity_gain:dict[str,float]|None=None)->tuple[PropagationEvent,...]:
        reductions=transmission_reduction or {}; gains=capacity_gain or {}; at=shock.starts_at; first=PropagationEvent(entity_id=shock.source_entity_id,impairment=shock.severity*(1-reductions.get(shock.source_entity_id,0)),depth=0,path_entity_ids=(shock.source_entity_id,),path_relationship_ids=(),effective_at=at,status=EpistemicStatus.COUNTERFACTUAL if reductions or gains else EpistemicStatus.MODELED)
        q=deque([first]); best={first.entity_id:first.impairment}; out=[first]
        while q:
            cur=q.popleft()
            if cur.depth>=self.rule.max_hops or cur.impairment<self.rule.minimum_impairment: continue
            for edge in self.graph.edges_from(cur.entity_id,at=at):
                nxt=cur.impairment*edge.strength*edge.capacity_fraction*(1-reductions.get(edge.target.entity_id,0)); nxt*=1-gains.get(edge.target.entity_id,0)
                if nxt<self.rule.minimum_impairment or nxt<=best.get(edge.target.entity_id,-1): continue
                event=PropagationEvent(entity_id=edge.target.entity_id,impairment=min(1,nxt),depth=cur.depth+1,path_entity_ids=cur.path_entity_ids+(edge.target.entity_id,),path_relationship_ids=cur.path_relationship_ids+(edge.relationship_id,),effective_at=at,status=first.status); best[event.entity_id]=event.impairment; out.append(event); q.append(event)
        return tuple(out)
