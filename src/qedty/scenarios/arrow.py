"""Optional Arrow interchange for scenario and state records."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .models import Scenario
    from .state import ScenarioState


def _pyarrow() -> Any:
    try:
        import pyarrow as pa  # type: ignore[import-untyped]
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("pyarrow is required for scenario Arrow interchange") from exc
    return pa


def scenarios_to_table(scenarios: tuple[Scenario, ...] | list[Scenario]) -> Any:
    """Convert deterministic scenario descriptors to an Arrow table."""
    pa = _pyarrow()
    ordered = sorted(scenarios, key=lambda item: item.scenario_id)
    return pa.table(
        {
            "scenario_id": [item.scenario_id for item in ordered],
            "name": [item.name for item in ordered],
            "kind": [item.kind.value for item in ordered],
            "status": [item.status.value for item in ordered],
            "base_world_digest": [item.base_world_digest for item in ordered],
            "epistemic_status": [item.epistemic_status.value for item in ordered],
            "parameters_json": [item.model_dump_json(include={"parameters"}) for item in ordered],
            "capacities_json": [item.model_dump_json(include={"capacities"}) for item in ordered],
            "scenario_digest": [item.digest for item in ordered],
        }
    )


def states_to_table(
    states: dict[str, ScenarioState] | tuple[tuple[str, ScenarioState], ...],
) -> Any:
    """Convert named materialized scenario states to Arrow."""
    pa = _pyarrow()
    items = (
        sorted(states.items(), key=lambda item: item[0])
        if isinstance(states, dict)
        else tuple(sorted(states, key=lambda item: item[0]))
    )
    return pa.table(
        {
            "scenario_id": [scenario_id for scenario_id, _ in items],
            "state_digest": [state.digest for _, state in items],
            "capacities_json": [str(state.to_mapping()["capacities"]) for _, state in items],
            "attributes_json": [str(state.to_mapping()["attributes"]) for _, state in items],
            "transmission_reductions_json": [
                str(state.to_mapping()["transmission_reductions"]) for _, state in items
            ],
        }
    )
