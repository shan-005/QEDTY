from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from seraph.core.enums import EventType, InterventionType
from seraph.scenarios.diff import diff, state_diff
from seraph.scenarios.engine import ScenarioEngine, apply_scenario, guard_matches
from seraph.scenarios.models import (
    ComparisonOperator,
    Intervention,
    PatchOperation,
    Scenario,
    ScenarioBranch,
    ScenarioGuard,
    ScenarioKind,
    ScenarioStatus,
    ScenarioTree,
    Shock,
    StatePatch,
)
from seraph.scenarios.shocks import active_shocks, normalize_shocks, shock_targets
from seraph.scenarios.state import ScenarioState

BASE = "world:demo"
T0 = datetime(2026, 1, 1, tzinfo=UTC)
T1 = T0 + timedelta(hours=6)


def test_legacy_capacity_parameter_and_override_contract() -> None:
    base = ScenarioState(capacities={"a": 1.0, "b": 0.5})
    scenario = Scenario(
        scenario_id="s1",
        name="stress",
        base_world_digest=BASE,
        parameters={"a": 0.7},
        capacities={"b": 0.9},
    )
    out = apply_scenario(base, scenario)
    assert out.capacities == {"a": 0.7, "b": 0.9}
    assert base.capacities["a"] == 1.0


def test_explicit_state_patches() -> None:
    state = ScenarioState(
        capacities={"a": 0.5},
        attributes={"a": {"mode": "normal", "load": 2.0}},
    )
    patches = (
        StatePatch(entity_id="a", path="capacity", operation=PatchOperation.ADD, value=0.2),
        StatePatch(
            entity_id="a",
            path="attributes.mode",
            operation=PatchOperation.SET,
            value="stress",
        ),
        StatePatch(
            entity_id="a",
            path="attributes.load",
            operation=PatchOperation.MULTIPLY,
            value=3.0,
        ),
    )
    state.apply_patches(patches)
    assert state.capacities["a"] == 0.7
    assert state.attributes["a"] == {"mode": "stress", "load": 6.0}


def test_shock_requires_explicit_consequence() -> None:
    shock = Shock(
        shock_id="s",
        name="hazard",
        event_type=EventType.NATURAL_HAZARD,
        source_entity_id="a",
        starts_at=T0,
        ends_at=T1,
        severity=1.0,
    )
    out = apply_scenario(
        ScenarioState(capacities={"a": 1.0}),
        Scenario(
            scenario_id="scenario",
            name="x",
            base_world_digest=BASE,
            shocks=(shock,),
        ),
        at=T0,
    )
    assert out.capacities["a"] == 1.0
    assert out.active_shock_ids == ("s",)


def test_shock_explicit_capacity_multiplier() -> None:
    shock = Shock(
        shock_id="s",
        name="outage",
        event_type=EventType.OUTAGE,
        source_entity_id="a",
        starts_at=T0,
        ends_at=T1,
        severity=0.8,
        capacity_multipliers={"a": 0.25, "b": 0.5},
    )
    scenario = Scenario(scenario_id="scenario", name="x", base_world_digest=BASE, shocks=(shock,))
    out = apply_scenario(ScenarioState(capacities={"a": 1.0, "b": 0.8}), scenario, at=T0)
    assert out.capacities["a"] == 0.25
    assert out.capacities["b"] == 0.4


def test_intervention_materializes_capacity_and_transmission_effects() -> None:
    intervention = Intervention(
        intervention_id="i",
        name="backup",
        intervention_type=InterventionType.BACKUP_SERVICE,
        cost_usd=10.0,
        protected_entity_ids=("a",),
        transmission_reduction=0.2,
        capacity_gain=0.1,
    )
    scenario = Scenario(
        scenario_id="scenario", name="x", base_world_digest=BASE, interventions=(intervention,)
    )
    out = apply_scenario(ScenarioState(capacities={"a": 0.5}), scenario)
    assert out.capacities["a"] == pytest.approx(0.6)
    assert out.transmission_reductions == {"a": 0.2}
    assert out.applied_intervention_ids == ("i",)


