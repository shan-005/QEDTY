from seraph.core.enums import EntityType
from seraph.core.hash import deterministic_id
from seraph.ontology.entities import Entity


def test_entity_contract():
    e = Entity(
        entity_id=deterministic_id("entity", "seraph", "satellite", "demo"),
        entity_type=EntityType.SATELLITE,
        canonical_name="Demo",
    )
    assert e.entity_id.startswith("entity:")
