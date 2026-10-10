# QEDTY Python–Rust Differential Conformance

## Purpose

Python remains QEDTY's semantic/reference authority. Rust implementations are accepted only when the shared contract, independent fixtures, and direct same-input comparisons agree. The JSONL adapter in `rust/crates/qedty-conformance/src/bin/qedty-differential.rs` is test infrastructure, not a production service or a second semantic layer.

## Files added by this bundle

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

The checked-in fixed inventory contains 41 cases, including the 13 Allen relations and reviewed negative cases. The default differential command adds 64 generated cases per each of five families (canonical JSON, identity, quantity, geometry, and time), for 361 total comparisons if all cases are present and the generator is enabled. These counts are inputs to the runner, not a claim that the Rust/Python comparison has already passed in GitHub Actions.

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

The ZIP bundle itself is not test evidence. Milestone acceptance requires the commands above to run against the actual repository checkout and candidate commit. Record the exact commit SHA, Python/Rust versions, command results, fixed/generated counts, seed, any out-of-scope behavior, and CI run URL. Do not mark the work complete solely because the Rust crate compiles.
