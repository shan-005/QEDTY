def robust_floor(scores:list[float])->float:
    if not scores:return 0.0
    return min(scores)
