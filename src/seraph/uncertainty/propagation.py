from .models import Interval
def add(a:Interval,b:Interval)->Interval:return Interval(lower=a.lower+b.lower,estimate=a.estimate+b.estimate,upper=a.upper+b.upper,confidence_level=min(a.confidence_level,b.confidence_level),method="interval-arithmetic:add")
def multiply_nonnegative(a:Interval,b:Interval)->Interval:return Interval(lower=a.lower*b.lower,estimate=a.estimate*b.estimate,upper=a.upper*b.upper,confidence_level=min(a.confidence_level,b.confidence_level),method="interval-arithmetic:multiply")
