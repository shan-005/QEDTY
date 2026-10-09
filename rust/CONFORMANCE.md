# Rust conformance protocol

## Source of expected behavior

Expected behavior comes from QEDTY's Python semantic/reference implementation plus the versioned, language-neutral fixtures in `data/contracts/golden-vectors/`. Rust tests must call production Rust functions and compare their outputs with those fixture values. A hand-written test that merely duplicates the Rust implementation is not cross-language conformance.

## Current executable coverage

| Vector file | Current Rust API | Comparison |
|---|---|---|
| `core/canonical_json.json` | `canonical_json` | Exact canonical JSON string |
| `core/identity.json` | `deterministic_id` | Exact ID string |
| `core/geometry_ecef.json` | `ecef_wgs84` | Each coordinate within vector `absolute_tolerance_m` |
| `core/quantity.json` | No conversion API currently exposed | Not yet implemented in Rust; must not be counted as pass |
| `core/time.json` | No time normalization API currently exposed | Not yet implemented in Rust; must not be counted as pass |

The existing `crates/qedty-core/tests/golden.rs` already tests the first three vectors. The new CLI provides a simple developer-facing command and a CI-visible summary. It should not replace that integration test.

## Vector design rules

A vector should include a stable identifier/kind, the minimum complete input, the expected output, relevant contract/profile version, and explicit tolerance/units when approximate math is involved. Vectors should be small and deterministic, and must not contain secrets or licensed bulk datasets.

When adding a domain vector:

1. Implement or identify the Python reference behavior.
2. Make the intended boundary behavior explicit in the domain contract.
3. Produce expected output with the Python implementation, not a second Rust implementation.
4. Review the fixture independently; avoid regenerating expected values in a way that simply blesses a bug.
5. Add Rust test(s) that load the same committed fixture.
6. Add or update the corresponding Python conformance checker.
7. Include the vector IDs in the PR and CI evidence.

## Differential tests

A differential test executes the same input against Python and Rust and compares normalized outputs. Exact strings/IDs/contracts require exact match. Floating-point computations use the contract's stated absolute/relative tolerances and must reject NaN/Infinity unless expressly allowed. Preserve error categories and validation boundaries too—not only successful outputs.

## Fuzz and property testing

Use `proptest` for invariants with structured domains and shrinking, for example identity prefix/length constraints, interval invariants, and geometry range checks. Use `cargo-fuzz` for untrusted parsers, serialization, vector readers, and complex inputs where coverage-guided fuzzing adds value. Fuzzing is a separate job if it requires nightly; stable required checks should remain reliable and deterministic.
