from dataclasses import dataclass


@dataclass(frozen=True)
class PropagationRule:
    minimum_impairment: float = 0.01
    max_hops: int = 32

    def validate(self) -> None:
        if not 0 < self.minimum_impairment <= 1 or self.max_hops < 0:
            raise ValueError("invalid propagation rule")
