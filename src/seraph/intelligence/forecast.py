from __future__ import annotations
from dataclasses import dataclass
from .anomaly import zscore
@dataclass(frozen=True)
class Forecast:
    estimate:float; lower:float; upper:float; horizon:str

def persistence(value:float,uncertainty:float,horizon:str)->Forecast:
    if uncertainty<0: raise ValueError("uncertainty negative")
    return Forecast(value,max(0,value-uncertainty),value+uncertainty,horizon)
