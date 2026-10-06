from __future__ import annotations
from typing import Any
from .models import Geometry,Point
def point_feature(entity_id:str,point:Point,properties:dict[str,Any]|None=None)->dict[str,Any]:
    return {"type":"Feature","id":entity_id,"geometry":{"type":"Point","coordinates":[point.longitude,point.latitude]},"properties":properties or {}}
