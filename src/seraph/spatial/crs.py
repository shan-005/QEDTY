DEFAULT_CRS = "EPSG:4326"


def validate_crs(crs: str) -> str:
    value = crs.strip().upper()
    if not value or ":" not in value:
        raise ValueError("CRS must use an authority:code form")
    return value
