from __future__ import annotations
import random
def deterministic_uniform(seed:int,n:int)->tuple[float,...]:
    if n<0: raise ValueError("n must be non-negative")
    rng=random.Random(seed); return tuple(rng.random() for _ in range(n))
