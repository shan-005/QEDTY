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

At the accepted merge commit [`6c86b3f`](https://github.com/shan-005/QEDTY/commit/6c86b3fca5d945f8e544635d9e0f084a0839c28f), the fixed inventory contains 51 cases, including all 13 Allen relations and reviewed negative cases. The default command adds 64 generated cases per each of seven families (canonical JSON, identity, quantity, geometry, time, interval membership and Allen relations): 448 generated plus 51 fixed, 499 total. The recorded run passed 499/499 cases with seed `20261010`. Per-operation totals were `canonical_json 67/67`, `contract_result 2/2`, `geometry.ecef 72/72`, `identity 69/69`, `interval.contains 70/70`, `quantity.convert 72/72`, `temporal.relation 78/78`, and `time.normalize 69/69`. See the [differential CI run](https://github.com/shan-005/QEDTY/actions/runs/38126849169) for the hosted gate.

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
