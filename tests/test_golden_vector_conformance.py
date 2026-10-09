from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator

from qedty.continuity.engine import ContinuityEngine
from qedty.core.enums import EpistemicStatus, EventType, InterventionType, RelationshipType
from qedty.counterfactual.engine import CounterfactualEngine
from qedty.economics.engine import EconomicImpactEngine
from qedty.economics.flows import trade_matrix
from qedty.economics.io import IOModel
from qedty.economics.models import EconomicExposure
from qedty.economics.trade import TradeFlow
from qedty.propagation.engine import PropagationEngine
from qedty.propagation.interventions import attenuation_for
from qedty.propagation.models import PropagationAggregation, PropagationEvent
from qedty.propagation.state import aggregate_impairments
from qedty.scenarios.models import Intervention
from qedty.scenarios.shocks import Shock
from qedty.uncertainty.models import Interval
from qedty.uncertainty.propagation import add
from qedty.uncertainty.sampling import deterministic_uniform


ROOT = Path(__file__).resolve().parents[1]
START = datetime(2026, 1, 1, tzinfo=UTC)
END = START + timedelta(days=1)


def _json(path: str) -> dict[str, Any]:
    return json.loads((ROOT / path).read_text(encoding="utf-8-sig"))


def _validate_schema(path: str) -> dict[str, Any]:
    schema = _json(path)
    Draft202012Validator.check_schema(schema)
    return schema


@dataclass(frozen=True, slots=True)
class _NodeRef:
    entity_id: str


@dataclass(frozen=True, slots=True)
class _Edge:
    relationship_id: str
    source: _NodeRef
    target: _NodeRef
    relationship_type: RelationshipType = RelationshipType.SUPPORTS
    valid_from: datetime | None = START
    valid_to: datetime | None = END
    strength: float = 1.0
    capacity_fraction: float = 1.0
    attributes: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class _ShockStub:
    shock_id: str
    source_entity_id: str
    severity: float
    starts_at: datetime
    ends_at: datetime


class _GraphStub:
    def __init__(self, edges: list[_Edge]) -> None:
        self._edges = edges

    def edges_from(self, entity_id: str, at: datetime | None = None) -> tuple[_Edge, ...]:
        matches = []
        for edge in self._edges:
            if edge.source.entity_id != entity_id:
                continue
            if at is not None and edge.valid_from is not None and at < edge.valid_from:
                continue
            if at is not None and edge.valid_to is not None and at >= edge.valid_to:
                continue
            matches.append(edge)
        return tuple(sorted(matches, key=lambda item: item.relationship_id))


def _edge(
    relationship_id: str,
    source: str,
    target: str,
    *,
    strength: float = 1.0,
    delay_seconds: float = 0.0,
) -> _Edge:
    return _Edge(
        relationship_id=relationship_id,
        source=_NodeRef(source),
        target=_NodeRef(target),
        strength=strength,
        attributes={"latency_seconds": delay_seconds},
    )


def _shock(severity: float = 0.8, *, duration_hours: float = 24.0) -> _ShockStub:
    return _ShockStub(
        shock_id="golden-shock",
        source_entity_id="a",
        severity=severity,
        starts_at=START,
        ends_at=START + timedelta(hours=duration_hours),
    )


def test_propagation_golden_vectors_execute_implementation() -> None:
    schema = _validate_schema("contracts/json-schema/propagation-v1.json")
    vectors = _json("tests/propagation_golden_vectors.json")
    assert schema["$id"] == vectors["contract"]
    vector_items = vectors["vectors"]
    assert vector_items, "propagation golden-vector file must not be empty"
    seen: set[str] = set()

    for vector in vector_items:
        vector_id = vector["id"]
        assert vector_id not in seen, f"duplicate propagation vector: {vector_id}"
        seen.add(vector_id)
        if vector_id == "single-edge":
            events = PropagationEngine(
                _GraphStub([_edge("r1", "a", "b", strength=vector["edge_factor"])])
            ).propagate(_shock(vector["severity"]))
            actual = next(event.impairment for event in events if event.entity_id == "b")
        elif vector_id == "two-hop":
            events = PropagationEngine(
                _GraphStub(
                    [
                        _edge("r1", "a", "b", strength=vector["edge_factor"]),
                        _edge("r2", "b", "c", strength=vector["edge_factor"]),
                    ]
                )
            ).propagate(_shock(vector["severity"]))
            actual = next(event.impairment for event in events if event.entity_id == "c")
        elif vector_id in {"sum-cap", "noisy-or", "max"}:
            aggregation = {
                "sum-cap": PropagationAggregation.SUM_CAP,
                "noisy-or": PropagationAggregation.NOISY_OR,
                "max": PropagationAggregation.MAX,
            }[vector_id]
            actual = aggregate_impairments(tuple(vector["contributions"]), aggregation)
        elif vector_id == "intervention":
            attenuation = attenuation_for(
                "service",
                {"service": vector["transmission_reduction"]},
                {"service": vector["capacity_gain"]},
            )
            actual = vector["baseline"] * attenuation
        elif vector_id == "zero-signal":
            result = PropagationEngine(_GraphStub([])).run(_shock(vector["severity"]))
            assert result.events == ()
            actual = sum(event.impairment for event in result.events)
        elif vector_id == "delay":
            events = PropagationEngine(
                _GraphStub(
                    [
                        _edge(
                            "r1",
                            "a",
                            "b",
                            strength=1.0,
                            delay_seconds=vector["delay_seconds"],
                        )
                    ]
                )
            ).propagate(_shock())
            event = next(event for event in events if event.entity_id == "b")
            actual = (event.effective_at - START).total_seconds()
        else:
            raise AssertionError(f"unsupported propagation vector: {vector_id}")

        assert actual == pytest.approx(
            vector.get("expected_impairment", vector.get("expected_elapsed_seconds"))
        ), f"propagation vector failed: {vector_id}"
    assert seen == {vector["id"] for vector in vector_items}


