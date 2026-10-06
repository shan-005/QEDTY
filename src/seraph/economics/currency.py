def usd(value:float)->float:
    if value<0: raise ValueError("negative monetary amount")
    return round(value,2)
