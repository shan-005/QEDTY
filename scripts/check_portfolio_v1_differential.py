#!/usr/bin/env python3
"""Direct Python/Rust conformance for QEDTY's legacy USD portfolio v1 kernels.

Python is the semantic reference. The Rust executable is a deterministic
numeric/selection kernel only; CounterfactualEngine and ResilienceOptimizer
application orchestration remain Python-owned.
"""

from __future__ import annotations

import argparse
import json
import math
import random
import shlex
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from qedty.optimization.constraints import BudgetConstraint, feasible  # noqa: E402
from qedty.optimization.objectives import cvar, efficiency, weighted_score  # noqa: E402
from qedty.optimization.portfolio import select_portfolio  # noqa: E402
from qedty.optimization.robustness import (  # noqa: E402
    cvar_score,
    dominance_score,
    robust_floor,
)

DEFAULT_RUST_COMMAND = [
    "cargo",
    "run",
    "--locked",
    "--quiet",
    "-p",
    "qedty-conformance",
    "--bin",
    "qedty-portfolio-v1-differential",
]


@dataclass(frozen=True, slots=True)
class _ReferenceItem:
    intervention_id: str
    cost_usd: float
    efficiency: float


def _selection_case(case_id: str, budget_usd: float, items: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "case_id": case_id,
        "operation": "portfolio.select.v1",
        "input": {"budget_usd": budget_usd, "items": items},
    }


def _helper_case(case_id: str, function: str, **values: Any) -> dict[str, Any]:
    return {
        "case_id": case_id,
        "operation": "portfolio.helper.v1",
        "input": {"function": function, **values},
    }


def _portfolio_reference(data: dict[str, Any]) -> dict[str, Any]:
    raw_budget = data.get("budget_usd")
    if (
        isinstance(raw_budget, bool)
        or not isinstance(raw_budget, (int, float))
        or not math.isfinite(float(raw_budget))
    ):
        raise ValueError("budget_usd must be a finite JSON number")

    raw_items = data.get("items")
    if not isinstance(raw_items, list):
        raise ValueError("items must be an array")

    items: list[_ReferenceItem] = []
    for raw in raw_items:
        if not isinstance(raw, dict):
            raise ValueError("each item must be an object")
        intervention_id = raw.get("intervention_id")
        cost_usd = raw.get("cost_usd")
        item_efficiency = raw.get("efficiency")
        if not isinstance(intervention_id, str):
            raise ValueError("intervention_id must be a string")
        if (
            isinstance(cost_usd, bool)
            or not isinstance(cost_usd, (int, float))
            or not math.isfinite(float(cost_usd))
        ):
            raise ValueError("cost_usd must be a finite JSON number")
        if (
            isinstance(item_efficiency, bool)
            or not isinstance(item_efficiency, (int, float))
            or not math.isfinite(float(item_efficiency))
        ):
            raise ValueError("efficiency must be a finite JSON number")
        items.append(
            _ReferenceItem(
                intervention_id=intervention_id,
                cost_usd=float(cost_usd),
                efficiency=float(item_efficiency),
            )
        )

    result = select_portfolio(items, data["budget_usd"])
    return {
        "selected_intervention_ids": list(result.selected_intervention_ids),
        "spent_usd": result.spent_usd,
        "objective_value": result.objective_value,
        "solver_mode": result.solver_mode,
        "status": result.status,
    }


def _helper_reference(data: dict[str, Any]) -> Any:
    function = data.get("function")

    if function == "efficiency":
        return efficiency(data["gain"], data["cost_usd"])
    if function == "weighted_score":
        return weighted_score(
            data["gain"],
            data["cost_usd"],
            data.get("risk", 0.0),
            gain_weight=data.get("gain_weight", 1.0),
            cost_weight=data.get("cost_weight", 1.0),
            risk_weight=data.get("risk_weight", 1.0),
        )
    if function == "cvar":
        return cvar([float(score) for score in data["scores"]], data.get("alpha", 0.9))
    if function == "robust_floor":
        return robust_floor([float(score) for score in data["scores"]])
    if function == "cvar_score":
        return cvar_score([float(score) for score in data["scores"]], data.get("alpha", 0.9))
    if function == "dominance_score":
        return dominance_score([float(score) for score in data["scores"]])
    if function == "budget_permits":
        constraint = BudgetConstraint(
            budget_usd=data["budget_usd"],
            fixed_overhead_usd=data.get("fixed_overhead_usd", 0.0),
        )
        return constraint.permits(
            data["cost_usd"],
            data.get("spent_usd", 0.0),
        )
    if function == "feasible":
        return feasible(
            SimpleNamespace(cost_usd=data["cost_usd"]),
            data["budget_usd"],
        )
    raise ValueError(f"unsupported portfolio helper: {function}")


