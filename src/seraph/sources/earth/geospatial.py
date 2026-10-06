from dataclasses import dataclass
from seraph.spatial.models import BoundingBox,Point
@dataclass(frozen=True)
class HazardFootprint:
    hazard_id:str; bbox:BoundingBox; severity:float; observed_at:str; evidence_id:str
    def contains(self,p:Point)->bool:
        lon=p.longitude; lat=p.latitude; return lat>=self.bbox.south and lat<=self.bbox.north and ((self.bbox.west<=lon<=self.bbox.east) if self.bbox.west<=self.bbox.east else (lon>=self.bbox.west or lon<=self.bbox.east))
