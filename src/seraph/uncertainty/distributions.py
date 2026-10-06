from dataclasses import dataclass
from math import sqrt,pi,exp
@dataclass(frozen=True)
class Normal:
    mean:float; std:float
    def pdf(self,x:float)->float:
        if self.std<=0: raise ValueError("std must be positive")
        z=(x-self.mean)/self.std; return exp(-.5*z*z)/(self.std*sqrt(2*pi))
