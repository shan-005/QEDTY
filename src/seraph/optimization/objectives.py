def efficiency(gain: float, cost_usd: float) -> float:
    if gain < 0 or cost_usd < 0:
        raise ValueError("invalid objective inputs")
    return gain / (cost_usd / 1_000_000) if cost_usd else gain
