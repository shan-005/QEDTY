"""SERAPH-PCI-X deterministic temporal propagation layer."""

from .arrow import events_to_table, result_to_tables
from .engine import PropagationEngine, apply_scenario_propagation
from .evidence import build_evidence, evidence_for_event, summarize_evidence
from .interventions import (
    active_intervention_effects,
    attenuation_for,
    merge_attenuation_maps,
    merge_capacity_gains,
)
from .models import (
    PropagationAggregation,
    PropagationEvent,
    PropagationEvidence,
    PropagationResult,
    PropagationStatus,
    PropagationSummary,
)
from .path import critical_paths, group_by_entity, influence_score, strongest, top_k
from .rules import PropagationRule
from .schema import CONTRACT_PROFILE, KEY, NAME, VERSION, json_schema
from .state import EntityPropagationState, aggregate_impairments

__all__ = [
    "CONTRACT_PROFILE",
    "KEY",
    "NAME",
    "VERSION",
    "EntityPropagationState",
    "PropagationAggregation",
    "PropagationEngine",
    "PropagationEvent",
    "PropagationEvidence",
    "PropagationResult",
    "PropagationRule",
    "PropagationStatus",
    "PropagationSummary",
    "active_intervention_effects",
    "aggregate_impairments",
    "apply_scenario_propagation",
    "attenuation_for",
    "build_evidence",
    "critical_paths",
    "events_to_table",
    "evidence_for_event",
    "group_by_entity",
    "influence_score",
    "json_schema",
    "merge_attenuation_maps",
    "merge_capacity_gains",
    "result_to_tables",
    "strongest",
    "summarize_evidence",
    "top_k",
]
