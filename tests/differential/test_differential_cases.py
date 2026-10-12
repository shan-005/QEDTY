from __future__ import annotations

import importlib.util
import json
import math
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


def test_generated_cases_are_reproducible_and_cover_fourteen_families() -> None:
    first = generate_cases(8, 20261010)
    second = generate_cases(8, 20261010)
    assert first == second
    assert len(first) == 112
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
        "graph.static.scc",
        "spatial.distance.haversine",
        "spatial.radius.query",
        "temporal.bitemporal.contains",
        "temporal.timeline.query",
        "temporal.index.query",
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

    scc_cases = [case for case in generated if case["operation"] == "graph.static.scc"]
    assert len(scc_cases) == 64
    for case in scc_cases:
        result = evaluate_reference(case["operation"], case["input"])
        assert result["ok"] is True
        components = result["result"]
        assert components == sorted(components)
        assert all(component == sorted(set(component)) for component in components)
        flattened = [label for component in components for label in component]
        assert sorted(flattened) == sorted(set(flattened))
        assert sorted(flattened) == sorted(case["input"]["nodes"])

    bitemporal_cases = [
        case for case in generated if case["operation"] == "temporal.bitemporal.contains"
    ]
    timeline_cases = [case for case in generated if case["operation"] == "temporal.timeline.query"]
    assert len(bitemporal_cases) == len(timeline_cases) == 64
    for case in [*bitemporal_cases, *timeline_cases]:
        result = evaluate_reference(case["operation"], case["input"])
        assert result["ok"] is True, (case["case_id"], result)
    assert {case["input"]["mode"] for case in timeline_cases} == {
        "at_or_before",
        "at_or_after",
        "between",
        "latest",
        "ordered",
        "values",
    }


def test_generated_temporal_index_cases_exercise_all_modes() -> None:
    generated = [
        case for case in generate_cases(64, 20261010) if case["operation"] == "temporal.index.query"
    ]
    assert len(generated) == 64
    assert {case["input"]["mode"] for case in generated} == {
        "at",
        "overlapping",
        "all",
        "get",
        "remove",
        "len",
        "add",
        "clear",
    }
    for case in generated:
        result = evaluate_reference(case["operation"], case["input"])
        assert result["ok"] is True, (case["case_id"], result)


def test_temporal_boundary_regression_cases_are_present() -> None:
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


def test_spherical_spatial_distance_fixed_contracts() -> None:
    cases = {
        case["case_id"]: case
        for case in load_cases(CASE_DIR)
        if case["operation"] == "spatial.distance.haversine"
    }
    expected = {
        "spatial-distance-identical-001": 0.0,
        "spatial-distance-equator-one-degree-001": 111195.0802335329,
        "spatial-distance-antimeridian-one-degree-001": 111195.0802335329,
        "spatial-distance-quarter-circumference-001": 10007557.221017962,
        "spatial-distance-antipodal-001": 20015114.442035925,
    }
    for case_id, expected_m in expected.items():
        case = cases[case_id]
        result = evaluate_reference(case["operation"], case["input"])
        assert result["ok"] is True
        assert math.isclose(
            result["result"],
            expected_m,
            rel_tol=case["comparison"]["relative_tolerance"],
            abs_tol=case["comparison"]["absolute_tolerance"],
        )
        assert case["expected_result"] == expected_m

    for case_id in (
        "spatial-distance-invalid-latitude-001",
        "spatial-distance-invalid-longitude-001",
    ):
        case = cases[case_id]
        result = evaluate_reference(case["operation"], case["input"])
        assert result["ok"] is False
        assert result["error"]["category"] == case["expected_error"]


def test_spherical_radius_query_fixed_contracts() -> None:
    cases = {
        case["case_id"]: case
        for case in load_cases(CASE_DIR)
        if case["operation"] == "spatial.radius.query"
    }
    expected = {
        "spatial-radius-basic-001": ["center", "near", "edge"],
        "spatial-radius-boundary-001": ["edge"],
        "spatial-radius-antimeridian-001": ["east", "west"],
        "spatial-radius-polar-001": ["center", "east", "west"],
        "spatial-radius-zero-duplicate-id-001": ["same", "zero"],
        "spatial-radius-empty-001": [],
        "spatial-radius-global-coverage-001": ["center", "east", "west", "antipode"],
    }
    for case_id, expected_ids in expected.items():
        case = cases[case_id]
        result = evaluate_reference(case["operation"], case["input"])
        assert result == {"ok": True, "result": expected_ids}
        assert case["expected_result"] == expected_ids

    for case_id in (
        "spatial-radius-negative-radius-001",
        "spatial-radius-invalid-cell-001",
        "spatial-radius-blank-id-001",
        "spatial-radius-invalid-latitude-001",
    ):
        case = cases[case_id]
        result = evaluate_reference(case["operation"], case["input"])
        assert result["ok"] is False
        assert result["error"]["category"] == case["expected_error"]


