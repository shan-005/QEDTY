from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RUNNER_PATH = ROOT / "scripts" / "check_python_rust_differential.py"

# Load the runner by its file path. This avoids relying on pytest adding
# the repository root to sys.path or treating scripts/ as an import package.
RUNNER_SPEC = importlib.util.spec_from_file_location("_qedty_differential_runner", RUNNER_PATH)
if RUNNER_SPEC is None or RUNNER_SPEC.loader is None:
    raise ImportError(f"Cannot load differential runner: {RUNNER_PATH}")

RUNNER = importlib.util.module_from_spec(RUNNER_SPEC)
sys.modules[RUNNER_SPEC.name] = RUNNER
RUNNER_SPEC.loader.exec_module(RUNNER)

SUPPORTED_OPERATIONS = RUNNER.SUPPORTED_OPERATIONS
_compare_values = RUNNER._compare_values
evaluate_reference = RUNNER.evaluate_reference
generate_cases = RUNNER.generate_cases
load_cases = RUNNER.load_cases
CASE_DIR = ROOT / "data" / "contracts" / "differential" / "cases"


def test_fixed_case_inventory_is_well_formed_and_unique() -> None:
    cases = load_cases(CASE_DIR)
    assert len(cases) >= 30
    assert len({case["case_id"] for case in cases}) == len(cases)
    assert {case["operation"] for case in cases} == SUPPORTED_OPERATIONS


def test_python_reference_satisfies_declared_fixed_cases() -> None:
    cases = load_cases(CASE_DIR)
    failures: list[str] = []
    for case in cases:
        actual = evaluate_reference(case["operation"], case["input"])
        expected_error = case.get("expected_error")
        if expected_error is not None:
            if (
                actual.get("ok") is not False
                or actual.get("error", {}).get("category") != expected_error
            ):
                failures.append(
                    f"{case['case_id']}: expected error {expected_error!r}, got {actual}"
                )
        elif actual.get("ok") is not True:
            failures.append(f"{case['case_id']}: unexpected Python reference error: {actual}")
        elif "expected_result" in case:
            mismatch = _compare_values(
                case,
                actual.get("result"),
                case["expected_result"],
                labels=("Python", "expected"),
            )
            if mismatch is not None:
                failures.append(f"{case['case_id']}: {mismatch}")
    assert not failures, "\n".join(failures)


def test_all_thirteen_allen_relations_are_represented() -> None:
    cases = load_cases(CASE_DIR)
    relation_cases = [case for case in cases if case["operation"] == "temporal.relation"]
    assert len(relation_cases) == 13
    assert {case.get("expected_result") for case in relation_cases} == {
        "before",
        "meets",
        "overlaps",
        "starts",
        "during",
        "finishes",
        "equals",
        "finished_by",
        "contains",
        "started_by",
        "overlapped_by",
        "met_by",
        "after",
    }


def test_numeric_tolerances_are_finite_and_non_negative() -> None:
    cases = load_cases(CASE_DIR)
    numeric = [case for case in cases if case["comparison"]["mode"] != "exact"]
    assert numeric
    for case in numeric:
        for key in ("absolute_tolerance", "relative_tolerance"):
            value = case["comparison"][key]
            assert isinstance(value, (int, float)) and not isinstance(value, bool)
            assert value >= 0 and value < float("inf"), (case["case_id"], key, value)


def test_case_schema_version_and_expected_error_placement() -> None:
    for path in sorted(CASE_DIR.glob("*.json")):
        doc = json.loads(path.read_text(encoding="utf-8"))
        assert doc["schema_version"] == "qedty-differential-cases@1"
        for case in doc["cases"]:
            assert "expected_error" not in case["comparison"]
            if "expected_error" in case:
                assert isinstance(case["expected_error"], str)


def test_generated_cases_are_reproducible_and_cover_five_families() -> None:
    first = generate_cases(8, 20261010)
    second = generate_cases(8, 20261010)
    assert first == second
    assert len(first) == 40
    assert len({case["case_id"] for case in first}) == len(first)
    assert {case["operation"] for case in first} == {
        "canonical_json",
        "identity",
        "quantity.convert",
        "geometry.ecef",
        "time.normalize",
    }
