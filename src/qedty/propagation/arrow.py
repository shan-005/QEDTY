"""Optional Apache Arrow interchange for propagation artifacts."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .models import PropagationEvent, PropagationResult


def _pyarrow() -> Any:
    try:
        import pyarrow as pa  # type: ignore[import-untyped]
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("pyarrow is required for propagation Arrow interchange") from exc
    return pa


def events_to_table(events: tuple[PropagationEvent, ...] | list[PropagationEvent]) -> Any:
    pa = _pyarrow()
    ordered = sorted(events, key=lambda item: (item.entity_id, item.effective_at, item.depth))
    return pa.table(
        {
            "entity_id": [item.entity_id for item in ordered],
            "impairment": [item.impairment for item in ordered],
            "depth": [item.depth for item in ordered],
            "effective_at": [item.effective_at for item in ordered],
            "status": [item.status.value for item in ordered],
            "aggregation": [item.aggregation.value for item in ordered],
            "contribution": [item.contribution for item in ordered],
            "source_shock_ids": [list(item.source_shock_ids) for item in ordered],
            "path_entity_ids": [list(item.path_entity_ids) for item in ordered],
            "path_relationship_ids": [list(item.path_relationship_ids) for item in ordered],
            "parent_entity_id": [item.parent_entity_id for item in ordered],
            "parent_relationship_id": [item.parent_relationship_id for item in ordered],
            "arrival_delay_seconds": [item.arrival_delay_seconds for item in ordered],
        }
    )


def result_to_tables(result: PropagationResult) -> dict[str, Any]:
    pa = _pyarrow()
    events = events_to_table(result.events)
    summary = pa.table(
        {
            "result_id": [result.result_id],
            "event_count": [result.summary.event_count],
            "reached_entity_count": [result.summary.reached_entity_count],
            "max_depth": [result.summary.max_depth],
            "maximum_impairment": [result.summary.maximum_impairment],
            "aggregation": [result.summary.aggregation.value],
            "status": [result.summary.status.value],
            "truncated": [result.summary.truncated],
            "termination_reason": [result.summary.termination_reason],
            "rule_digest": [result.summary.rule_digest],
        }
    )
    return {"events": events, "summary": summary}
