from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from seraph.core import CORE_VERSION
from seraph.core.contracts import ContractResult
from seraph.core.enums import EntityType, EpistemicStatus
from seraph.core.hash import deterministic_id
from seraph.core.types import (
    AssertionRef,
    EntityRef,
    ExternalIdentifier,
    TimeWindow,
)
from seraph.core.units import Quantity


def test_reference_surface_is_frozen_and_strict() -> None:
    entity = EntityRef(entity_id="entity:demo")
    assert entity.entity_id == "entity:demo"

    identifier = ExternalIdentifier(namespace="  nasa  ", value="  NORAD:1  ")
    assert identifier.namespace == "nasa"
    assert identifier.value == "NORAD:1"

    assertion = AssertionRef(assertion_id="assertion:1", status=EpistemicStatus.OBSERVED)
    assert assertion.status is EpistemicStatus.OBSERVED


def test_time_window_is_utc_half_open() -> None:
    local = datetime(2026, 10, 6, 5, 30, tzinfo=UTC) + timedelta(hours=1)
    window = TimeWindow(start=local, end=local + timedelta(hours=1))
    assert window.contains(local)
    assert not window.contains(window.end)


def test_quantity_contract_is_decimal_and_dimension_checked() -> None:
    q = Quantity(value=Decimal("2.5"), unit="km")
    assert q.to("m").value == Decimal("2500.0")


def test_core_profiles_are_explicit() -> None:
    assert CORE_VERSION.core_contract_version == "1.0.0"
    assert CORE_VERSION.identity_hash_algorithm == "SHA-256"
    assert "UCUM=2.2" in CORE_VERSION.unit_profile
    assert CORE_VERSION.jcs_profile == "RFC8785"


def test_identity_is_unchanged_for_existing_reference_formula() -> None:
    assert deterministic_id("entity", "seraph", EntityType.SATELLITE.value, "demo") == (
        "entity:e24bb28cec2205c94c215c07e8767df2"
    )


def test_contract_result_is_json_shape_compatible() -> None:
    result = ContractResult(
        value={"loss": 100.0},
        epistemic_state=EpistemicStatus.MODELED,
        evidence_ids=("e2", "e1", "e1"),
        provenance_ids=("p2", "p1"),
    )
    assert result.to_dict()["evidence_ids"] == ["e1", "e2"]
