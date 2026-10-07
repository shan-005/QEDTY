from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .contracts import ContractResult
from .geometry import GeodeticPoint, geodetic_to_ecef
from .hash import canonical_json, deterministic_id
from .time import parse_rfc3339, to_rfc3339
from .units import convert_value


class ConformanceError(AssertionError):
    """Raised when a golden vector does not match the reference semantics."""


def load_vector(path: str | Path) -> dict[str, Any]:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ConformanceError(f"golden vector must be an object: {path}")
    return value


def check_vector(vector: dict[str, Any]) -> None:
    kind = vector.get("kind")
    if kind == "identity":
        actual = deterministic_id(
            vector["kind"], vector["namespace"], *vector["parts"], length=vector["length"]
        )
        if actual != vector["expected_id"]:
            raise ConformanceError(f"identity mismatch: {actual!r} != {vector['expected_id']!r}")
    elif kind == "canonical_json":
        actual = canonical_json(vector["value"])
        if actual != vector["expected"]:
            raise ConformanceError(f"canonical JSON mismatch: {actual!r} != {vector['expected']!r}")
    elif kind == "time":
        instant = parse_rfc3339(vector["input"])
        actual = to_rfc3339(instant)
        if actual != vector["expected_utc"]:
            raise ConformanceError(f"time mismatch: {actual!r} != {vector['expected_utc']!r}")
    elif kind == "quantity":
        actual = str(convert_value(vector["value"], vector["from_unit"], vector["to_unit"]))
        if actual != vector["expected_value"]:
            raise ConformanceError(f"quantity mismatch: {actual!r} != {vector['expected_value']!r}")
    elif kind == "geometry_ecef":
        point = GeodeticPoint(vector["latitude"], vector["longitude"], vector.get("height_m", 0.0))
        actual_ecef = geodetic_to_ecef(point)
        for actual_value, expected_value in zip(
            actual_ecef, vector["expected_ecef_m"], strict=False
        ):
            if abs(actual_value - expected_value) > vector.get("absolute_tolerance_m", 1e-6):
                raise ConformanceError(
                    f"ECEF mismatch: actual={actual_ecef}; expected={vector['expected_ecef_m']}"
                )
    elif kind == "contract_result":
        result = ContractResult(
            value=vector["value"],
            epistemic_state=vector["epistemic_state"],
            evidence_ids=tuple(vector.get("evidence_ids", [])),
            provenance_ids=tuple(vector.get("provenance_ids", [])),
            assumptions=tuple(vector.get("assumptions", [])),
            model_id=vector.get("model_id"),
            model_version=vector.get("model_version"),
            valid_at=parse_rfc3339(vector["valid_at"]) if vector.get("valid_at") else None,
            uncertainty=vector.get("uncertainty"),
            metadata=vector.get("metadata", {}),
        )
        actual = canonical_json(result.to_dict())
        if actual != vector["expected_canonical_json"]:
            raise ConformanceError("ContractResult canonical representation mismatch")
    else:
        raise ConformanceError(f"unknown vector kind: {kind!r}")
