"""Deterministic temporal propagation engine.

The engine implements bounded, time-respecting graph propagation.  It is
intentionally a mechanistic reference implementation rather than a learned or
probabilistic forecaster.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from heapq import heappop, heappush
from math import isfinite
from typing import TYPE_CHECKING, Any

from seraph.core.enums import EpistemicStatus
from seraph.core.hash import deterministic_id
from seraph.core.time import ensure_utc

from .evidence import build_evidence
from .interventions import attenuation_for, merge_attenuation_maps, merge_capacity_gains
from .models import (
    PropagationAggregation,
    PropagationEvent,
    PropagationResult,
    PropagationStatus,
    PropagationSummary,
)
from .rules import PropagationRule
from .state import aggregate_impairments

if TYPE_CHECKING:
    from seraph.graph.store import TemporalGraph
    from seraph.scenarios.shocks import Shock
    from seraph.scenarios.state import ScenarioState


@dataclass(frozen=True, slots=True)
class _Signal:
    source_shock_id: str
    entity_id: str
    impairment: float
    depth: int
    path_entity_ids: tuple[str, ...]
    path_relationship_ids: tuple[str, ...]
    effective_at: datetime
    parent_entity_id: str | None
    parent_relationship_id: str | None
    delay_seconds: float

    @property
    def key(self) -> tuple[object, ...]:
        return (
            self.source_shock_id,
            self.path_relationship_ids,
            self.entity_id,
        )


class PropagationEngine:
    """Reusable deterministic propagation reference implementation."""

    def __init__(
        self,
        graph: TemporalGraph,
        rule: PropagationRule | None = None,
        *,
        state: ScenarioState | None = None,
    ) -> None:
        self.graph = graph
        self.rule = rule or PropagationRule()
        self.rule.validate()
        self.state = state

    def propagate(
        self,
        shock: Shock,
        *,
        transmission_reduction: dict[str, float] | None = None,
        capacity_gain: dict[str, float] | None = None,
        at: datetime | None = None,
        state: ScenarioState | None = None,
    ) -> tuple[PropagationEvent, ...]:
        """Backward-compatible single-shock API returning canonical events."""
        return self.propagate_many(
            (shock,),
            transmission_reduction=transmission_reduction,
            capacity_gain=capacity_gain,
            at=at,
            state=state,
        )

    def propagate_many(
        self,
        shocks: tuple[Shock, ...] | list[Shock],
        *,
        transmission_reduction: dict[str, float] | None = None,
        capacity_gain: dict[str, float] | None = None,
        at: datetime | None = None,
        state: ScenarioState | None = None,
    ) -> tuple[PropagationEvent, ...]:
        """Propagate multiple initiating shocks deterministically."""
        result = self.run(
            shocks,
            transmission_reduction=transmission_reduction,
            capacity_gain=capacity_gain,
            at=at,
            state=state,
        )
        return result.events

    def run(
        self,
        shocks: tuple[Shock, ...] | list[Shock] | Shock,
        *,
        transmission_reduction: dict[str, float] | None = None,
        capacity_gain: dict[str, float] | None = None,
        at: datetime | None = None,
        state: ScenarioState | None = None,
    ) -> PropagationResult:
        """Execute propagation and return events plus summary/evidence."""
        shock_items = (shocks,) if not isinstance(shocks, (tuple, list)) else tuple(shocks)
        ordered_shocks = tuple(
            sorted(shock_items, key=lambda item: (item.starts_at, item.shock_id))
        )
        effective_state = state or self.state
        state_reductions = (
            {} if effective_state is None else dict(effective_state.transmission_reductions)
        )
        reductions = merge_attenuation_maps(state_reductions, transmission_reduction)
        gains = merge_capacity_gains(capacity_gain)
        if not ordered_shocks:
            summary = PropagationSummary(
                status=PropagationStatus.NO_INITIAL_SIGNAL,
                aggregation=self.rule.aggregation,
                event_count=0,
                reached_entity_count=0,
                max_depth=0,
                maximum_impairment=0.0,
                source_shock_ids=(),
                started_at=None,
                terminal_at=None,
                processed_signals=0,
                generated_signals=0,
                truncated=False,
                termination_reason="no shocks supplied",
                rule_digest=self.rule.digest,
            )
            result_id = deterministic_id("propagation", self.rule.digest, "empty")
            return PropagationResult(result_id=result_id, events=(), evidence=(), summary=summary)

        heap: list[tuple[datetime, int, str, str, tuple[str, ...], tuple[str, ...], _Signal]] = []
        contributions: dict[str, list[_Signal]] = {}
        seen_signals: set[tuple[object, ...]] = set()
        processed = 0
        generated = 0
        truncated = False
        termination_reason = "quiescent"
        truncation_reason: str | None = None

        def push(signal: _Signal) -> None:
            nonlocal generated, truncated, truncation_reason
            if signal.impairment < self.rule.minimum_impairment:
                return
            if signal.key in seen_signals:
                return
            current = contributions.setdefault(signal.entity_id, [])
            if len(current) >= self.rule.max_paths_per_entity:
                nonlocal truncation_reason
                truncated = True
                truncation_reason = "max_paths_per_entity reached"
                return
            seen_signals.add(signal.key)
            current.append(signal)
            generated += 1
            heappush(
                heap,
                (
                    signal.effective_at,
                    signal.depth,
                    signal.source_shock_id,
                    signal.entity_id,
                    signal.path_relationship_ids,
                    signal.path_entity_ids,
                    signal,
                ),
            )

        for shock in ordered_shocks:
            seed_at = _seed_time(shock, at)
            attenuation = attenuation_for(shock.source_entity_id, reductions, gains)
            impairment = max(0.0, min(1.0, float(shock.severity) * attenuation))
            push(
                _Signal(
                    source_shock_id=shock.shock_id,
                    entity_id=shock.source_entity_id,
                    impairment=impairment,
                    depth=0,
                    path_entity_ids=(shock.source_entity_id,),
                    path_relationship_ids=(),
                    effective_at=seed_at,
                    parent_entity_id=None,
                    parent_relationship_id=None,
                    delay_seconds=0.0,
                )
            )

        while heap:
            if processed >= self.rule.max_signals:
                truncated = True
                termination_reason = "max_signals reached"
                truncation_reason = termination_reason
                break
            _, _, _, _, _, _, current = heappop(heap)
            processed += 1
            if current.depth >= self.rule.max_hops:
                continue
            if current.impairment < self.rule.minimum_impairment:
                continue
            for relationship in self.graph.edges_from(current.entity_id, at=current.effective_at):
                if not self.rule.allows_relationship(relationship):
                    continue
                target_id = relationship.target.entity_id
                if not self.rule.allow_cycles and target_id in current.path_entity_ids:
                    continue
                factor = self.rule.edge_factor(relationship)
                if factor <= 0:
                    continue
                delay = self.rule.delay_seconds(relationship)
                arrival = current.effective_at + timedelta(seconds=delay)
                if self.rule.require_edge_active_on_arrival and not _relationship_active(
                    relationship, arrival
                ):
                    continue
                attenuation = attenuation_for(target_id, reductions, gains)
                candidate = current.impairment * factor * attenuation
                if not isfinite(candidate) or candidate < self.rule.minimum_impairment:
                    continue
                push(
                    _Signal(
                        source_shock_id=current.source_shock_id,
                        entity_id=target_id,
                        impairment=min(1.0, candidate),
                        depth=current.depth + 1,
                        path_entity_ids=(*current.path_entity_ids, target_id),
                        path_relationship_ids=(
                            *current.path_relationship_ids,
                            relationship.relationship_id,
                        ),
                        effective_at=arrival,
                        parent_entity_id=current.entity_id,
                        parent_relationship_id=relationship.relationship_id,
                        delay_seconds=current.delay_seconds + delay,
                    )
                )

        events = _materialize_events(
            contributions, self.rule.aggregation, bool(reductions or gains)
        )
        status = PropagationStatus.TRUNCATED if truncated else PropagationStatus.COMPLETE
        if not events:
            status = PropagationStatus.NO_INITIAL_SIGNAL
            termination_reason = "all initial signals below minimum impairment"
        elif truncation_reason is not None:
            termination_reason = truncation_reason
        started_at = min(
            (event.effective_at for event in events),
            default=None,
        )
        terminal_at = max(
            (event.effective_at for event in events),
            default=None,
        )
        summary = PropagationSummary(
            status=status,
            aggregation=self.rule.aggregation,
            event_count=len(events),
            reached_entity_count=len(events),
            max_depth=max((event.depth for event in events), default=0),
            maximum_impairment=max((event.impairment for event in events), default=0.0),
            source_shock_ids=tuple(sorted({item.shock_id for item in ordered_shocks})),
            started_at=started_at,
            terminal_at=terminal_at,
            processed_signals=processed,
            generated_signals=generated,
            truncated=truncated,
            termination_reason=termination_reason,
            rule_digest=self.rule.digest,
        )
        evidence = build_evidence(events)
        result_id = deterministic_id(
            "propagation",
            tuple(item.shock_id for item in ordered_shocks),
            self.rule.digest,
            tuple(event.model_dump(mode="json") for event in events),
        )
        return PropagationResult(
            result_id=result_id, events=events, evidence=evidence, summary=summary
        )


def apply_scenario_propagation(
    graph: TemporalGraph,
    scenario: Any,
    *,
    rule: PropagationRule | None = None,
    state: ScenarioState | None = None,
    at: datetime | None = None,
) -> PropagationResult:
    """Convenience adapter from the frozen Scenario model to propagation."""
    shocks = tuple(getattr(scenario, "shocks", ()))
    return PropagationEngine(graph, rule, state=state).run(shocks, at=at, state=state)


def _seed_time(shock: Any, at: datetime | None) -> datetime:
    start = ensure_utc(shock.starts_at)
    if at is None:
        return start
    return max(start, ensure_utc(at))


def _relationship_active(relationship: Any, at: datetime) -> bool:
    valid_from = getattr(relationship, "valid_from", None)
    valid_to = getattr(relationship, "valid_to", None)
    instant = ensure_utc(at)
    return (valid_from is None or instant >= ensure_utc(valid_from)) and (
        valid_to is None or instant < ensure_utc(valid_to)
    )


def _materialize_events(
    contributions: dict[str, list[_Signal]],
    aggregation: PropagationAggregation,
    counterfactual: bool,
) -> tuple[PropagationEvent, ...]:
    events: list[PropagationEvent] = []
    status = EpistemicStatus.COUNTERFACTUAL if counterfactual else EpistemicStatus.MODELED
    for entity_id in sorted(contributions):
        signals = tuple(contributions[entity_id])
        aggregate = aggregate_impairments(tuple(item.impairment for item in signals), aggregation)
        strongest = min(
            signals,
            key=lambda item: (
                -item.impairment,
                item.depth,
                item.effective_at,
                item.source_shock_id,
                item.path_relationship_ids,
                item.path_entity_ids,
            ),
        )
        events.append(
            PropagationEvent(
                entity_id=entity_id,
                impairment=aggregate,
                depth=strongest.depth,
                path_entity_ids=strongest.path_entity_ids,
                path_relationship_ids=strongest.path_relationship_ids,
                effective_at=strongest.effective_at,
                status=status,
                source_shock_ids=tuple(sorted({item.source_shock_id for item in signals})),
                parent_entity_id=strongest.parent_entity_id,
                parent_relationship_id=strongest.parent_relationship_id,
                contribution=strongest.impairment,
                aggregation=aggregation,
                arrival_delay_seconds=strongest.delay_seconds,
            )
        )
    return tuple(
        sorted(
            events,
            key=lambda item: (item.depth, -item.impairment, item.effective_at, item.entity_id),
        )
    )
