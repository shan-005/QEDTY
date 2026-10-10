#!/usr/bin/env python3
"""Run QEDTY's Python reference and native Rust core on identical JSON cases.

The runner is intentionally fail-closed: missing Rust tooling, unknown operations,
missing response lines, unexpected errors, and mismatches all return non-zero.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import random
import shlex
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from qedty.core.contracts import ContractResult  # noqa: E402
from qedty.core.geometry import GeodeticPoint, geodetic_to_ecef  # noqa: E402
from qedty.core.hash import canonical_json, deterministic_id  # noqa: E402
from qedty.core.time import in_window, parse_rfc3339, to_rfc3339  # noqa: E402
from qedty.core.units import convert_value  # noqa: E402
from qedty.temporal.intervals import Interval, classify  # noqa: E402

SUPPORTED_OPERATIONS = {
    "canonical_json",
    "identity",
    "quantity.convert",
    "time.normalize",
    "geometry.ecef",
    "contract_result",
    "interval.contains",
    "temporal.relation",
}
DEFAULT_RUST_COMMAND = [
    "cargo",
    "run",
    "--locked",
    "--quiet",
    "-p",
    "qedty-conformance",
    "--bin",
    "qedty-differential",
]


def _error_category(operation: str, error: Exception) -> str:
    message = str(error).casefold()
    name = type(error).__name__.casefold()
    if operation == "identity":
        return "invalid_digest_length" if "length" in message else "invalid_identity"
    if operation == "quantity.convert":
        if "incompatible" in message or "cannot convert" in message:
            return "incompatible_units"
        if "finite" in message or "nan" in message or "infinity" in message:
            return "non_finite"
        if "unknown unit" in message or "unsupported unit" in message:
            return "unknown_unit"
        if "division by zero" in message:
            return "division_by_zero"
        return "invalid_unit"
    if operation in {"time.normalize", "interval.contains", "temporal.relation"}:
        if (
            "interval" in message
            or "start < end" in message
            or "end must be after start" in message
        ):
            return "invalid_interval"
        return "invalid_timestamp"
    if operation == "geometry.ecef":
        return "invalid_coordinate"
    if operation == "contract_result":
        return "invalid_contract"
    if operation == "canonical_json":
        return "invalid_input"
    if "keyerror" in name:
        return "invalid_input"
    return "invalid_input"


def _contract_result_from_input(data: dict[str, Any]) -> str:
    valid_at = parse_rfc3339(data["valid_at"]) if data.get("valid_at") else None
    result = ContractResult(
        value=data["value"],
        epistemic_state=data["epistemic_state"],
        evidence_ids=tuple(data.get("evidence_ids", ())),
        provenance_ids=tuple(data.get("provenance_ids", ())),
        assumptions=tuple(data.get("assumptions", ())),
        model_id=data.get("model_id"),
        model_version=data.get("model_version"),
        valid_at=valid_at,
        uncertainty=data.get("uncertainty"),
        metadata=data.get("metadata", {}),
    )
    return canonical_json(result.to_dict())


def evaluate_reference(operation: str, data: dict[str, Any]) -> dict[str, Any]:
    """Evaluate a case with the real QEDTY Python reference functions."""
    try:
        if operation == "canonical_json":
            result: Any = canonical_json(data["value"])
        elif operation == "identity":
            parts = data["parts"]
            result = deterministic_id(data["kind"], *parts, length=int(data["length"]))
        elif operation == "quantity.convert":
            converted = convert_value(
                Decimal(str(data["value"])), data["from_unit"], data["to_unit"]
            )
            result = float(converted)
            if not math.isfinite(result):
                raise ValueError("quantity result is not finite")
        elif operation == "time.normalize":
            result = to_rfc3339(parse_rfc3339(data["timestamp"]))
        elif operation == "geometry.ecef":
            point = GeodeticPoint(
                latitude=float(data["latitude_deg"]),
                longitude=float(data["longitude_deg"]),
                height_m=float(data["height_m"]),
            )
            result = list(geodetic_to_ecef(point))
        elif operation == "contract_result":
            result = _contract_result_from_input(data["contract"])
        elif operation == "interval.contains":
            result = in_window(
                parse_rfc3339(data["instant"]),
                parse_rfc3339(data["start"]) if data.get("start") is not None else None,
                parse_rfc3339(data["end"]) if data.get("end") is not None else None,
            )
        elif operation == "temporal.relation":
            left = Interval(
                start=parse_rfc3339(data["left"]["start"]),
                end=parse_rfc3339(data["left"]["end"]),
            )
            right = Interval(
                start=parse_rfc3339(data["right"]["start"]),
                end=parse_rfc3339(data["right"]["end"]),
            )
            result = classify(left, right).value
        else:
            return {
                "ok": False,
                "error": {"category": "unsupported_operation", "message": operation},
            }
        return {"ok": True, "result": result}
    except Exception as error:  # classify errors for differential reporting.
        return {
            "ok": False,
            "error": {
                "category": _error_category(operation, error),
                "message": f"{type(error).__name__}: {error}",
            },
        }


def _case(case: dict[str, Any], source: str) -> None:
    required = {"case_id", "operation", "input", "comparison"}
    missing = required - case.keys()
    if missing:
        raise ValueError(f"{source}: case misses required keys {sorted(missing)}")
    if not isinstance(case["case_id"], str) or not case["case_id"].strip():
        raise ValueError(f"{source}: case_id must be a non-empty string")
    if case["operation"] not in SUPPORTED_OPERATIONS:
        raise ValueError(f"{source}/{case['case_id']}: unsupported operation in fixture")
    if not isinstance(case["input"], dict):
        raise ValueError(f"{source}/{case['case_id']}: input must be an object")
    if not isinstance(case["comparison"], dict) or case["comparison"].get("mode") not in {
        "exact",
        "numeric",
        "vector_tolerance",
    }:
        raise ValueError(f"{source}/{case['case_id']}: invalid comparison mode")
    if case["comparison"]["mode"] != "exact":
        for field in ("absolute_tolerance", "relative_tolerance"):
            tolerance = case["comparison"].get(field)
            if (
                isinstance(tolerance, bool)
                or not isinstance(tolerance, (int, float))
                or not math.isfinite(float(tolerance))
                or tolerance < 0
            ):
                raise ValueError(
                    f"{source}/{case['case_id']}: {field} must be finite and non-negative"
                )
    if "expected_error" in case and not isinstance(case["expected_error"], str):
        raise ValueError(
            f"{source}/{case['case_id']}: expected_error must be a string when present"
        )


def _reject_nonstandard_json_constant(value: str) -> None:
    raise ValueError(f"non-standard JSON numeric constant is forbidden: {value}")


def _load_strict_json(path: Path) -> Any:
    return json.loads(
        path.read_text(encoding="utf-8-sig"),
        parse_constant=_reject_nonstandard_json_constant,
    )


def load_cases(directory: Path) -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    seen: set[str] = set()
    schema_path = ROOT / "contracts" / "json-schema" / "differential-cases.schema.json"
    schema = _load_strict_json(schema_path)
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema)
    files = sorted(directory.glob("*.json"))
    if not files:
        raise ValueError(f"no differential case files found under {directory}")
    for path in files:
        document = _load_strict_json(path)
        validator.validate(document)
        if document.get("schema_version") != "qedty-differential-cases@1":
            raise ValueError(f"{path}: unsupported/missing schema_version")
        items = document.get("cases")
        if not isinstance(items, list):
            raise ValueError(f"{path}: `cases` must be an array")
        for case in items:
            _case(case, str(path.relative_to(ROOT)))
            if case["case_id"] in seen:
                raise ValueError(f"duplicate differential case ID: {case['case_id']}")
            seen.add(case["case_id"])
            cases.append(case)
    return cases


def _iso_seconds(value: datetime) -> str:
    return value.astimezone(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def generate_cases(count: int, seed: int) -> list[dict[str, Any]]:
    """Generate deterministic, replayable cases. `count` is cases per family."""
    rng = random.Random(seed)
    generated: list[dict[str, Any]] = []
    base = datetime(2026, 1, 1, tzinfo=UTC)
    for i in range(count):
        generated.extend(
            [
                {
                    "case_id": f"generated-{seed}-canonical-{i:04d}",
                    "operation": "canonical_json",
                    "input": {"value": {"i": i, "flag": i % 2 == 0, "nested": [seed, f"v-{i}"]}},
                    "comparison": {"mode": "exact"},
                },
                {
                    "case_id": f"generated-{seed}-identity-{i:04d}",
                    "operation": "identity",
                    "input": {
                        "kind": "generated",
                        "parts": ["qedty", f"item-{i}", rng.randrange(0, 1_000_000)],
                        "length": 32,
                    },
                    "comparison": {"mode": "exact"},
                },
                {
                    "case_id": f"generated-{seed}-quantity-{i:04d}",
                    "operation": "quantity.convert",
                    "input": {
                        "value": str(rng.randrange(-1_000_000, 1_000_001) / 4),
                        "from_unit": "km",
                        "to_unit": "m",
                    },
                    "comparison": {
                        "mode": "numeric",
                        "absolute_tolerance": 1e-8,
                        "relative_tolerance": 1e-12,
                    },
                },
                {
                    "case_id": f"generated-{seed}-geometry-{i:04d}",
                    "operation": "geometry.ecef",
                    "input": {
                        "latitude_deg": rng.uniform(-90.0, 90.0),
                        "longitude_deg": rng.uniform(-180.0, 180.0),
                        "height_m": rng.uniform(-1000.0, 10000.0),
                    },
                    "comparison": {
                        "mode": "vector_tolerance",
                        "absolute_tolerance": 2e-6,
                        "relative_tolerance": 0.0,
                    },
                },
                {
                    "case_id": f"generated-{seed}-time-{i:04d}",
                    "operation": "time.normalize",
                    "input": {
                        "timestamp": _iso_seconds(
                            base + timedelta(seconds=i * 7919 + rng.randrange(0, 3000))
                        )
                    },
                    "comparison": {"mode": "exact"},
                },
            ]
        )
    return generated


def _compare_values(
    case: dict[str, Any], left: Any, right: Any, *, labels: tuple[str, str]
) -> str | None:
    mode = case["comparison"]["mode"]
    if mode == "exact":
        if left == right:
            return None
        return f"exact mismatch: {labels[0]}={left!r}, {labels[1]}={right!r}"

    abs_tol = float(case["comparison"].get("absolute_tolerance", 0.0))
    rel_tol = float(case["comparison"].get("relative_tolerance", 0.0))
    if mode == "numeric":
        try:
            pairs = [(float(left), float(right))]
        except (TypeError, ValueError) as exc:
            return (
                f"numeric comparator received non-numeric result: {exc}; "
                f"{labels[0]}={left!r}, {labels[1]}={right!r}"
            )
    else:
        if not isinstance(left, list) or not isinstance(right, list) or len(left) != len(right):
            return f"vector shape mismatch: {labels[0]}={left!r}, {labels[1]}={right!r}"
        try:
            pairs = [(float(a), float(b)) for a, b in zip(left, right, strict=True)]
        except (TypeError, ValueError) as exc:
            return f"vector comparator received non-numeric item: {exc}"

    for index, (a, b) in enumerate(pairs):
        if not math.isfinite(a) or not math.isfinite(b):
            return (
                f"non-finite numerical result at component {index}: "
                f"{labels[0]}={a}, {labels[1]}={b}"
            )
        allowed = abs_tol + rel_tol * abs(a)
        if abs(a - b) > allowed:
            return (
                f"tolerance mismatch at component {index}: {labels[0]}={a:.17g}, "
                f"{labels[1]}={b:.17g}, delta={abs(a - b):.17g}, allowed={allowed:.17g}"
            )
    return None


def _compare(case: dict[str, Any], reference: dict[str, Any], native: dict[str, Any]) -> str | None:
    expected_error = case.get("expected_error")
    if expected_error is not None:
        if reference.get("ok") is not False:
            return f"expected Python error {expected_error!r}, got success"
        if native.get("ok") is not False:
            return f"expected Rust error {expected_error!r}, got success"
        ref_category = reference.get("error", {}).get("category")
        rust_category = native.get("error", {}).get("category")
        if ref_category != expected_error or rust_category != expected_error:
            return (
                f"error category mismatch: expected={expected_error!r}, "
                f"Python={ref_category!r}, Rust={rust_category!r}; "
                f"Python error={reference.get('error')}; Rust error={native.get('error')}"
            )
        return None

    if reference.get("ok") is not True or native.get("ok") is not True:
        return f"unexpected error: Python={reference.get('error')}; Rust={native.get('error')}"

    left, right = reference.get("result"), native.get("result")
    if "expected_result" in case:
        expected = case["expected_result"]
        oracle_mismatch = _compare_values(case, left, expected, labels=("Python", "expected"))
        if oracle_mismatch is not None:
            return f"Python oracle mismatch: {oracle_mismatch}"
        oracle_mismatch = _compare_values(case, right, expected, labels=("Rust", "expected"))
        if oracle_mismatch is not None:
            return f"Rust oracle mismatch: {oracle_mismatch}"
    return _compare_values(case, left, right, labels=("Python", "Rust"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--cases-dir", type=Path, default=ROOT / "data/contracts/differential/cases"
    )
    parser.add_argument(
        "--generated-count",
        type=int,
        default=64,
        help="deterministic cases per generated family; 0 disables generation",
    )
    parser.add_argument("--seed", type=int, default=20261010)
    parser.add_argument("--timeout", type=int, default=240)
    args = parser.parse_args()
    if not 0 <= args.generated_count <= 10_000:
        parser.error("--generated-count must be between 0 and 10000")
    if args.timeout <= 0:
        parser.error("--timeout must be positive")

    try:
        cases = load_cases(args.cases_dir)
        generated = generate_cases(args.generated_count, args.seed)
        seen = {case["case_id"] for case in cases}
        duplicate_generated = seen.intersection(case["case_id"] for case in generated)
        if duplicate_generated:
            raise ValueError(
                f"generated cases collide with fixture IDs: {sorted(duplicate_generated)[:3]}"
            )
        cases.extend(generated)
    except Exception as error:  # malformed fixtures must fail with a clear report.
        print(f"ERROR: differential case validation failed: {error}", file=sys.stderr)
        return 2

    command_text = os.environ.get("QEDTY_DIFFERENTIAL_RUST_COMMAND")
    command = shlex.split(command_text) if command_text else DEFAULT_RUST_COMMAND
    requests = [
        {"case_id": case["case_id"], "operation": case["operation"], "input": case["input"]}
        for case in cases
    ]
    payload = "".join(
        json.dumps(item, ensure_ascii=False, separators=(",", ":"), allow_nan=False) + "\n"
        for item in requests
    )
    try:
        process = subprocess.run(
            command,
            input=payload,
            text=True,
            capture_output=True,
            cwd=ROOT,
            timeout=args.timeout,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        print(f"ERROR: could not execute Rust differential runner: {error}", file=sys.stderr)
        print(f"Command: {shlex.join(command)}", file=sys.stderr)
        return 2

    if process.returncode != 0:
        print(f"ERROR: Rust runner exited {process.returncode}", file=sys.stderr)
        if process.stderr:
            print(process.stderr[-12000:], file=sys.stderr)
        return 2
    responses: list[dict[str, Any]] = []
    for line_number, line in enumerate(process.stdout.splitlines(), start=1):
        try:
            item = json.loads(line)
        except json.JSONDecodeError as error:
            print(
                f"ERROR: Rust runner emitted non-JSON stdout on line {line_number}: "
                f"{line!r} ({error})",
                file=sys.stderr,
            )
            if process.stderr:
                print(process.stderr[-6000:], file=sys.stderr)
            return 2
        if not isinstance(item, dict):
            print(f"ERROR: Rust response line {line_number} must be a JSON object", file=sys.stderr)
            return 2
        if not isinstance(item.get("ok"), bool):
            print(
                f"ERROR: Rust response line {line_number} lacks boolean `ok`",
                file=sys.stderr,
            )
            return 2
        if item["ok"] and "result" not in item:
            print(
                f"ERROR: Rust success response line {line_number} lacks `result`",
                file=sys.stderr,
            )
            return 2
        if not item["ok"]:
            error = item.get("error")
            if not isinstance(error, dict) or not isinstance(error.get("category"), str):
                print(
                    f"ERROR: Rust error response line {line_number} lacks an error category",
                    file=sys.stderr,
                )
                return 2
        responses.append(item)
    if len(responses) != len(cases):
        print(
            f"ERROR: protocol response count mismatch: cases={len(cases)}, "
            f"Rust responses={len(responses)}",
            file=sys.stderr,
        )
        if process.stderr:
            print(process.stderr[-6000:], file=sys.stderr)
        return 2

    failures: list[tuple[str, str]] = []
    passed = 0
    operation_totals: dict[str, list[int]] = {}
    for case, response in zip(cases, responses, strict=True):
        case_id = case["case_id"]
        operation_totals.setdefault(case["operation"], [0, 0])
        operation_totals[case["operation"]][1] += 1
        if response.get("case_id") != case_id:
            failure = (
                f"protocol case_id mismatch: expected {case_id!r}, got {response.get('case_id')!r}"
            )
        else:
            reference = evaluate_reference(case["operation"], case["input"])
            failure = _compare(case, reference, response)
        if failure is None:
            passed += 1
            operation_totals[case["operation"]][0] += 1
        else:
            failures.append((case_id, failure))
            print(f"FAIL {case_id}: {failure}", file=sys.stderr)

    print(
        f"QEDTY Python–Rust differential result: {passed}/{len(cases)} cases passed; "
        f"seed={args.seed}; generated_per_family={args.generated_count}"
    )
    for operation, (ok_count, total) in sorted(operation_totals.items()):
        print(f"  {operation}: {ok_count}/{total}")
    if failures:
        print(
            f"FAILED: {len(failures)} mismatch(es). "
            "Promote each confirmed mismatch to a fixed regression case.",
            file=sys.stderr,
        )
        return 1
    print(
        "PASS: no unexpected skips; Python and Rust matched under each case's "
        "declared comparison contract."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
