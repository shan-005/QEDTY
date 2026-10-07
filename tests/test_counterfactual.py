from datetime import UTC, datetime, timedelta

from seraph.continuity.engine import ContinuityEngine
from seraph.core.enums import EpistemicStatus, EventType, InterventionType
from seraph.propagation.models import PropagationEvent
from seraph.scenarios.models import Intervention
from seraph.scenarios.shocks import Shock


class EmptyGraph:
    def edges_from(self, entity_id: str, at=None):
        return ()


def test_counterfactual_gain_with_direct_propagation_event():
    start = datetime(2026, 1, 1, tzinfo=UTC)
    end = start + timedelta(hours=2)
    shock = Shock(
        shock_id="x",
        name="x",
        event_type=EventType.OUTAGE,
        source_entity_id="a",
        starts_at=start,
        ends_at=end,
        severity=0.5,
    )
    event = PropagationEvent(
        entity_id="a",
        impairment=0.5,
        depth=0,
        path_entity_ids=("a",),
        path_relationship_ids=(),
        effective_at=start,
        status=EpistemicStatus.MODELED,
    )

    class StubPropagation:
        def __init__(self):
            self.called = 0

        def propagate(self, shock, **kwargs):
            self.called += 1
            if kwargs:
                return (
                    event.model_copy(
                        update={"impairment": 0.2, "status": EpistemicStatus.COUNTERFACTUAL}
                    ),
                )
            return (event,)

    propagation = StubPropagation()
    from seraph.counterfactual.engine import CounterfactualEngine

    intervention = Intervention(
        intervention_id="i",
        name="i",
        intervention_type=InterventionType.HARDENING,
        cost_usd=1.0,
        protected_entity_ids=("a",),
        transmission_reduction=0.6,
    )
    result = CounterfactualEngine(propagation, ContinuityEngine()).compare(shock, "a", intervention)
    assert result.continuity_gain > 0
    assert result.digest == result.digest
