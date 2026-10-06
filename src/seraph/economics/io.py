from __future__ import annotations
from dataclasses import dataclass
@dataclass(frozen=True)
class IOModel:
    sectors:tuple[str,...]
    technical_coefficients:tuple[tuple[float,...],...]
    def validate(self):
        n=len(self.sectors)
        if len(self.technical_coefficients)!=n or any(len(r)!=n for r in self.technical_coefficients): raise ValueError("IO matrix dimension mismatch")
        if any(x<0 for r in self.technical_coefficients for x in r): raise ValueError("IO coefficients must be non-negative")
    def total_output(self,final_demand:tuple[float,...])->tuple[float,...]:
        self.validate(); n=len(self.sectors)
        if len(final_demand)!=n: raise ValueError("final demand mismatch")
        # Fixed-point Leontief solve with bounded deterministic iteration; explicit model semantics.
        x=list(final_demand)
        for _ in range(200):
            nx=[final_demand[i]+sum(self.technical_coefficients[i][j]*x[j] for j in range(n)) for i in range(n)]
            if max(abs(nx[i]-x[i]) for i in range(n))<1e-10:return tuple(nx)
            x=nx
        raise ValueError("IO model did not converge; spectral radius may be >= 1")
