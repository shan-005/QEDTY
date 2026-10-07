from .models import Interval


def widen(interval: Interval, factor: float) -> Interval:
    if factor < 0:
        raise ValueError("negative factor")
    half = (interval.upper - interval.lower) * factor / 2
    return Interval(
        lower=interval.estimate - half,
        estimate=interval.estimate,
        upper=interval.estimate + half,
        confidence_level=interval.confidence_level,
        method=interval.method + ":widened",
    )


def intersect(a: Interval, b: Interval) -> Interval:
    lo = max(a.lower, b.lower)
    hi = min(a.upper, b.upper)
    if lo > hi:
        raise ValueError("intervals do not intersect")
    est = min(max((a.estimate + b.estimate) / 2, lo), hi)
    return Interval(
        lower=lo,
        estimate=est,
        upper=hi,
        confidence_level=min(a.confidence_level, b.confidence_level),
        method="interval:intersection",
    )