def test_generated_spherical_spatial_families_are_deterministic() -> None:
    first = generate_cases(64, 20261010)
    second = generate_cases(64, 20261010)
    assert first == second
    distances = [case for case in first if case["operation"] == "spatial.distance.haversine"]
    radius_queries = [case for case in first if case["operation"] == "spatial.radius.query"]
    assert len(distances) == len(radius_queries) == 64

    for case in distances:
        result = evaluate_reference(case["operation"], case["input"])
        assert result["ok"] is True
        assert math.isfinite(result["result"]) and result["result"] >= 0.0

    for case in radius_queries:
        result = evaluate_reference(case["operation"], case["input"])
        assert result["ok"] is True
        ids = result["result"]
        assert len(ids) == len(set(ids))
        point_ids = {point["id"].strip() for point in case["input"]["points"]}
        assert set(ids).issubset(point_ids)


def test_static_graph_scc_contract_fixed_cases() -> None:
    cases = {
        case["case_id"]: case
        for case in load_cases(CASE_DIR)
        if case["operation"] == "graph.static.scc"
    }
    expected = {
        "graph-static-scc-basic-001": [["a", "b", "c"], ["d"], ["isolated"]],
        "graph-static-scc-two-cycles-one-way-001": [["a", "b"], ["c", "d"]],
        "graph-static-scc-acyclic-001": [["a"], ["m"], ["z"]],
        "graph-static-scc-trimmed-implicit-duplicate-001": [["a", "b"]],
        "graph-static-scc-self-loop-isolate-001": [["lonely"], ["self"]],
        "graph-static-scc-empty-graph-001": [],
    }
    for case_id, expected_result in expected.items():
        case = cases[case_id]
        result = evaluate_reference(case["operation"], case["input"])
        assert result == {"ok": True, "result": expected_result}
        assert case["expected_result"] == expected_result

    for case_id in (
        "graph-static-scc-blank-node-001",
        "graph-static-scc-malformed-edge-001",
        "graph-static-scc-non-string-endpoint-001",
    ):
        case = cases[case_id]
        result = evaluate_reference(case["operation"], case["input"])
        assert result["ok"] is False
        assert result["error"]["category"] == case["expected_error"]


def test_bitemporal_and_event_timeline_fixed_contracts() -> None:
    cases = {case["case_id"]: case for case in load_cases(CASE_DIR)}
    for case_id, expected in {
        "bitemporal-open-both-clocks-001": True,
        "temporal-bitemporal-open-upper-bounds-001": True,
        "bitemporal-valid-upper-exclusive-001": False,
        "bitemporal-outside-valid-clock-001": False,
        "bitemporal-transaction-upper-exclusive-001": False,
        "bitemporal-equivalent-offset-instant-001": True,
    }.items():
        case = cases[case_id]
        assert case["operation"] == "temporal.bitemporal.contains"
        assert case["expected_result"] is expected
        assert evaluate_reference(case["operation"], case["input"]) == {
            "ok": True,
            "result": expected,
        }

    for case_id in (
        "bitemporal-equal-valid-bounds-invalid-001",
        "bitemporal-reversed-transaction-bounds-invalid-001",
        "timeline-reversed-between-invalid-001",
    ):
        case = cases[case_id]
        result = evaluate_reference(case["operation"], case["input"])
        assert result["ok"] is False
        assert result["error"]["category"] == "invalid_interval"

    timeline_expected = {
        "timeline-at-or-before-sequence-001": "sequence-2",
        "timeline-at-or-after-earliest-sequence-001": "sequence-minus-one",
        "timeline-between-half-open-001": [
            {"at": "2026-01-02T00:00:00.000000Z", "value": "start", "sequence": 1},
            {"at": "2026-01-03T00:00:00.000000Z", "value": "middle", "sequence": 2},
        ],
        "timeline-latest-001": {
            "at": "2026-01-03T00:00:00.000000Z",
            "value": "latest",
            "sequence": 0,
        },
    }
    for case_id, expected in timeline_expected.items():
        case = cases[case_id]
        assert case["expected_result"] == expected
        assert evaluate_reference(case["operation"], case["input"]) == {
            "ok": True,
            "result": expected,
        }


def test_temporal_index_fixed_contracts_and_error_categories() -> None:
    cases = {
        case["case_id"]: case
        for case in load_cases(CASE_DIR)
        if case["operation"] == "temporal.index.query"
    }
    expected_ids = {
        "temporal-index-at-half-open-order-001",
        "temporal-index-overlapping-touching-boundaries-001",
        "temporal-index-all-sorted-start-and-key-001",
        "temporal-index-duplicate-add-idempotent-001",
        "temporal-index-explicit-add-is-idempotent-001",
        "temporal-index-explicit-add-increments-length-001",
        "temporal-index-initial-key-collision-value-001",
        "temporal-index-add-collision-extent-001",
        "temporal-index-get-existing-001",
        "temporal-index-get-missing-key-001",
        "temporal-index-remove-existing-001",
        "temporal-index-remove-missing-key-001",
        "temporal-index-clear-empties-index-001",
        "temporal-index-invalid-reversed-extent-001",
        "temporal-index-invalid-nonstring-value-001",
        "temporal-index-invalid-mode-001",
    }
    assert expected_ids.issubset(cases)

    for case_id in expected_ids:
        case = cases[case_id]
        actual = evaluate_reference(case["operation"], case["input"])
        if "expected_error" in case:
            assert actual["ok"] is False, (case_id, actual)
            assert actual["error"]["category"] == case["expected_error"], (case_id, actual)
        else:
            assert actual == {"ok": True, "result": case["expected_result"]}, (case_id, actual)

