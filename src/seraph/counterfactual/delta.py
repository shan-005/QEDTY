from dataclasses import dataclass
@dataclass(frozen=True)
class Delta:
    baseline:float; counterfactual:float
    @property
    def change(self)->float:return self.counterfactual-self.baseline
