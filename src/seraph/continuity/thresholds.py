def validate_threshold(value:float)->float:
    if not 0<value<1: raise ValueError("threshold must be in (0,1)")
    return value
