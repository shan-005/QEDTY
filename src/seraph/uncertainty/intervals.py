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
