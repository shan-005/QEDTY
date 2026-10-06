from seraph.integrations.ogc import jsonfg_for_entity
from seraph.spatial.models import Point


def test_jsonfg():
    x = jsonfg_for_entity("e", "Satellite", Point(latitude=1, longitude=2))
    assert x["geometry"]["coordinates"] == [2, 1]