def _python_error_category(case: dict[str, Any], error: Exception) -> str:
    message = str(error).casefold()
    if case["operation"] == "portfolio.select.v1":
        if any(
            token in message
            for token in (
                "must be a finite json number",
                "items must be an array",
                "each item must be an object",
                "intervention_id must be a string",
            )
        ):
            return "invalid_input"
        if "budget" in message:
            return "invalid_budget"
        if "duplicate intervention_id" in message:
            return "duplicate_intervention_id"
        if "objective contribution" in message:
            return "non_finite_objective"
        return "invalid_item"

    function = case["input"].get("function")
    if function in {"efficiency", "weighted_score"}:
        return "invalid_objective_inputs"
    if function in {"cvar", "cvar_score"}:
        if "empty" in message:
            return "empty_scores"
        return "invalid_alpha"
    if function == "budget_permits":
        return "invalid_budget_constraint"
    return "invalid_input"


def evaluate_reference(case: dict[str, Any]) -> dict[str, Any]:
    try:
        if case["operation"] == "portfolio.select.v1":
            result = _portfolio_reference(case["input"])
        elif case["operation"] == "portfolio.helper.v1":
            result = _helper_reference(case["input"])
        else:
            raise ValueError("unsupported operation")
        return {"case_id": case["case_id"], "ok": True, "result": result}
    except (KeyError, TypeError, ValueError, OverflowError) as error:
        return {
            "case_id": case["case_id"],
            "ok": False,
            "error": {"category": _python_error_category(case, error)},
        }