def _continuity_result(vector: dict[str, Any]):
    duration_hours = float(vector.get("duration_hours", 2.0))
    shock = Shock(
        shock_id=f"continuity-{vector['name']}",
        name=vector["name"],
        event_type=EventType.OUTAGE,
        source_entity_id="service",
        starts_at=START,
        ends_at=START + timedelta(hours=duration_hours),
        severity=float(vector.get("impairment_fraction", 0.0)),
    )
    impairment = float(vector.get("impairment_fraction", 0.0))
    events = (
        PropagationEvent(
            entity_id="service",
            impairment=impairment,
            depth=0,
            path_entity_ids=("service",),
            path_relationship_ids=(),
            effective_at=START,
            status=EpistemicStatus.MODELED,
        ),
    ) if impairment > 0 else ()
    return shock, ContinuityEngine().simulate(
        "service",
        shock,
        events,
        threshold=float(vector.get("threshold", 0.3)),
    )


def test_continuity_golden_vectors_execute_implementation() -> None:
    schema = _validate_schema("contracts/json-schema/continuity-v1.json")
    vectors = _json("tests/continuity_golden_vectors.json")
    assert schema["title"] == "QEDTY ContinuityResult v1"
    assert vectors["vectors"], "continuity golden-vector file must not be empty"

    for vector in vectors["vectors"]:
        _, result = _continuity_result(vector)
        actual_fields = result.model_dump(mode="json")
        Draft202012Validator(schema).validate(actual_fields)
        for field_name in (
            "minimum_capacity_fraction",
            "time_below_threshold_hours",
            "capacity_hours",
            "resilience_index",
        ):
            if field_name in vector:
                assert getattr(result, field_name) == pytest.approx(vector[field_name]), (
                    vector["name"],
                    field_name,
                )


class _VectorPropagation:
    def __init__(self, baseline_capacity: float, counterfactual_capacity: float) -> None:
        self._baseline_capacity = baseline_capacity
        self._counterfactual_capacity = counterfactual_capacity

    def propagate(self, shock: Shock, **kwargs: object) -> tuple[PropagationEvent, ...]:
        capacity = self._counterfactual_capacity if kwargs else self._baseline_capacity
        return (
            PropagationEvent(
                entity_id="service",
                impairment=1.0 - capacity,
                depth=0,
                path_entity_ids=("service",),
                path_relationship_ids=(),
                effective_at=shock.starts_at,
                status=EpistemicStatus.MODELED,
            ),
        )


def test_counterfactual_golden_vectors_execute_implementation() -> None:
    schema = _validate_schema("contracts/json-schema/counterfactual-v1.json")
    vectors = _json("tests/counterfactual_golden_vectors.json")
    assert schema["title"] == "QEDTY CounterfactualResult v1"
    assert vectors["vectors"], "counterfactual golden-vector file must not be empty"

    for vector in vectors["vectors"]:
        shock = Shock(
            shock_id=f"counterfactual-{vector['name']}",
            name=vector["name"],
            event_type=EventType.OUTAGE,
            source_entity_id="service",
            starts_at=START,
            ends_at=START + timedelta(hours=2),
            severity=0.5,
        )
        intervention = Intervention(
            intervention_id=f"intervention-{vector['name']}",
            name="Golden-vector intervention",
            intervention_type=InterventionType.HARDENING,
            cost_usd=1.0,
            protected_entity_ids=("service",),
            transmission_reduction=0.5,
        )
        result = CounterfactualEngine(
            _VectorPropagation(
                float(vector["baseline_capacity"]),
                float(vector["counterfactual_capacity"]),
            ),
            ContinuityEngine(),
        ).compare(shock, "service", intervention)
        Draft202012Validator(schema).validate(result.model_dump(mode="json"))
        assert result.baseline_capacity == pytest.approx(vector["baseline_capacity"])
        assert result.counterfactual_capacity == pytest.approx(vector["counterfactual_capacity"])
        assert result.continuity_gain == pytest.approx(vector["continuity_gain"])


