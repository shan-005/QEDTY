from dataclasses import dataclass


@dataclass(frozen=True)
class Assumption:
    name: str
    value: str
    source: str | None = None
