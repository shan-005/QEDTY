from datetime import datetime
from seraph.ontology.relations import Relationship
from seraph.temporal.intervals import contains
def active_relationships(edges:tuple[Relationship,...],at:datetime)->tuple[Relationship,...]:
    return tuple(e for e in edges if e.valid_from is None or (e.valid_to is None and at>=e.valid_from) or (e.valid_to is not None and contains(at,e.valid_from,e.valid_to)))