def test_intervention_activation_window() -> None:
    intervention = Intervention(
        intervention_id="i",
        name="future",
        intervention_type=InterventionType.HARDENING,
        cost_usd=1.0,
        protected_entity_ids=("a",),
        capacity_gain=0.2,
        activation_at=T1,
    )
    scenario = Scenario(
        scenario_id="scenario", name="x", base_world_digest=BASE, interventions=(intervention,)
    )
    assert (
        apply_scenario(ScenarioState(capacities={"a": 1.0}), scenario, at=T0).capacities["a"] == 1.0
    )
    assert (
        apply_scenario(ScenarioState(capacities={"a": 1.0}), scenario, at=T1).capacities["a"] == 1.0
    )
    assert apply_scenario(ScenarioState(capacities={"a": 0.5}), scenario, at=T1).capacities[
        "a"
    ] == pytest.approx(0.7)


def test_state_digest_and_diff_are_deterministic() -> None:
    a = ScenarioState(capacities={"b": 0.5, "a": 1.0}, attributes={"a": {"x": 1}})
    b = ScenarioState(capacities={"a": 0.8, "b": 0.5}, attributes={"a": {"x": 2}})
    assert (
        a.digest
        == ScenarioState(capacities={"a": 1.0, "b": 0.5}, attributes={"a": {"x": 1}}).digest
    )
    delta = state_diff(a, b)
    assert delta.changed_entities == ("a",)
    assert delta.capacity_delta["a"] == pytest.approx(-0.2)
    assert delta.attribute_changes["a"]["x"] == {"before": 1, "after": 2}


def test_scenario_diff_preserves_legacy_surface() -> None:
    a = Scenario(scenario_id="a", name="a", base_world_digest=BASE, capacities={"x": 0.4})
    b = Scenario(scenario_id="b", name="b", base_world_digest=BASE, capacities={"x": 0.7, "y": 0.2})
    delta = diff(a, b)
    assert delta.changed_entities == ("x", "y")
    assert delta.capacity_delta["x"] == pytest.approx(0.3)
    assert delta.capacity_delta["y"] == pytest.approx(0.2)


def test_scenario_tree_guards() -> None:
    root = Scenario(
        scenario_id="root", name="root", base_world_digest=BASE, status=ScenarioStatus.VALIDATED
    )
    high = Scenario(scenario_id="high", name="high", base_world_digest=BASE)
    low = Scenario(scenario_id="low", name="low", base_world_digest=BASE)
    guard = ScenarioGuard(path="capacities.a", operator=ComparisonOperator.GE, value=0.8)
    tree = ScenarioTree(
        root_scenario_id="root",
        scenarios=(root, high, low),
        branches=(
            ScenarioBranch(
                branch_id="b1",
                parent_scenario_id="root",
                child_scenario_id="high",
                label="high",
                guard=guard,
            ),
            ScenarioBranch(
                branch_id="b2", parent_scenario_id="root", child_scenario_id="low", label="low"
            ),
        ),
    )
    results = ScenarioEngine().tree(tree, ScenarioState(capacities={"a": 0.9}))
    assert set(results) == {"root", "high", "low"}
    assert guard_matches(ScenarioState(capacities={"a": 0.9}), guard)
    assert not guard_matches(ScenarioState(capacities={"a": 0.7}), guard)


def test_scenario_tree_rejects_cycle() -> None:
    root = Scenario(scenario_id="root", name="root", base_world_digest=BASE)
    a = Scenario(scenario_id="a", name="a", base_world_digest=BASE)
    b = Scenario(scenario_id="b", name="b", base_world_digest=BASE)
    with pytest.raises(ValueError):
        ScenarioTree(
            root_scenario_id="root",
            scenarios=(root, a, b),
            branches=(
                ScenarioBranch(
                    branch_id="1", parent_scenario_id="root", child_scenario_id="a", label="ra"
                ),
                ScenarioBranch(
                    branch_id="2", parent_scenario_id="a", child_scenario_id="b", label="ab"
                ),
                ScenarioBranch(
                    branch_id="3", parent_scenario_id="b", child_scenario_id="a", label="ba"
                ),
            ),
        )


def test_scenario_build_is_deterministic() -> None:
    a = Scenario.build(
        name="demo", base_world_digest=BASE, kind=ScenarioKind.STRESS, capacities={"a": 0.5}
    )
    b = Scenario.build(
        name="demo", base_world_digest=BASE, kind=ScenarioKind.STRESS, capacities={"a": 0.5}
    )
    assert a.scenario_id == b.scenario_id
    assert a.digest == b.digest


