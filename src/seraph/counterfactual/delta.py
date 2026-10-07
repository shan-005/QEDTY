from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Delta:
    baseline: float
    counterfactual: float

    @property
    def change(self) -> float:
        return self.counterfactual - self.baseline

    @property
    def absolute_improvement(self) -> float:
        return self.counterfactual - self.baseline

    @property
    def relative_change(self) -> float:
        if self.baseline == 0:
            return 0.0 if self.counterfactual == 0 else float("inf")
        return self.change / abs(self.baseline)