def _fixed_cases() -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []

    cases.append(
        _selection_case(
            "portfolio-v1-exact-combination",
            8.0,
            [
                {"intervention_id": "a", "cost_usd": 5.0, "efficiency": 10.0},
                {"intervention_id": "b", "cost_usd": 7.0, "efficiency": 8.0},
                {"intervention_id": "c", "cost_usd": 3.0, "efficiency": 10.0},
            ],
        )
    )
    cases.append(
        _selection_case(
            "portfolio-v1-exact-zero-cost-is-omitted",
            0.0,
            [{"intervention_id": "free", "cost_usd": 0.0, "efficiency": 5.0}],
        )
    )
    cases.append(
        _selection_case(
            "portfolio-v1-tie-break-id",
            5.0,
            [
                {"intervention_id": "b", "cost_usd": 5.0, "efficiency": 10.0},
                {"intervention_id": "a", "cost_usd": 5.0, "efficiency": 10.0},
            ],
        )
    )
    cases.append(_selection_case("portfolio-v1-empty", 10.0, []))

    boundary_28 = [
        {
            "intervention_id": f"item-{index:02d}",
            "cost_usd": 10.0 if index == 0 else 11.0,
            "efficiency": float(28 - index),
        }
        for index in range(28)
    ]
    cases.append(_selection_case("portfolio-v1-28-exact-boundary", 10.0, boundary_28))

    boundary_29 = [
        {
            "intervention_id": f"item-{index:02d}",
            "cost_usd": 10.0 if index == 0 else 11.0,
            "efficiency": float(29 - index),
        }
        for index in range(29)
    ]
    cases.append(_selection_case("portfolio-v1-29-greedy-boundary", 10.0, boundary_29))
    cases.append(
        _selection_case(
            "portfolio-v1-29-zero-cost-greedy-behaviour",
            0.0,
            [
                {"intervention_id": f"free-{index:02d}", "cost_usd": 0.0, "efficiency": 1.0}
                for index in range(29)
            ],
        )
    )
    cases.append(
        _selection_case(
            "portfolio-v1-over-budget-items-still-count-toward-cutoff",
            10.0,
            [
                {
                    "intervention_id": f"too-costly-{index:02d}",
                    "cost_usd": 11.0,
                    "efficiency": 30.0 - index,
                }
                for index in range(29)
            ],
        )
    )

    cases.extend(
        [
            _selection_case("portfolio-v1-invalid-negative-budget", -1.0, []),
            _selection_case(
                "portfolio-v1-invalid-negative-cost",
                10.0,
                [{"intervention_id": "bad-cost", "cost_usd": -1.0, "efficiency": 1.0}],
            ),
            _selection_case(
                "portfolio-v1-invalid-negative-efficiency",
                10.0,
                [{"intervention_id": "bad-efficiency", "cost_usd": 1.0, "efficiency": -1.0}],
            ),
            _selection_case(
                "portfolio-v1-invalid-duplicate-id",
                10.0,
                [
                    {"intervention_id": "duplicate", "cost_usd": 1.0, "efficiency": 1.0},
                    {"intervention_id": "duplicate", "cost_usd": 2.0, "efficiency": 2.0},
                ],
            ),
        ]
    )

    cases.extend(
        [
            _helper_case(
                "portfolio-v1-efficiency-normal", "efficiency", gain=0.5, cost_usd=1_000_000.0
            ),
            _helper_case("portfolio-v1-efficiency-zero-cost", "efficiency", gain=5.0, cost_usd=0.0),
            _helper_case(
                "portfolio-v1-weighted-score",
                "weighted_score",
                gain=10.0,
                cost_usd=2_000_000.0,
                risk=1.0,
                gain_weight=1.0,
                cost_weight=1.0,
                risk_weight=1.0,
            ),
            _helper_case(
                "portfolio-v1-cvar-upper-tail-count", "cvar", scores=[1.0, 2.0, 3.0], alpha=0.9
            ),
            _helper_case(
                "portfolio-v1-cvar-negative-scores", "cvar", scores=[-5.0, -1.0, 4.0], alpha=0.5
            ),
            _helper_case(
                "portfolio-v1-neumaier-summation-cvar",
                "cvar",
                scores=[-1e16, 1.0, 1.0, 1e16],
                alpha=0.01,
            ),
            _helper_case(
                "portfolio-v1-neumaier-summation-dominance",
                "dominance_score",
                scores=[-1e16, 1.0, 1.0, 1e16],
            ),
            _helper_case("portfolio-v1-cvar-empty-rejected", "cvar", scores=[], alpha=0.9),
            _helper_case("portfolio-v1-cvar-invalid-alpha", "cvar", scores=[1.0], alpha=1.0),
            _helper_case("portfolio-v1-robust-floor", "robust_floor", scores=[0.2, 0.8, 0.5]),
            _helper_case("portfolio-v1-robust-floor-empty", "robust_floor", scores=[]),
            _helper_case("portfolio-v1-cvar-score-empty", "cvar_score", scores=[], alpha=0.9),
            _helper_case(
                "portfolio-v1-cvar-score-normal", "cvar_score", scores=[0.2, 0.8, 0.5], alpha=0.5
            ),
            _helper_case("portfolio-v1-dominance-score", "dominance_score", scores=[2.0, 2.0]),
            _helper_case("portfolio-v1-dominance-score-empty", "dominance_score", scores=[]),
            _helper_case(
                "portfolio-v1-budget-permits-with-overhead",
                "budget_permits",
                budget_usd=100.0,
                fixed_overhead_usd=10.0,
                cost_usd=80.0,
                spent_usd=0.0,
            ),
            _helper_case(
                "portfolio-v1-budget-permits-exceeds",
                "budget_permits",
                budget_usd=100.0,
                fixed_overhead_usd=10.0,
                cost_usd=91.0,
                spent_usd=0.0,
            ),
            _helper_case(
                "portfolio-v1-budget-permits-negative-cost",
                "budget_permits",
                budget_usd=100.0,
                fixed_overhead_usd=0.0,
                cost_usd=-1.0,
                spent_usd=0.0,
            ),
            _helper_case(
                "portfolio-v1-budget-invalid-overhead",
                "budget_permits",
                budget_usd=100.0,
                fixed_overhead_usd=-1.0,
                cost_usd=1.0,
                spent_usd=0.0,
            ),
            _helper_case(
                "portfolio-v1-feasible-at-budget",
                "feasible",
                budget_usd=10.0,
                cost_usd=10.0,
            ),
            _helper_case(
                "portfolio-v1-feasible-over-budget",
                "feasible",
                budget_usd=10.0,
                cost_usd=10.01,
            ),
            _helper_case(
                "portfolio-v1-feasible-negative-cost",
                "feasible",
                budget_usd=10.0,
                cost_usd=-1.0,
            ),
            _helper_case(
                "portfolio-v1-efficiency-invalid-negative-gain",
                "efficiency",
                gain=-1.0,
                cost_usd=1.0,
            ),
            _helper_case(
                "portfolio-v1-weighted-score-invalid-negative-weight",
                "weighted_score",
                gain=1.0,
                cost_usd=1.0,
                risk=0.0,
                gain_weight=-1.0,
                cost_weight=1.0,
                risk_weight=1.0,
            ),
        ]
    )
    return cases


