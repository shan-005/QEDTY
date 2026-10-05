from __future__ import annotations

from seraph.pci.entities.models import Entity


def node_key(entity: Entity) -> str:
    return entity.entity_id
