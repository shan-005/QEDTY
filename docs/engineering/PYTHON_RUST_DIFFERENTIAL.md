# QEDTY Python–Rust Differential Conformance

## Purpose

Python remains QEDTY's semantic/reference authority. Rust implementations are accepted only when the shared contract, independent fixtures, and direct same-input comparisons agree. The JSONL adapter in `rust/crates/qedty-conformance/src/bin/qedty-differential.rs` is test infrastructure, not a production service or a second semantic layer.

## Key files and interfaces

```text
rust/crates/qedty-conformance/src/bin/qedty-differential.rs
scripts/check_python_rust_differential.py
scripts/merge_python_rust_differential_docs.py
scripts/update_manifest_inventory.py
tests/differential/test_differential_cases.py
contracts/json-schema/differential-cases.schema.json
data/contracts/differential/README.md
data/contracts/differential/cases/core.json
docs/engineering/PYTHON_RUST_DIFFERENTIAL.md
.github/workflows/python-rust-differential.yml
```

## Operation coverage

| Operation ID | Python authority | Rust counterpart | Comparison |
|---|---|---|---|
| `canonical_json` | `qedty.core.hash.canonical_json` | `qedty_core::canonical_json` | Exact canonical bytes as UTF-8 text |
| `identity` | `qedty.core.hash.deterministic_id` | `qedty_core::deterministic_id` | Exact ID string; namespace is first item in `parts` |
| `quantity.convert` | `qedty.core.units.convert_value` (`Decimal`) | `qedty_core::quantity::convert_value` (`f64`) | Contract-defined absolute/relative tolerance |
| `time.normalize` | `qedty.core.time.parse_rfc3339` / `to_rfc3339` | `qedty_core::temporal` | Exact normalized UTC string |
| `geometry.ecef` | `GeodeticPoint` / `geodetic_to_ecef` | checked `try_ecef_wgs84` | Per-axis tolerance in metres |
| `contract_result` | `qedty.core.contracts.ContractResult` | `qedty_core::contract_result::ContractResult` | Exact canonical JSON |
| `interval.contains` | `qedty.core.time.in_window` | `qedty_core::temporal::in_window` | Exact boolean and error category |
| `temporal.relation` | `qedty.temporal.intervals.classify` | `qedty_core::temporal_relations::relation` | Exact one of 13 Allen relation labels |
| `bitemporal.contains` | `qedty.temporal.models.BitemporalExtent` / `TemporalExtent.contains` | `qedty_core::temporal::in_window` on both clocks | Exact boolean; independent valid-time and transaction-time half-open windows; null endpoints are unbounded |
| `graph.static.bfs` | `qedty.graph.algorithms.static_bfs_labels` | `qedty_core::graph::DirectedGraph::breadth_first` | Exact ordered list of reachable non-source labels |

## Phase 4 acceptance — bounded temporal edges and static BFS (PR #42)

