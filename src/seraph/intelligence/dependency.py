from seraph.graph.store import TemporalGraph
def critical_upstreams(graph:TemporalGraph,entity_id:str)->tuple[str,...]:return tuple(sorted(e.entity_id for e in graph.neighbors(entity_id,direction="in")))
