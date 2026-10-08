"""Optional Apache Arrow interchange for graph batches."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from .schema import CAPABILITIES, KEY

if TYPE_CHECKING:
    from .store import TemporalGraph


def to_arrow_tables(graph: TemporalGraph) -> tuple[Any, Any]:
    """Return ``(vertices, relationships)`` as PyArrow tables.

    PyArrow is deliberately optional: the graph reference implementation does
    not require it, while the exported schema is stable enough for a future
    Rust/Arrow data plane.
    """

    try:
        import pyarrow as pa  # type: ignore[import-untyped]
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("pyarrow is required for Arrow graph interchange") from exc

    vertices = pa.table(
        {
            "entity_id": [entity.entity_id for entity in graph.entities()],
            "entity_type": [entity.entity_type.value for entity in graph.entities()],
            "canonical_name": [entity.canonical_name for entity in graph.entities()],
            "latitude": [entity.latitude for entity in graph.entities()],
            "longitude": [entity.longitude for entity in graph.entities()],
            "epistemic_status": [entity.epistemic_status.value for entity in graph.entities()],
            "confidence": [entity.confidence for entity in graph.entities()],
            "properties_json": [
                json.dumps(entity.properties, sort_keys=True, separators=(",", ":"))
                for entity in graph.entities()
            ],
        }
    )
    relationships = pa.table(
        {
            "relationship_id": [r.relationship_id for r in graph.relationships()],
            "source_entity_id": [r.source.entity_id for r in graph.relationships()],
            "target_entity_id": [r.target.entity_id for r in graph.relationships()],
            "relationship_type": [r.relationship_type.value for r in graph.relationships()],
            "valid_from": [r.valid_from for r in graph.relationships()],
            "valid_to": [r.valid_to for r in graph.relationships()],
            "strength": [r.strength for r in graph.relationships()],
            "capacity_fraction": [r.capacity_fraction for r in graph.relationships()],
            "epistemic_status": [r.epistemic_status.value for r in graph.relationships()],
            "attributes_json": [
                json.dumps(r.attributes, sort_keys=True, separators=(",", ":"))
                for r in graph.relationships()
            ],
        }
    )
    metadata = {
        b"qedty.graph.schema": KEY.encode(),
        b"qedty.graph.capabilities": json.dumps(CAPABILITIES).encode(),
    }
    vertices = vertices.replace_schema_metadata({**(vertices.schema.metadata or {}), **metadata})
    relationships = relationships.replace_schema_metadata(
        {**(relationships.schema.metadata or {}), **metadata}
    )
    return vertices, relationships
