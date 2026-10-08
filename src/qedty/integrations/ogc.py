from typing import Any

from qedty.spatial.jsonfg import feature
from qedty.spatial.models import Point


def jsonfg_for_entity(entity_id: str, name: str, point: Point) -> dict[str, Any]:
    return feature(entity_id, point, feature_type=name)
