from qedty.integrations.ogc import jsonfg_for_entity
from qedty.spatial.models import Point


def test_jsonfg():
    x = jsonfg_for_entity("e", "Satellite", Point(latitude=1, longitude=2))
    assert x["geometry"]["coordinates"] == [2, 1]
