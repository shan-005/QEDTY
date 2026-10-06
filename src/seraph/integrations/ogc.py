from typing import Any

from seraph.spatial.jsonfg import feature
from seraph.spatial.models import Point


def jsonfg_for_entity(entity_id: str, name: str, point: Point) -> dict[str, Any]:
    return feature(entity_id, point, feature_type=name)