def generate_cases(count: int, seed: int) -> list[dict[str, Any]]:
    rng = random.Random(seed)
    cases: list[dict[str, Any]] = _fixed_cases()

    exact_rng = random.Random(seed ^ 0xA17E2026)
    for index in range(count):
        size = exact_rng.randrange(0, 17)
        items = [
            {
                "intervention_id": f"e{index:03d}-{item_index:02d}",
                "cost_usd": float(exact_rng.randrange(0, 101)),
                "efficiency": round(exact_rng.uniform(0.0, 25.0), 8),
            }
            for item_index in range(size)
        ]
        cases.append(
            _selection_case(
                f"portfolio-v1-generated-exact-{index:04d}",
                float(exact_rng.randrange(0, 301)),
                items,
            )
        )

    fallback_rng = random.Random(seed ^ 0x29FA11B0)
    for index in range(count):
        size = 29 + fallback_rng.randrange(0, 12)
        items = [
            {
                "intervention_id": f"g{index:03d}-{item_index:02d}",
                "cost_usd": float(fallback_rng.randrange(0, 101)),
                "efficiency": round(fallback_rng.uniform(0.0, 25.0), 8),
            }
            for item_index in range(size)
        ]
        cases.append(
            _selection_case(
                f"portfolio-v1-generated-fallback-{index:04d}",
                float(fallback_rng.randrange(0, 301)),
                items,
            )
        )

    for index in range(count):
        cases.append(
            _helper_case(
                f"portfolio-v1-generated-efficiency-{index:04d}",
                "efficiency",
                gain=round(rng.uniform(0.0, 100.0), 9),
                cost_usd=0.0 if index % 9 == 0 else float(rng.randrange(1, 2_000_001)),
            )
        )
        cases.append(
            _helper_case(
                f"portfolio-v1-generated-weighted-score-{index:04d}",
                "weighted_score",
                gain=round(rng.uniform(0.0, 100.0), 9),
                cost_usd=float(rng.randrange(0, 2_000_001)),
                risk=round(rng.uniform(0.0, 10.0), 9),
                gain_weight=round(rng.uniform(0.0, 3.0), 9),
                cost_weight=round(rng.uniform(0.0, 3.0), 9),
                risk_weight=round(rng.uniform(0.0, 3.0), 9),
            )
        )
        scores = [round(rng.uniform(-100.0, 100.0), 9) for _ in range(rng.randrange(1, 25))]
        alpha = rng.choice((0.1, 0.25, 0.5, 0.75, 0.9, 0.95))
        cases.append(
            _helper_case(
                f"portfolio-v1-generated-cvar-{index:04d}", "cvar", scores=scores, alpha=alpha
            )
        )
        cases.append(
            _helper_case(
                f"portfolio-v1-generated-robust-floor-{index:04d}", "robust_floor", scores=scores
            )
        )
        cases.append(
            _helper_case(
                f"portfolio-v1-generated-cvar-score-{index:04d}",
                "cvar_score",
                scores=scores,
                alpha=alpha,
            )
        )
        cases.append(
            _helper_case(
                f"portfolio-v1-generated-dominance-{index:04d}", "dominance_score", scores=scores
            )
        )
        cases.append(
            _helper_case(
                f"portfolio-v1-generated-budget-permits-{index:04d}",
                "budget_permits",
                budget_usd=float(rng.randrange(0, 501)),
                fixed_overhead_usd=float(rng.randrange(0, 51)),
                cost_usd=float(rng.randrange(0, 501)),
                spent_usd=float(rng.randrange(0, 101)),
            )
        )
        cases.append(
            _helper_case(
                f"portfolio-v1-generated-feasible-{index:04d}",
                "feasible",
                budget_usd=float(rng.randrange(0, 501)),
                cost_usd=float(rng.randrange(0, 501)),
            )
        )

    return cases


