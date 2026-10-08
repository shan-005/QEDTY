from qedty.core.enums import EntityType
from qedty.core.hash import deterministic_id
from qedty.ontology.entities import Entity


def test_entity_contract():
    e = Entity(
        entity_id=deterministic_id("entity", "qedty", "satellite", "demo"),
        entity_type=EntityType.SATELLITE,
        canonical_name="Demo",
    )
    assert e.entity_id.startswith("entity:")
