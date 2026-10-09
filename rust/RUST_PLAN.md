# Rust deterministic compute kernel

**Starting status:** the existing core is operational; Rust kernel expansion is in progress.
**Repository baseline:** `0e395232fc609ac5c12fc1ff64353ef6869f4c3a` (observed `main` commit).
**First objective:** turn the small deterministic native core into a maintainable, contract-conformant compute kernel without changing the authoritative Python semantics.

## 2.0 — Workspace and repeatable verification (this bundle)

Deliver: root Cargo workspace, pinned development toolchain, `qedty-conformance`, CI workflow, instructions, file map, research baseline.

Exit gate:
- `cargo metadata --locked` succeeds;
- format, workspace tests, Clippy and conformance CLI pass;
- existing native golden tests and Phase 1 Python suite remain green;
- root lockfile is Cargo-generated and committed after review.

## 2.1 — Core module decomposition (first production code task)

Move implementations from the current monolithic `crates/qedty-core/src/lib.rs` into internal modules while preserving public exports:
- `canonical.rs`: canonical JSON profile and serialization behavior;
- `identity.rs`: SHA-256 and deterministic IDs;
- `types.rs`: `EntityRef`, `TimeWindow`, and `Quantity`;
- `geometry.rs`: WGS-84 constants/conversion API;
- `error.rs`: typed core errors.

This is a behavior-preserving refactor. It must not change the canonical JSON bytes or identity digest values. Keep vector tests running before and after each move.

## 2.2 — Numeric and core API contracts

Define fallible validation APIs additively. Document finite-number handling, latitude/longitude ranges, height units, hash preimages, identity digest length, and error categories. Do not silently change `ecef_wgs84`'s tuple signature until consumers have migrated; introduce a validated method if the public contract needs it.

## 2.3 — Geodesy and spatial primitives

Build only the functions required by the Python reference/contract. Start with the existing WGS-84 ECEF implementation, add geodetic edge cases (equator, poles, negative height, dateline, zero longitude), then select further operations such as inverse ECEF only when there is a referenced Python function and golden vector. Document tolerance in meters.

## 2.4 — Temporal primitives

Implement reusable interval/timeline operations, not application orchestration. Define open/closed interval boundaries, UTC normalization, invalid and empty interval behavior, granularity, and bitemporal distinctions from Python contracts. Each behavior needs shared fixtures before Rust is accepted.

## 2.5 — Graph primitives and spatial/temporal indexing

Focus first on stable graph representation, deterministic adjacency ordering, edge traversal and small pure algorithms that have Python references. Select data structures by benchmarked graph sizes and access patterns. Don't introduce a graph dependency until measured evidence justifies it.

## 2.6 — Deterministic compute kernels

Incrementally port propagation aggregation, scenario transforms, continuity calculations, uncertainty primitives, and selected optimization/analytics kernels. Numerical operations require domain invariants and explicit tolerances; output ordering and tie-breaking must be deterministic where expected.

## 2.7 — Python boundary (only when proven useful)

PyO3 + maturin are the preferred research candidates, but the repository currently uses setuptools as its Python build backend and currently makes maturin optional. Do not switch the project-wide build backend as part of workspace setup. Prototype a narrow extension only after stable Rust APIs and conformance coverage exist, then make a separate packaging ADR and test wheel builds for Python 3.12 and 3.13 on supported platforms.

## 2.8 — Performance evidence and release readiness

For each kernel: Criterion release-mode benchmark, reproducible workload, baseline result, allocation/memory observations, profile evidence, and no statistically credible regression without an approved reason. Optimize only measured bottlenecks. C++/CUDA remains Phase 7.

## Mandatory cross-language pipeline

```text
Python reference + contract
       ↓ generate/review shared golden vector
Rust implementation
       ↓ run native vector tests
Python ↔ Rust differential/conformance tests
       ↓ property tests + fuzzing where appropriate
release-mode benchmark + memory/profile checks
       ↓ review/API approval
candidate for stable public API or Python binding
```

## Rust exit criteria

Rust kernel expansion is complete only when the planned Rust kernel scope has a reviewed API and domain-by-domain conformance matrix; supported shared vectors pass; errors/boundaries/tolerances are documented; property/differential tests cover important invariants; security and dependency reviews are in CI; performance claims have reproducible benchmarks; Python integration is tested if enabled; and packaging/release artifacts are reproducible. Merely passing the initial three-vector CLI does not close Rust.
