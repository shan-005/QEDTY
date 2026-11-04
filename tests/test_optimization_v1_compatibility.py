from __future__ import annotations

import json
import re
from pathlib import Path

from qedty.optimization.models import RankedIntervention
from qedty.optimization.portfolio import knapsack_portfolio

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "contracts/qedty/optimization/optimization-v1.json"
PROTO = ROOT / "proto/qedty/optimization/v1/optimization.proto"


def test_optimization_v1_json_schema_surface_is_preserved() -> None:
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))

    assert schema["$id"] == "https://qedty.dev/schema/optimization/v1"
    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert schema["type"] == "object"

    properties = schema["properties"]
    assert set(properties) == {
        "budget_usd",
        "objective",
        "recommendations",
        "selected_intervention_ids",
    }
    assert set(schema["required"]) == {
        "recommendations",
        "objective",
        "budget_usd",
    }
    assert properties["budget_usd"] == {
        "minimum": 0,
        "type": "number",
    }


def test_optimization_v1_protobuf_field_numbers_and_types_are_preserved() -> None:
    source = PROTO.read_text(encoding="utf-8")
    assert "package qedty.optimization.v1;" in source

    messages: dict[str, dict[str, tuple[str, int]]] = {}

    message_pattern = re.compile(r"message\s+(\w+)\s*\{([^}]*)\}")
    field_pattern = re.compile(
        r"\b(optional\s+|repeated\s+)?"
        r"([A-Za-z_][A-Za-z0-9_.]*)\s+"
        r"([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(\d+)\s*;"
    )

    for message_match in message_pattern.finditer(source):
        name, body = message_match.groups()
        fields = {}

        for field_match in field_pattern.finditer(body):
            qualifier, field_type, field_name, number = field_match.groups()
            fields[field_name] = (
                f"{qualifier or ''}{field_type}",
                int(number),
            )

        messages[name] = fields

    assert messages["Digest"] == {
        "sha256": ("string", 1),
    }
    assert messages["Metadata"] == {
        "schema_version": ("string", 1),
        "producer": ("string", 2),
    }
    assert messages["RankedIntervention"] == {
        "intervention_id": ("string", 1),
        "continuity_gain": ("double", 2),
        "cost_usd": ("double", 3),
        "efficiency": ("double", 4),
        "robust_score": ("double", 5),
        "selected": ("bool", 6),
    }
    assert messages["OptimizationResult"] == {
        "metadata": ("Metadata", 1),
        "recommendations": ("repeated RankedIntervention", 2),
        "objective": ("string", 3),
        "budget_usd": ("double", 4),
        "selected_intervention_ids": ("repeated string", 5),
        "spent_usd": ("double", 6),
        "digest": ("Digest", 7),
    }


def test_v1_zero_cost_candidate_keeps_legacy_knapsack_selection_semantics() -> None:
    """v1 assigns zero objective contribution to a zero-cost candidate.

    The versioned v2 contract intentionally uses different selection semantics;
    v2.1 adds the separately versioned resilience_gain objective. Keep
    this v1 behavior stable rather than silently changing existing callers.
    """
    free_candidate = RankedIntervention(
        intervention_id="free-positive-gain",
        continuity_gain=5.0,
        cost_usd=0.0,
        efficiency=5.0,
        robust_score=5.0,
    )

    selected, spent = knapsack_portfolio((free_candidate,), 0.0)

    assert selected == ()
    assert spent == 0.0
