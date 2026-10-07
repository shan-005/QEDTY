"""Deterministic scenario execution, composition and branching."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from seraph.core.enums import EpistemicStatus
from seraph.core.hash import deterministic_id
from seraph.core.time import ensure_utc

from .interventions import active_interventions
from .models import ComparisonOperator, Scenario, ScenarioGuard, ScenarioRun, ScenarioTree
from .shocks import active_shocks

if TYPE_CHECKING:
    from collections.abc import Iterable
    from datetime import datetime

    from .state import ScenarioState


def apply_scenario(
    base: ScenarioState,
    scenario: Scenario,
    *,
    at: datetime | None = None,
    require_world_digest: bool = False,
) -> ScenarioState:
    """Materialize ``scenario`` on a copy of ``base``.

    Backward compatibility: ``parameters`` remain capacity multipliers and
    ``capacities`` remain absolute overrides.  New explicit patches, shocks and
    interventions are then applied deterministically.
    """
    out = base.copy()
    if (
        require_world_digest
        and scenario.base_world_digest
        and out.world_digest != scenario.base_world_digest
    ):
        raise ValueError("scenario base_world_digest does not match state world_digest")
    if (
        scenario.base_state_digest is not None
        and require_world_digest
        and base.digest != scenario.base_state_digest
    ):
        raise ValueError("scenario base_state_digest does not match input state digest")

    for entity_id, multiplier in sorted(scenario.parameters.items()):
        out.set_capacity(entity_id, out.capacity(entity_id) * multiplier)

    for entity_id, value in sorted(scenario.capacities.items()):
        out.set_capacity(entity_id, value)

    out.apply_patches(scenario.patches)

    evaluation_time = ensure_utc(at) if at is not None else _default_evaluation_time(scenario, out)
    for shock in active_shocks(scenario.shocks, evaluation_time) if evaluation_time else ():
        for entity_id, multiplier in sorted(shock.capacity_multipliers.items()):
            out.set_capacity(entity_id, out.capacity(entity_id) * multiplier)
        out.apply_patches(shock.patches)
        out.active_shock_ids = tuple(sorted(set(out.active_shock_ids) | {shock.shock_id}))

    for intervention in active_interventions(scenario.interventions, evaluation_time):
        for entity_id in intervention.protected_entity_ids:
            gain = intervention.capacity_gain
            out.set_capacity(entity_id, out.capacity(entity_id) + gain)
            out.transmission_reductions[entity_id] = max(
                out.transmission_reductions.get(entity_id, 0.0), intervention.transmission_reduction
            )
        out.apply_patches(intervention.patches)
        out.applied_intervention_ids = tuple(
            sorted(set(out.applied_intervention_ids) | {intervention.intervention_id})
        )

    out.lineage = (*out.lineage, scenario.scenario_id)
    out.with_evaluation(evaluation_time)
    out.validate()
    return out


def compose_scenarios(
    base: ScenarioState,
    scenarios: Iterable[Scenario],
    *,
    at: datetime | None = None,
    require_world_digest: bool = False,
) -> ScenarioState:
    out = base
    for scenario in scenarios:
        out = apply_scenario(out, scenario, at=at, require_world_digest=require_world_digest)
    return out


class ScenarioEngine:
    """Reusable deterministic scenario executor."""

    def apply(
        self,
        base: ScenarioState,
        scenario: Scenario,
        *,
        at: datetime | None = None,
        require_world_digest: bool = False,
    ) -> ScenarioState:
        return apply_scenario(base, scenario, at=at, require_world_digest=require_world_digest)

    def run(
        self,
        base: ScenarioState,
        scenario: Scenario,
        *,
        at: datetime | None = None,
        require_world_digest: bool = False,
    ) -> tuple[ScenarioState, ScenarioRun]:
        result = self.apply(base, scenario, at=at, require_world_digest=require_world_digest)
        run_id = deterministic_id("scenario-run", scenario.scenario_id, base.digest, result.digest)
        record = ScenarioRun(
            run_id=run_id,
            scenario_id=scenario.scenario_id,
            base_digest=base.digest,
            result_digest=result.digest,
            applied_shock_ids=tuple(
                sorted(set(result.active_shock_ids) - set(base.active_shock_ids))
            ),
            applied_intervention_ids=tuple(
                sorted(set(result.applied_intervention_ids) - set(base.applied_intervention_ids))
            ),
            epistemic_status=(
                EpistemicStatus.COUNTERFACTUAL
                if scenario.kind.value == "counterfactual"
                else scenario.epistemic_status
            ),
        )
        return result, record

    def compose(
        self,
        base: ScenarioState,
        scenarios: Iterable[Scenario],
        *,
        at: datetime | None = None,
        require_world_digest: bool = False,
    ) -> ScenarioState:
        return compose_scenarios(base, scenarios, at=at, require_world_digest=require_world_digest)

    def tree(
        self, tree: ScenarioTree, base: ScenarioState, *, at: datetime | None = None
    ) -> dict[str, ScenarioState]:
        """Evaluate every scenario node reachable from the tree root."""
        index = {scenario.scenario_id: scenario for scenario in tree.scenarios}
        results: dict[str, ScenarioState] = {}

        def visit(node_id: str, state: ScenarioState) -> None:
            scenario = index[node_id]
            result = self.apply(state, scenario, at=at)
            results[node_id] = result
            branch_by_child = {
                branch.child_scenario_id: branch
                for branch in tree.branches
                if branch.parent_scenario_id == node_id
            }
            for child in tree.children_of(node_id):
                branch = branch_by_child.get(child.scenario_id)
                if (
                    branch is not None
                    and branch.guard is not None
                    and not guard_matches(result, branch.guard)
                ):
                    continue
                visit(child.scenario_id, result)

        visit(tree.root_scenario_id, base)
        return results


def _default_evaluation_time(scenario: Scenario, state: ScenarioState) -> datetime | None:
    if state.evaluated_at is not None:
        return state.evaluated_at
    if scenario.valid_from is not None:
        return scenario.valid_from
    starts = [shock.starts_at for shock in scenario.shocks]
    activations = [
        item.activation_at for item in scenario.interventions if item.activation_at is not None
    ]
    candidates = [*starts, *activations]
    return min(candidates) if candidates else None


def guard_matches(state: ScenarioState, guard: ScenarioGuard) -> bool:
    """Evaluate a declarative scenario guard against materialized state."""
    current: object | None
    parts = guard.path.split(".")
    if len(parts) >= 2 and parts[0] == "capacities":
        current = state.capacities.get(parts[1])
    elif len(parts) >= 3 and parts[0] == "attributes":
        current = state.attributes.get(parts[1])
        for part in parts[2:]:
            if not isinstance(current, dict) or part not in current:
                current = None
                break
            current = current[part]
    elif len(parts) >= 2 and parts[0] == "transmission_reductions":
        current = state.transmission_reductions.get(parts[1])
    elif guard.path == "world_digest":
        current = state.world_digest
    else:
        raise ValueError("unsupported guard path")

    target = guard.value
    op = guard.operator
    if op is ComparisonOperator.EQ:
        return bool(current == target)
    if op is ComparisonOperator.NE:
        return bool(current != target)
    if current is None:
        return False
    try:
        if op is ComparisonOperator.LT:
            return bool(current < target)
        if op is ComparisonOperator.LE:
            return bool(current <= target)
        if op is ComparisonOperator.GE:
            return bool(current >= target)
        if op is ComparisonOperator.GT:
            return bool(current > target)
    except TypeError as exc:
        raise ValueError("guard comparison uses incompatible value types") from exc
    raise ValueError(f"unsupported guard operator: {op}")
