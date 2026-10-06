from __future__ import annotations
from .models import EconomicExposure,EconomicImpact
from seraph.continuity.models import ContinuityResult
class EconomicImpactEngine:
    def estimate(self,exposure:EconomicExposure,continuity:ContinuityResult,duration_hours:float,*,indirect_multiplier:float=0.0)->EconomicImpact:
        if duration_hours<0 or indirect_multiplier<0: raise ValueError("invalid duration/multiplier")
        duration_fraction=min(1,duration_hours/(exposure.reference_period_days*24)); direct=exposure.reference_value_usd*exposure.exposed_fraction*(1-continuity.minimum_capacity_fraction)*duration_fraction*exposure.pass_through; indirect=direct*indirect_multiplier
        return EconomicImpact(entity_id=exposure.entity_id,direct_loss_usd=direct,indirect_loss_usd=indirect,total_loss_usd=direct+indirect,methodology="reference-exposure model",assumptions=("not an observed realized loss","indirect multiplier is externally supplied or scenario-assumed"))
