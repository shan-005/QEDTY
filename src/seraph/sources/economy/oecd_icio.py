from dataclasses import dataclass


@dataclass(frozen=True)
class ICIOFlow:
    reporter: str
    partner: str
    industry: str
    value_usd: float
    vintage: str
    source_uri: str
