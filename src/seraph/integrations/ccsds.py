from seraph.sources.space.ccsds import OrbitRecord, parse_omm_kvn


def parse_orbit(text: str) -> OrbitRecord:
    return parse_omm_kvn(text)