def test_shock_helpers_are_deterministic() -> None:
    z = Shock(
        shock_id="z",
        name="z",
        event_type=EventType.OUTAGE,
        source_entity_id="a",
        starts_at=T0,
        ends_at=T1,
        severity=0.1,
    )
    a = z.model_copy(update={"shock_id": "a"})
    assert shock_targets(z) == ("a",)
    assert tuple(item.shock_id for item in active_shocks((z,), T0)) == ("z",)
    assert tuple(item.shock_id for item in normalize_shocks((z, a))) == ("a", "z")


def test_full_scenario_run_record() -> None:
    engine = ScenarioEngine()
    scenario = Scenario(
        scenario_id="run",
        name="run",
        base_world_digest=BASE,
        capacities={"a": 0.3},
    )
    base = ScenarioState(
        capacities={"a": 1.0},
        world_digest=BASE,
        active_shock_ids=("old-shock",),
        applied_intervention_ids=("old-intervention",),
    )
    result, record = engine.run(base, scenario)
    assert result.capacities["a"] == 0.3
    assert record.applied_shock_ids == ()
    assert record.applied_intervention_ids == ()
    assert record.base_digest
    assert record.result_digest == result.digest
    assert record.deterministic_key.startswith("scenario-run:")


def test_json_schema_is_versioned() -> None:
    from seraph.scenarios.schema import KEY, json_schema

    schema = json_schema()
    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert schema["$id"] == KEY
    assert "Scenario" in schema["$defs"]


def test_world_digest_guard_and_remove_patch() -> None:
    scenario = Scenario(
        scenario_id="guarded",
        name="guarded",
        base_world_digest="expected",
        patches=(
            StatePatch(
                entity_id="a",
                path="attributes.nested.value",
                operation=PatchOperation.SET,
                value=3,
            ),
        ),
    )
    base = ScenarioState(
        capacities={"a": 1.0},
        attributes={"a": {"obsolete": 1}},
        world_digest="wrong",
    )
    with pytest.raises(ValueError, match="base_world_digest"):
        apply_scenario(base, scenario, require_world_digest=True)
    out = apply_scenario(
        ScenarioState(
            capacities={"a": 1.0},
            attributes={"a": {"obsolete": 1}},
            world_digest="expected",
        ),
        scenario,
        require_world_digest=True,
    )
    assert out.attributes["a"]["nested"] == {"value": 3}
    remove = StatePatch(
        entity_id="a",
        path="attributes.nested.value",
        operation=PatchOperation.REMOVE,
    )
    out.apply_patch(remove)
    assert out.attributes["a"]["nested"] == {}


def test_scenario_tree_rejects_multiple_parents() -> None:
    root = Scenario(scenario_id="root", name="root", base_world_digest=BASE)
    a = Scenario(scenario_id="a", name="a", base_world_digest=BASE)
    b = Scenario(scenario_id="b", name="b", base_world_digest=BASE)
    child = Scenario(scenario_id="child", name="child", base_world_digest=BASE)
    with pytest.raises(ValueError, match="multiple parents"):
        ScenarioTree(
            root_scenario_id="root",
            scenarios=(root, a, b, child),
            branches=(
                ScenarioBranch(
                    branch_id="1", parent_scenario_id="root", child_scenario_id="a", label="a"
                ),
                ScenarioBranch(
                    branch_id="2", parent_scenario_id="root", child_scenario_id="b", label="b"
                ),
                ScenarioBranch(
                    branch_id="3", parent_scenario_id="a", child_scenario_id="child", label="ac"
                ),
                ScenarioBranch(
                    branch_id="4", parent_scenario_id="b", child_scenario_id="child", label="bc"
                ),
            ),
        )


def test_golden_vectors() -> None:
    path = Path(__file__).with_name("scenarios_golden_vectors.json")
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["contract_version"] == "seraph-scenarios@1.0.0"
    assert len(payload["vectors"]) == 8
    for vector in payload["vectors"]:
        scenario = Scenario.model_validate(vector["scenario"], strict=False)
        base = ScenarioState(capacities=vector["base_state"]["capacities"])
        out = apply_scenario(base, scenario, at=T0)
        assert out.capacities == vector["expected"]["capacities"]
        assert out.transmission_reductions == vector["expected"]["transmission_reductions"]
        assert out.digest == vector["expected"]["digest"]
