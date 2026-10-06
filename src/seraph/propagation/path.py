from .models import PropagationEvent
def strongest(events:tuple[PropagationEvent,...])->tuple[PropagationEvent,...]:
    best:dict[str,PropagationEvent]={}
    for e in events:
        if e.entity_id not in best or e.impairment>best[e.entity_id].impairment: best[e.entity_id]=e
    return tuple(sorted(best.values(),key=lambda x:(x.depth,x.entity_id)))
