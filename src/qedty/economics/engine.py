from __future__ import annotations

import json
from hashlib import sha256
from typing import TYPE_CHECKING

from .models import EconomicExposure, EconomicImpact

if TYPE_CHECKING:
    from qedty.continuity.models import ContinuityResult


class EconomicImpactEngine:
    def estimate(
        self,
        exposure: EconomicExposure,
        continuity: ContinuityResult,
        duration_hours: float,
        *,
        indirect_multiplier: float = 0.0,
        value_added_ratio: float | None = None,
    ) -> EconomicImpact:
        if duration_hours < 0 or indirect_multiplier < 0:
            raise ValueError("invalid duration/multiplier")
        duration_fraction = min(1.0, duration_hours / (exposure.reference_period_days * 24.0))
        loss_fraction = 1.0 - continuity.minimum_capacity_fraction
        direct = (
            exposure.reference_value_usd
            * exposure.exposed_fraction
            * loss_fraction
            * duration_fraction
            * exposure.pass_through
        )
        indirect = direct * indirect_multiplier
        ratio = exposure.value_added_ratio if value_added_ratio is None else value_added_ratio
        if not 0 <= ratio <= 1:
            raise ValueError("value_added_ratio must be in [0,1]")
        digest = sha256(
            json.dumps(
                {
                    "entity": exposure.entity_id,
                    "direct": direct,
                    "indirect": indirect,
                    "duration": duration_hours,
                },
                sort_keys=True,
                separators=(",", ":"),
            ).encode()
        ).hexdigest()
        return EconomicImpact(
            entity_id=exposure.entity_id,
            direct_loss_usd=direct,
            indirect_loss_usd=indirect,
            total_loss_usd=direct + indirect,
            value_added_loss_usd=(direct + indirect) * ratio,
            displaced_output_usd=direct + indirect,
            methodology="reference-exposure model with explicit indirect multiplier",
            assumptions=(
                "not an observed realized loss",
                "duration and pass-through are explicit assumptions",
                "indirect multiplier is caller-supplied",
            ),
            model_digest=digest,
        )
