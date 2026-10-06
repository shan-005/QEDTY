from dataclasses import dataclass


@dataclass(frozen=True)
class SnaMeasure:
    concept: str
    value: float
    currency: str
    period: str
    source_uri: str