def _exhaustive_portfolio_oracle(data: dict[str, Any]) -> dict[str, Any]:
    """Independent exhaustive oracle for small exact v1 portfolios.

    This deliberately does not call select_portfolio or reuse its branch-and-bound
    pruning. It enumerates every feasible subset, preserving the v1 candidate
    ordering and tie rule, so shared implementation defects are less likely to
    pass the direct Python/Rust comparison unnoticed.
    """

    ordered = sorted(
        data["items"],
        key=lambda item: (-float(item["efficiency"]), item["intervention_id"]),
    )
    budget = float(data["budget_usd"])
    best_value = -1.0
    best_ids: tuple[str, ...] = ()
    best_spent = 0.0

    for mask in range(1 << len(ordered)):
        selected_ids: list[str] = []
        spent = 0.0
        objective_value = 0.0
        feasible_subset = True

        for index, item in enumerate(ordered):
            if not (mask & (1 << index)):
                continue
            cost = float(item["cost_usd"])
            if spent + cost > budget:
                feasible_subset = False
                break
            spent += cost
            objective_value += max(
                0.0,
                float(item["efficiency"]) * cost / 1_000_000.0,
            )
            selected_ids.append(item["intervention_id"])

        if not feasible_subset:
            continue

        candidate_ids = tuple(selected_ids)
        if objective_value > best_value or (
            objective_value == best_value and candidate_ids < best_ids
        ):
            best_value = objective_value
            best_ids = candidate_ids
            best_spent = spent

    return {
        "selected_intervention_ids": list(best_ids),
        "spent_usd": best_spent,
        "objective_value": best_value,
        "solver_mode": "exact_branch_and_bound",
        "status": "optimal_reference",
    }


def _equivalent(expected: Any, actual: Any, path: str = "result") -> tuple[bool, str]:
    if isinstance(expected, bool) or isinstance(actual, bool):
        return (expected is actual, f"{path}: expected {expected!r}, got {actual!r}")

    if isinstance(expected, (int, float)) and isinstance(actual, (int, float)):
        equal = math.isclose(float(expected), float(actual), rel_tol=1e-12, abs_tol=1e-12)
        return (equal, f"{path}: expected {expected!r}, got {actual!r}")

    if isinstance(expected, dict) and isinstance(actual, dict):
        if expected.keys() != actual.keys():
            return (False, f"{path}: object keys differ: {expected.keys()} vs {actual.keys()}")
        for key in expected:
            equal, reason = _equivalent(expected[key], actual[key], f"{path}.{key}")
            if not equal:
                return False, reason
        return True, ""

    if isinstance(expected, list) and isinstance(actual, list):
        if len(expected) != len(actual):
            return (False, f"{path}: list lengths differ: {len(expected)} vs {len(actual)}")
        for index, (left, right) in enumerate(zip(expected, actual, strict=True)):
            equal, reason = _equivalent(left, right, f"{path}[{index}]")
            if not equal:
                return False, reason
        return True, ""

    return (expected == actual, f"{path}: expected {expected!r}, got {actual!r}")


