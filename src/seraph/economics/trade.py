from dataclasses import dataclass


@dataclass(frozen=True)
class TradeFlow:
    exporter: str
    importer: str
    sector: str
    value_usd: float

    def validate(self) -> None:
        if self.value_usd < 0:
            raise ValueError("trade value must be non-negative")