PR [#42](https://github.com/shan-005/QEDTY/pull/42) was merged at [`3546fbdf9a05d7a989ea530e782c7c3a7e059c5e`](https://github.com/shan-005/QEDTY/commit/3546fbdf9a05d7a989ea530e782c7c3a7e059c5e). The exact PR head was `0b2d1d60878e56a9e7f656501dece0f09d4f75ff`.

The fixed inventory is **96 cases** and the default generated inventory is **512 cases** (64 per each of eight deterministic families). The canonical command passed **608/608** comparisons with seed `20261010`, with no unexpected skips. Operation totals: `canonical_json 67/67`, `contract_result 2/2`, `geometry.ecef 72/72`, `graph.static.bfs 70/70`, `identity 69/69`, `interval.contains 79/79`, `quantity.convert 72/72`, `temporal.relation 91/91`, and `time.normalize 86/86`.

All five required hosted workflows passed on that exact head: [QEDTY CI](https://github.com/shan-005/QEDTY/actions/runs/38145228618), [QEDTY Rust](https://github.com/shan-005/QEDTY/actions/runs/38145228592), [Platform Smoke](https://github.com/shan-005/QEDTY/actions/runs/38145228589), [Python–Rust Differential](https://github.com/shan-005/QEDTY/actions/runs/38145228585), and [Dependency Review](https://github.com/shan-005/QEDTY/actions/runs/38145228576).

This acceptance is limited to the listed offset-equivalence/window-error cases and the version-1 label-only static directed BFS contract. It does not establish temporal world-graph parity or full parity for graph, spatial, propagation, uncertainty, optimization, or Python application domains.

At the accepted merge commit [`6c86b3f`](https://github.com/shan-005/QEDTY/commit/6c86b3fca5d945f8e544635d9e0f084a0839c28f), the fixed inventory contains 51 cases, including all 13 Allen relations and reviewed negative cases. The default command adds 64 generated cases per each of seven families (canonical JSON, identity, quantity, geometry, time, interval membership and Allen relations): 448 generated plus 51 fixed, 499 total. The recorded run passed 499/499 cases with seed `20261010`. Per-operation totals were `canonical_json 67/67`, `contract_result 2/2`, `geometry.ecef 72/72`, `identity 69/69`, `interval.contains 70/70`, `quantity.convert 72/72`, `temporal.relation 78/78`, and `time.normalize 69/69`. See the [differential CI run](https://github.com/shan-005/QEDTY/actions/runs/38126849169) for the hosted gate.

## Temporal boundary follow-up (PR #37)

PR [#37](https://github.com/shan-005/QEDTY/pull/37) added 20 fixed timestamp/window cases and corrected Python parsing of malformed timezone offsets to follow QEDTY's supported shared RFC 3339 profile. The accepted merge commit is [`8cfd0de6601542be5d61cbfb65a6599b232390b7`](https://github.com/shan-005/QEDTY/commit/8cfd0de6601542be5d61cbfb65a6599b232390b7).

The latest fixed inventory is **71 cases**. With 64 generated cases in each of seven families, the default run totals **519 comparisons** (71 fixed + 448 generated) and passed 519/519 with seed `20261010`. Per-operation totals: `canonical_json 67/67`, `contract_result 2/2`, `geometry.ecef 72/72`, `identity 69/69`, `interval.contains 77/77`, `quantity.convert 72/72`, `temporal.relation 78/78`, and `time.normalize 82/82`.

The Python suite passed **243 tests with 67.24% coverage** on Python 3.12 and 3.13. The Rust workspace passed 77 tests. Ruff lint/format, mypy, Bandit, dependency auditing, packaging/Twine, CLI, manifest, lockfile and Rust 1.78/Arrow IPC gates also passed. See the pre-merge checks: [differential](https://github.com/shan-005/QEDTY/actions/runs/38132560404), [CI](https://github.com/shan-005/QEDTY/actions/runs/38132560494), [Rust](https://github.com/shan-005/QEDTY/actions/runs/38132560447), [Platform Smoke](https://github.com/shan-005/QEDTY/actions/runs/38132560364), and [Dependency Review](https://github.com/shan-005/QEDTY/actions/runs/38132560437).

This is bounded operation-level parity for the declared inputs, not exhaustive RFC 3339 grammar, bitemporal/timeline parity, full temporal ontology semantics, or whole-domain Python–Rust parity.


## Allen inverse-relation regression expansion — accepted in PR #39

PR [#39](https://github.com/shan-005/QEDTY/pull/39) was merged at [a80e0cd704b45eed79468d064c963bcaf774c9fc](https://github.com/shan-005/QEDTY/commit/a80e0cd704b45eed79468d064c963bcaf774c9fc). The fixed corpus adds thirteen cases that reverse the left and right intervals of each canonical Allen-relation fixture. The expected result is the inverse mapping: before/after, meets/met-by, overlaps/overlapped-by, starts/started-by, during/contains, finishes/finished-by, and equals/equals. A focused fixture test asserts all thirteen swapped inputs and inverse labels are present before the differential runner executes them against Python and Rust.

The accepted inventory contains **84 fixed cases**. The default run passed **532/532 comparisons** (84 fixed + 448 generated) with seed `20261010`; the temporal-relation operation passed **91/91** comparisons (27 fixed + 64 generated). Per-operation totals are recorded in the [engineering acceptance record](CROSS_LANGUAGE_CONFORMANCE_EXPANSION.md).

The full Python suite passed **244 tests** with **67.24% total coverage** on both Python 3.12 and 3.13. The Rust workspace passed **77 tests**. All eight visible PR-head check runs passed: [QEDTY CI](https://github.com/shan-005/QEDTY/actions/runs/38141225163), [QEDTY Rust](https://github.com/shan-005/QEDTY/actions/runs/38141225210), [Python–Rust Differential](https://github.com/shan-005/QEDTY/actions/runs/38141225164), [Platform Smoke](https://github.com/shan-005/QEDTY/actions/runs/38141225208), and [review check](https://github.com/shan-005/QEDTY/actions/runs/38141225209).

Bitemporal and timeline APIs remain outside direct parity until their matching semantics are specified. These results validate the declared fixtures and operations, not exhaustive Allen algebra proofs or whole-domain temporal parity.

## Bitemporal direct differential — in progress

The version-1 `bitemporal.contains` operation compares one valid-time instant and one transaction/knowledge-time instant against two independent half-open windows. Each window uses inclusive lower and exclusive upper bounds; a null endpoint is unbounded. Both windows are validated even when the first membership result is false. Reversed or empty finite windows are invalid.

The fixed fixture file `data/contracts/differential/cases/bitemporal.json` covers membership in both dimensions, independent boundary exclusion, fully open ranges, one-sided open ranges, inclusive starts, and invalid windows. This is a bounded first step: it does not yet establish timeline ordering/query parity or version-history/supersession semantics.

## Commands

```bash
cargo fmt --all -- --check
cargo test --workspace --locked
cargo clippy --workspace --all-targets --locked -- -D warnings
uv run pytest -q tests/differential
uv run python scripts/check_python_rust_differential.py --generated-count 64 --seed 20261010
```

## Failure policy

- A missing binary, failed build, malformed response, missing response, duplicate case ID, unsupported declared operation, or unrecognized comparison mode is a hard failure.
- Exact string/ID/contract outputs are not normalized to hide differences.
- Floating-point tolerances are per-case and documented; no global tolerance is permitted.
- Expected errors require both implementations to fail with the same declared stable category.
- A confirmed mismatch must be minimized and committed as a fixed regression.
- Golden outputs are not regenerated from the Rust side.
- Native graph primitives are not assumed to have parity with QEDTY's temporal world graph until a shared explicit contract exists.

## Acceptance record

The expansion was executed and merged as [PR #33](https://github.com/shan-005/QEDTY/pull/33), at merge commit [`6c86b3fca5d945f8e544635d9e0f084a0839c28f`](https://github.com/shan-005/QEDTY/commit/6c86b3fca5d945f8e544635d9e0f084a0839c28f). Verification recorded for that commit: 8 focused differential tests passed; the full Python suite passed 233 tests with 67.21% coverage; 499/499 differential comparisons passed; and 77 Rust workspace tests passed across the core and conformance suites. Ruff lint/format, mypy, CLI validation, lockfile and manifest inventory checks passed. The post-merge [QEDTY CI](https://github.com/shan-005/QEDTY/actions/runs/38126849216), [Rust](https://github.com/shan-005/QEDTY/actions/runs/38126849124), [differential](https://github.com/shan-005/QEDTY/actions/runs/38126849169), and [platform smoke](https://github.com/shan-005/QEDTY/actions/runs/38126849131) workflows completed successfully. Graph, spatial-index, bitemporal, propagation, uncertainty, and optimization semantics remain explicitly narrower or unshared where the matrix says so; these results do not establish whole-domain parity or production readiness.


## Phase 4 candidate slice: temporal edge closure and static graph BFS

The candidate extension adds a bounded `graph.static.bfs` operation to the version-1 differential-case allowlist. Its input is `{nodes: string[], edges: [string, string][], source: string}`; each edge is directed. The source is excluded from output, outgoing labels are visited lexically, labels are trimmed, edge endpoints implicitly create nodes, and repeat edges cannot duplicate a visited label. Both a Python reference helper and the existing Rust `DirectedGraph::breadth_first` implementation receive the same JSON request.

The same candidate adds fixed pairs of equivalent timestamp representations (including positive and negative UTC offsets), and rejects equal or reversed windows even when their endpoints use different offsets. Existing fixed expected results remain independent oracles. No expected result is regenerated from Rust.

At the default seed/count, the candidate inventory is expected to contain 96 fixed cases and 512 generated cases across eight families (608 total comparisons). Treat that as the candidate inventory until required hosted checks pass on the exact commit. The new graph operation covers one label-only static kernel; it does not imply Python `TemporalGraph` parity, static graph-wide parity, or coverage of spatial, propagation, uncertainty, or optimization domains.
