from qedty.core.enums import EntityType
from qedty.core.hash import deterministic_id


def test_identity_deterministic():
    assert deterministic_id(
        "entity", "qedty", EntityType.SATELLITE.value, "demo"
    ) == deterministic_id("entity", "qedty", "satellite", "demo")
