from __future__ import annotations


def zscore(value: float, mean: float, std: float) -> float:
    if std <= 0:
        raise ValueError("std must be positive")
    return (value - mean) / std


def is_anomaly(value: float, mean: float, std: float, threshold: float = 3.0) -> bool:
    return abs(zscore(value, mean, std)) >= threshold