def compare_case(case: dict[str, Any], actual: dict[str, Any]) -> tuple[bool, str]:
    expected = evaluate_reference(case)
    if expected.get("case_id") != actual.get("case_id"):
        return (
            False,
            f"case id mismatch: expected {expected.get('case_id')!r}, got {actual.get('case_id')!r}",
        )
    if expected.get("ok") is not actual.get("ok"):
        return (
            False,
            f"{case['case_id']}: Python/Rust success state differs: {expected} vs {actual}",
        )
    if expected["ok"] is False:
        return _equivalent(expected.get("error"), actual.get("error"), "error")
    return _equivalent(expected.get("result"), actual.get("result"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--generated-count", type=int, default=64)
    parser.add_argument("--seed", type=int, default=20261124)
    parser.add_argument("--timeout", type=int, default=240)
    parser.add_argument(
        "--rust-command", default=None, help="optional shell-quoted replacement command"
    )
    args = parser.parse_args()

    if not 0 <= args.generated_count <= 10_000:
        parser.error("--generated-count must be between 0 and 10000")
    if args.timeout <= 0:
        parser.error("--timeout must be positive")

    cases = generate_cases(args.generated_count, args.seed)
    case_ids = [case["case_id"] for case in cases]
    if len(case_ids) != len(set(case_ids)):
        print("ERROR: duplicate case IDs in portfolio v1 differential suite", file=sys.stderr)
        return 2

    command = shlex.split(args.rust_command) if args.rust_command else DEFAULT_RUST_COMMAND
    payload = "".join(
        json.dumps(case, ensure_ascii=False, allow_nan=False, separators=(",", ":")) + "\n"
        for case in cases
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
        print(f"ERROR: could not execute portfolio v1 Rust runner: {error}", file=sys.stderr)
        print(f"Command: {shlex.join(command)}", file=sys.stderr)
        return 2

    if process.returncode != 0:
        print(f"ERROR: portfolio v1 Rust runner exited {process.returncode}", file=sys.stderr)
        if process.stderr:
            print(process.stderr[-12000:], file=sys.stderr)
        return 2

    raw_lines = process.stdout.splitlines()
    if len(raw_lines) != len(cases):
        print(
            f"ERROR: expected {len(cases)} Rust response lines, received {len(raw_lines)}",
            file=sys.stderr,
        )
        if process.stderr:
            print(process.stderr[-12000:], file=sys.stderr)
        return 2

    counts: dict[str, int] = {}
    for index, (case, line) in enumerate(zip(cases, raw_lines, strict=True), start=1):
        try:
            actual = json.loads(line)
        except json.JSONDecodeError as error:
            print(f"ERROR: invalid Rust JSON response at line {index}: {error}", file=sys.stderr)
            print(repr(line), file=sys.stderr)
            return 2

        reference = evaluate_reference(case)
        if (
            case["operation"] == "portfolio.select.v1"
            and reference.get("ok") is True
            and len(case["input"]["items"]) <= 16
        ):
            oracle = _exhaustive_portfolio_oracle(case["input"])
            oracle_equal, oracle_reason = _equivalent(reference["result"], oracle)
            if not oracle_equal:
                print(
                    f"FAIL: {case['case_id']} (Python reference vs exhaustive oracle)",
                    file=sys.stderr,
                )
                print(oracle_reason, file=sys.stderr)
                print(f"Python:   {reference['result']}", file=sys.stderr)
                print(f"Exhaustive: {oracle}", file=sys.stderr)
                return 1

        equal, reason = compare_case(case, actual)
        if not equal:
            print(f"FAIL: {case['case_id']} ({case['operation']})", file=sys.stderr)
            print(reason, file=sys.stderr)
            print(f"Python: {evaluate_reference(case)}", file=sys.stderr)
            print(f"Rust:   {actual}", file=sys.stderr)
            if process.stderr:
                print(process.stderr[-12000:], file=sys.stderr)
            return 1
        counts[case["operation"]] = counts.get(case["operation"], 0) + 1

    total = sum(counts.values())
    print(
        f"QEDTY portfolio v1 Python-Rust differential: {total}/{total} cases passed; seed={args.seed}"
    )
    for operation, count in sorted(counts.items()):
        print(f"  {operation}: {count}/{count}")
    print("PASS: Python v1 portfolio kernels and Rust matched every declared case.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
