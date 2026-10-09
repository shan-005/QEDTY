# Phase 2 implementation and conformance matrix

| Capability | Python/reference authority | Rust target | Shared expected output | Minimum completion tests |
|---|---|---|---|---|
| Canonical JSON | Existing Python canonicalization implementation/tests; locate exact path before editing | lib.rs::canonical_json | core/canonical_json.json | Byte-exact output, nested object order, array order, escaping, supported values and errors |
| Deterministic identity | Existing Python identity helper/tests; locate exact path | lib.rs::deterministic_id | core/identity.json | Validation, parts order, digest-length boundaries, multiple shared vectors |
| WGS-84 ECEF | Existing Python geometry implementation/tests; locate exact path before changing semantics | Existing ecef_wgs84; new geometry::try_ecef_wgs84 | core/geometry_ecef.json | Shared tolerance, edge geographic cases, checked-input errors, old signature preserved |
| Temporal extent | src/qedty/temporal/intervals.py and qedty.core.time.ensure_utc | Planned temporal.rs | Shared vectors added after behavior mapping | UTC normalization, unbounded ends, finite start < end, canonical [start, end), contains/intersects/intersection/shift, naive datetime policy |
| Core structs | proto/qedty/core/v1/core.proto and contracts/json-schema/core.contract.schema.json | Current structs and focused additions | Fixture from current contracts | Field names, required fields, serialization and round trip |
| Arrow boundary | contracts/arrow/core.contract.json and current conformance tests | Planned arrow.rs / Phase 3 boundary | Contract plus fixtures | Field order/types/nullability/metadata; no unmeasured zero-copy claim |
| Graph | Actual Python graph implementation/tests to be located before port | Planned graph.rs | Shared vectors created from Python | Empty/disconnected/duplicate/self-loop cases, ordering policy, deterministic behavior |
| Propagation | Actual Python propagation source/tests | Planned propagation.rs | Per-kernel shared vectors | No-op/shocks, cycle/limit behavior, missing/unknown inputs, numeric tolerance |
| Scenario/continuity | Actual Python implementations/tests | Planned scenario.rs and continuity.rs | Shared scenario vectors with model/contract version | Baseline linkage, intervention/no-op, provenance/epistemic outputs at wrapper boundary |
| Uncertainty/economics/optimization | Actual Python formulas/tests; port after formula mapping and profiling | Planned focused modules | Shared numeric vectors with units/assumptions | Dimensions, error ranges, convergence/stopping criteria, deterministic or seeded randomness |

## Verification layers

- Golden vectors: normative examples from the Python reference or an approved specification.
- Differential testing: identical input into Python and Rust; structural equality and explicit numeric tolerance per kernel.
- Property tests: invariants such as half-open interval consistency or no-op intervention invariance.
- Fuzz tests: malformed-input and crash/panic hardening; not a replacement for normative vectors.
- Benchmarks: versioned identical workloads with toolchain/profile/host/sample details and measured distributions.
- Packaging tests: only when bindings are introduced; import, error translation, wheel install and source build on Python 3.12/3.13.

A row is not complete until exact source paths and tests are named in the PR. “Locate before port” is intentional; don't guess repository semantics.
