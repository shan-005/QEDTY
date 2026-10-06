from datetime import datetime

from seraph.ontology.relations import Relationship


def active(edge: Relationship, at: datetime) -> bool:
    return not (
        (edge.valid_from and at < edge.valid_from) or (edge.valid_to and at >= edge.valid_to)
    )
