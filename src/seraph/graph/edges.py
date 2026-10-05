from __future__ import annotations

from datetime import datetime

from seraph.core.time import in_window
from seraph.core.types import Relationship


def edge_is_valid_at(edge: Relationship, at: datetime | None) -> bool:
    if at is None:
        return True
    return in_window(at, edge.valid_from, edge.valid_to)
