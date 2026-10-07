from datetime import UTC, datetime, timedelta

from seraph.continuity.engine import ContinuityEngine
from seraph.core.enums import EpistemicStatus, EventType
from seraph.propagation.models import PropagationEvent
from seraph.scenarios.shocks import Shock


def shock():
    s = datetime(2026, 1, 1, tzinfo=UTC)
    return Shock(
        shock_id="x",
        name="x",
        event_type=EventType.OUTAGE,
        source_entity_id="a",
        starts_at=s,
        ends_at=s + timedelta(hours=2),
        severity=0.5,
    )


def event():
    s = datetime(2026, 1, 1, tzinfo=UTC)
    return PropagationEvent(
        entity_id="a",
        impairment=0.5,
        depth=0,
        path_entity_ids=("a",),
        path_relationship_ids=(),
        effective_at=s,
        status=EpistemicStatus.MODELED,
    )


def test_legacy_capacity():
    c = ContinuityEngine().simulate("a", shock(), (event(),))
    assert c.minimum_capacity_fraction == 0.5


def test_recovery_curve_and_resilience():
    c = ContinuityEngine().simulate(
        "a", shock(), (event(),), recovery_rate=0.001, recovery_horizon_hours=48
    )
    assert c.capacity_hours > 0
    assert 0 < c.resilience_index < 1
    assert c.points[-1].phase == "recovery"


def test_threshold_and_digest_are_deterministic():
    c = ContinuityEngine().simulate("a", shock(), (event(),), threshold=0.6)
    assert c.time_below_threshold_hours > 0
    assert c.digest == c.digest
