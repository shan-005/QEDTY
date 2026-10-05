from __future__ import annotations

from datetime import datetime

from seraph.core.time import ensure_utc
from seraph.core.types import Relationship


def relationship_sort_key(edge: Relationship) -> tuple[str, str, str, str]:
    return (edge.source.entity_id, edge.target.entity_id, edge.relationship_type.value, edge.relationship_id)


def overlaps_window(edge: Relationship, start: datetime, end: datetime) -> bool:
    start_utc, end_utc = ensure_utc(start), ensure_utc(end)
    edge_start = ensure_utc(edge.valid_from) if edge.valid_from else datetime.min.replace(tzinfo=start_utc.tzinfo)
    edge_end = ensure_utc(edge.valid_to) if edge.valid_to else datetime.max.replace(tzinfo=end_utc.tzinfo)
    return edge_start < end_utc and start_utc < edge_end
