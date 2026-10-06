from __future__ import annotations
from math import atan2, cos, radians, sin, sqrt

def haversine_km(lat1:float,lon1:float,lat2:float,lon2:float)->float:
    phi1,phi2=radians(lat1),radians(lat2); dphi=radians(lat2-lat1); dl=radians(lon2-lon1)
    a=sin(dphi/2)**2+cos(phi1)*cos(phi2)*sin(dl/2)**2
    return 6371.0088*2*atan2(sqrt(a),sqrt(max(0.0,1-a)))
