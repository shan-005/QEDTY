from datetime import UTC, datetime, timedelta

from seraph.continuity.engine import ContinuityEngine
from seraph.core.enums import EpistemicStatus, EventType
from seraph.propagation.models import PropagationEvent
from seraph.scenarios.shocks import Shock


def test_capacity():
    s = datetime(2026, 1, 1, tzinfo=UTC)
    e = s + timedelta(hours=2)
    sh = Shock(
        shock_id="x",
        name="x",
        event_type=EventType.OUTAGE,
        source_entity_id="a",
        starts_at=s,
        ends_at=e,
        severity=0.5,
    )
    ev = (
        PropagationEvent(
            entity_id="a",
            impairment=0.5,
            depth=0,
            path_entity_ids=("a",),
            path_relationship_ids=(),
            effective_at=s,
            status=EpistemicStatus.MODELED,
        ),
    )
    c = ContinuityEngine().simulate("a", sh, ev)
    assert c.minimum_capacity_fraction == 0.5
