from __future__ import annotations
def effective_capacity(base:float,substitutable_fraction:float,substitute_capacity:float)->float:
    return max(0.0,min(1.0,base+substitutable_fraction*substitute_capacity))
