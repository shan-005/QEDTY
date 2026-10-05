from __future__ import annotations

from seraph.continuity.models import ContinuityResult
from seraph.economics.models import EconomicExposure, EconomicLoss


class EconomicLossEngine:
    def estimate(self, *, exposure: EconomicExposure, continuity: ContinuityResult, duration_hours: float) -> EconomicLoss:
        if duration_hours < 0.0:
            raise ValueError("duration_hours must be non-negative")
        duration_fraction = min(1.0, duration_hours / (exposure.reference_period_days * 24.0))
        service_loss_fraction = max(0.0, 1.0 - continuity.minimum_capacity_fraction)
        loss = exposure.reference_value_usd * exposure.exposed_fraction * service_loss_fraction * duration_fraction * exposure.transmission_elasticity
        return EconomicLoss(
            entity_id=exposure.entity_id,
            modeled_loss_usd=loss,
            reference_exposure_usd=exposure.reference_value_usd,
            assumptions=(
                "linear reference-period exposure",
                "minimum capacity is used as the disruption proxy",
                "duration fraction is capped at one reference period",
                "result is modeled and not a realized-loss observation",
            ),
        )
