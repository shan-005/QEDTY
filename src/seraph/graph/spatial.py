from seraph.spatial.models import Point
from seraph.core.geometry import haversine_km
def spatial_distance(a:Point,b:Point)->float:return haversine_km(a.latitude,a.longitude,b.latitude,b.longitude)
