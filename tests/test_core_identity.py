from seraph.core.enums import EntityType
from seraph.core.hash import deterministic_id


def test_identity_deterministic():
    assert deterministic_id(
        "entity", "seraph", EntityType.SATELLITE.value, "demo"
    ) == deterministic_id("entity", "seraph", "satellite", "demo")