def test_economics_golden_vectors_execute_implementation() -> None:
    schema = _validate_schema("contracts/json-schema/economics-v1.json")
    vectors = _json("tests/economics_golden_vectors.json")
    assert schema["title"] == "QEDTY EconomicImpact v1"
    assert vectors["vectors"], "economics golden-vector file must not be empty"

    for vector in vectors["vectors"]:
        if vector["name"] == "single_sector_leontief":
            model = IOModel(
                sectors=("sector",),
                technical_coefficients=(tuple(vector["A"][0]),),
            )
            actual = model.total_output(tuple(vector["d"]))[0]
            assert actual == pytest.approx(vector["x"][0]), vector["name"]
        elif vector["name"] == "trade_total":
            flows = [
                TradeFlow(
                    exporter=item["exporter"],
                    importer=item["importer"],
                    sector=item["sector"],
                    value_usd=float(item["value_usd"]),
                )
                for item in vector["flows"]
            ]
            actual = trade_matrix(flows).total()
            assert actual == pytest.approx(vector["total"]), vector["name"]
        elif vector["name"] == "reference_exposure_loss":
            shock = Shock(
                shock_id=f"economics-{vector['name']}",
                name=vector["name"],
                event_type=EventType.OUTAGE,
                source_entity_id="service",
                starts_at=START,
                ends_at=START + timedelta(hours=float(vector["duration_hours"])),
                severity=1.0 - float(vector["capacity_fraction"]),
            )
            event = PropagationEvent(
                entity_id="service",
                impairment=1.0 - float(vector["capacity_fraction"]),
                depth=0,
                path_entity_ids=("service",),
                path_relationship_ids=(),
                effective_at=START,
                status=EpistemicStatus.MODELED,
            )
            continuity = ContinuityEngine().simulate("service", shock, (event,))
            exposure = EconomicExposure(
                entity_id="service",
                reference_value_usd=float(vector["reference_value_usd"]),
                reference_period_days=float(vector["reference_period_days"]),
                exposed_fraction=float(vector["exposed_fraction"]),
                pass_through=float(vector["pass_through"]),
            )
            result = EconomicImpactEngine().estimate(
                exposure, continuity, float(vector["duration_hours"])
            )
            Draft202012Validator(schema).validate(result.model_dump(mode="json"))
            assert result.direct_loss_usd == pytest.approx(vector["expected_direct_loss_usd"])
            assert result.total_loss_usd == pytest.approx(vector["expected_total_loss_usd"])
        else:
            raise AssertionError(f"unsupported economics vector: {vector['name']}")


def test_uncertainty_golden_vectors_execute_implementation() -> None:
    schema = _validate_schema("contracts/json-schema/uncertainty-v1.json")
    vectors = _json("tests/uncertainty_golden_vectors.json")
    assert schema["title"] == "QEDTY Interval v1"
    assert vectors["vectors"], "uncertainty golden-vector file must not be empty"

    for vector in vectors["vectors"]:
        if vector["name"] == "add":
            actual = add(Interval(**vector["a"]), Interval(**vector["b"]))
            expected = vector["result"]
            actual_dump = actual.model_dump()
            for field_name in ("lower", "estimate", "upper", "confidence_level", "method"):
                if isinstance(expected[field_name], float):
                    assert actual_dump[field_name] == pytest.approx(expected[field_name])
                else:
                    assert actual_dump[field_name] == expected[field_name]
            Draft202012Validator(schema).validate(actual_dump)
        elif vector["name"] == "uniform":
            actual = deterministic_uniform(int(vector["seed"]), int(vector["n"]))
            assert actual[: len(vector["first_three"])] == pytest.approx(vector["first_three"])
            assert len(actual) == vector["n"]
        else:
            raise AssertionError(f"unsupported uncertainty vector: {vector['name']}")

def test_phase1b_reconcile_canonicalizes_legacy_repository_urls() -> None:
    source = (
        "https://github.com/IRIN-0/qedty/tree/main "
        "https://github.com/IRIN-0/QEDTY/issues"
    )
    from runpy import run_path

    namespace = run_path(str(ROOT / "scripts" / "phase1b_reconcile.py"))
    canonicalize_repository_urls = namespace["canonicalize_repository_urls"]
    actual = canonicalize_repository_urls(source)
    assert actual == (
        "https://github.com/shan-005/QEDTY/tree/main "
        "https://github.com/shan-005/QEDTY/issues"
    )
