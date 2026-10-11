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
    assert len(relation_cases) >= 13
    assert {
        case.get("expected_result") for case in relation_cases if "expected_result" in case
    } == {
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


def test_generated_cases_are_reproducible_and_cover_eight_families() -> None:
    first = generate_cases(8, 20261010)
    second = generate_cases(8, 20261010)
    assert first == second
    assert len(first) == 64
    assert len({case["case_id"] for case in first}) == len(first)
    assert {case["operation"] for case in first} == {
        "canonical_json",
        "identity",
        "quantity.convert",
        "geometry.ecef",
        "time.normalize",
        "interval.contains",
        "temporal.relation",
        "graph.static.bfs",
    }


def test_generated_temporal_cases_cover_all_relations_and_membership_boundaries() -> None:
    generated = generate_cases(64, 20261010)
    relation_cases = [case for case in generated if case["operation"] == "temporal.relation"]
    membership_cases = [case for case in generated if case["operation"] == "interval.contains"]
    assert len(relation_cases) == 64
    assert len(membership_cases) == 64
    actual_relations = {
        evaluate_reference(case["operation"], case["input"])["result"] for case in relation_cases
    }
    assert actual_relations == {
        "before",
        "meets",
        "overlaps",
        "starts",
        "during",
        "finishes",
        "equals",
        "started_by",
        "contains",
        "finished_by",
        "overlapped_by",
        "met_by",
        "after",
    }
    membership_results = {
        evaluate_reference(case["operation"], case["input"])["result"] for case in membership_cases
    }
    assert membership_results == {True, False}
    graph_cases = [case for case in generated if case["operation"] == "graph.static.bfs"]
    assert len(graph_cases) == 64
    for case in graph_cases:
        result = evaluate_reference(case["operation"], case["input"])
        assert result["ok"] is True
        assert case["input"]["source"] not in result["result"]
        assert len(result["result"]) == len(set(result["result"]))


def test_temporal_boundary_regression_cases_are_present() -> None
    cases = load_cases(CASE_DIR)
    by_id = {case["case_id"]: case for case in cases}
    timestamp_ids = {
        "time-offset-crosses-previous-year-001",
        "time-offset-crosses-next-year-001",
        "time-max-positive-offset-001",
        "time-max-negative-offset-001",
        "time-min-year-valid-001",
        "time-max-year-valid-001",
        "time-invalid-leap-day-001",
        "time-invalid-leap-second-001",
        "time-invalid-offset-hours-001",
        "time-invalid-offset-minutes-001",
        "time-utc-underflow-year-boundary-001",
        "time-utc-overflow-year-boundary-001",
        "time-year-zero-invalid-001",
    }
    interval_ids = {
        "interval-start-inclusive-boundary-001",
        "interval-end-exclusive-boundary-001",
        "interval-lower-unbounded-inside-001",
        "interval-upper-unbounded-inside-001",
        "interval-lower-unbounded-at-end-001",
        "interval-upper-unbounded-before-start-001",
        "interval-reversed-endpoints-001",
    }
    assert (timestamp_ids | interval_ids).issubset(by_id)
    assert {by_id[case_id]["operation"] for case_id in timestamp_ids} == {"time.normalize"}
    assert {by_id[case_id]["operation"] for case_id in interval_ids} == {"interval.contains"}


def test_allen_inverse_relations_have_swapped_input_fixed_cases() -> None:
    inverse_relations = {
        "before": "after",
        "meets": "met_by",
        "overlaps": "overlapped_by",
        "starts": "started_by",
        "during": "contains",
        "finishes": "finished_by",
        "equals": "equals",
        "finished_by": "finishes",
        "contains": "during",
        "started_by": "starts",
        "overlapped_by": "overlaps",
        "met_by": "meets",
        "after": "before",
    }
    cases = load_cases(CASE_DIR)
    by_id = {case["case_id"]: case for case in cases}
    expected_inverse_ids = {
        f"allen-{relation.replace('_', '-')}-inverse-001" for relation in inverse_relations
    }
    actual_inverse_ids = {
        case["case_id"] for case in cases if case["case_id"].endswith("-inverse-001")
    }
    assert actual_inverse_ids == expected_inverse_ids

    for relation, expected_inverse in inverse_relations.items():
        stem = f"allen-{relation.replace('_', '-')}"
        original = by_id[f"{stem}-001"]
        swapped = by_id[f"{stem}-inverse-001"]
        assert original["expected_result"] == relation
        assert swapped["expected_result"] == expected_inverse
        assert swapped["operation"] == "temporal.relation"
        assert swapped["input"] == {
            "left": original["input"]["right"],
            "right": original["input"]["left"],
        }


def test_equivalent_instant_representations_normalize_identically() -> None:
    cases = {case["case_id"]: case for case in load_cases(CASE_DIR)}
    pairs = (
        ("time-equivalent-offset-plus0530-001", "time-equivalent-offset-utc-001"),
        ("time-equivalent-offset-minus1200-001", "time-equivalent-offset-utc-noon-001"),
    )
    for left_id, right_id in pairs:
        left = evaluate_reference(cases[left_id]["operation"], cases[left_id]["input"])
        right = evaluate_reference(cases[right_id]["operation"], cases[right_id]["input"])
        assert left["ok"] is right["ok"] is True
        assert left["result"] == right["result"]
        assert left["result"] == cases[left_id]["expected_result"]
        assert right["result"] == cases[right_id]["expected_result"]


def test_equal_and_reversed_windows_after_utc_normalization_are_rejected() -> None:
    cases = {case["case_id"]: case for case in load_cases(CASE_DIR)}
    for case_id in (
        "interval-empty-equal-offset-endpoints-001",
        "interval-reversed-after-offset-normalization-001",
    ):
        case = cases[case_id]
        result = evaluate_reference(case["operation"], case["input"])
        assert result["ok"] is False
        assert result["error"]["category"] == "invalid_interval"


def test_static_graph_bfs_contract_fixed_cases() -> None:
    cases = {
        case["case_id"]: case
        for case in load_cases(CASE_DIR)
        if case["operation"] == "graph.static.bfs"
    }
    expected = {
        "graph-static-bfs-basic-001": ["b", "c", "d"],
        "graph-static-bfs-cycle-001": ["b", "c"],
        "graph-static-bfs-disconnected-001": ["b"],
        "graph-static-bfs-implicit-endpoint-duplicate-edge-001": ["b"],
    }
    for case_id, expected_result in expected.items():
        case = cases[case_id]
        result = evaluate_reference(case["operation"], case["input"])
        assert result == {"ok": True, "result": expected_result}
        assert case["expected_result"] == expected_result
    for case_id in (
        "graph-static-bfs-unknown-source-001",
        "graph-static-bfs-blank-node-001",
    ):
        case = cases[case_id]
        result = evaluate_reference(case["operation"], case["input"])
        assert result["ok"] is False
        assert result["error"]["category"] == case["expected_error"]
