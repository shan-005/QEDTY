from .models import BoundingBox, Point


def point_in_bbox(point: Point, bbox: BoundingBox) -> bool:
    lon = point.longitude
    lat = point.latitude
    lon_ok = (
        (bbox.west <= lon <= bbox.east)
        if bbox.west <= bbox.east
        else (lon >= bbox.west or lon <= bbox.east)
    )
    return lat >= bbox.south and lat <= bbox.north and lon_ok
