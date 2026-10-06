from datetime import datetime
from seraph.core.time import ensure_utc
def overlaps(a_start:datetime,a_end:datetime,b_start:datetime,b_end:datetime)->bool:
    a,b,c,d=map(ensure_utc,(a_start,a_end,b_start,b_end)); return a<d and c<b
def contains(instant:datetime,start:datetime,end:datetime)->bool:
    t,s,e=map(ensure_utc,(instant,start,end)); return s<=t<e
