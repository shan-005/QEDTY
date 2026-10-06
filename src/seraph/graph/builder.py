from __future__ import annotations
from seraph.ontology.world import WorldModel
from .store import TemporalGraph
def from_world(world:WorldModel)->TemporalGraph:
    g=TemporalGraph()
    for e in world.entities.values(): g.add_entity(e)
    for r in world.relationships.values(): g.add_relationship(r)
    return g
