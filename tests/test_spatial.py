from seraph.spatial.models import BoundingBox, Point
from seraph.spatial.operations import point_in_bbox


def test_bbox():
    assert point_in_bbox(
        Point(latitude=17.4, longitude=78.4), BoundingBox(west=78, south=17, east=79, north=18)
    )
