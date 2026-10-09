# Rust deterministic compute kernel

**Starting status:** the existing core is operational; Rust kernel expansion is in progress.
**Repository baseline:** the current protected `main` branch. Refresh the remote commit before implementation/review; avoid treating a historical SHA as the current head.
**First objective:** grow the small deterministic native core into a maintainable, contract-conformant compute kernel without changing the authoritative Python semantics.

## Workspace and repeatable verification

Deliver: root Cargo workspace, pinned development toolchain, `qedty-conformance`, CI workflow, instructions, file map, and research baseline.

Exit gate:
- `cargo metadata --locked` succeeds;
- format, workspace tests, Clippy, and the conformance CLI pass;
- native golden tests and the Python quality/test suite remain green;
- the root workspace lockfile is committed and verified with locked Cargo commands.

## Core module decomposition

`crates/qedty-core/src/geometry.rs` already holds the WGS-84 geometry implementation; `crates/qedty-core/src/lib.rs` still holds the other current core implementation. Further decomposition is a planned, behavior-preserving refactor, not a description of the current file layout. Preserve public exports and do not change canonical JSON bytes, identity digests, or existing signatures without an explicit compatibility decision.

Potential internal boundaries, to create only when they materially improve maintainability:
- `canonical.rs`: canonical JSON profile and serialization behavior;
- `identity.rs`: SHA-256 and deterministic IDs;
- `types.rs`: core reference/value types;
- `error.rs`: typed core errors.

Keep shared vector tests running before and after each refactor. Do not create empty placeholder modules to make the tree resemble a future design.

## Numeric and core API contracts

Define fallible validation APIs additively. Document finite-number handling, latitude/longitude ranges, height units, hash preimages, identity digest length, and error categories. Do not silently change `ecef_wgs84` tuple behavior until consumers have migrated; introduce a validated API if the public contract needs it.

## Geodesy and spatial primitives

Build only functions required by the Python reference and contracts. The current ECEF API has independently expected equator, east-quarter-turn, pole, antimeridian, and negative-height fixtures. Select further operations such as inverse ECEF only when there is a referenced Python function and independently reviewed golden vector. Document tolerance in meters.

## Temporal primitives

Implement reusable interval/timeline operations, not application orchestration. Define interval boundaries, UTC normalization, invalid and empty interval behavior, granularity, and bitemporal distinctions from Python contracts. The existing `time.json` fixture does not mean a Rust time API has been implemented; add one only with shared expected-value fixtures.

## Graph primitives and spatial/temporal indexing

Focus first on stable graph representation, deterministic adjacency ordering, edge traversal, and small pure algorithms that have Python references. Choose data structures from benchmarked graph sizes and access patterns. Do not introduce a graph dependency until measured evidence justifies it.

## Deterministic compute kernels

Incrementally port propagation aggregation, scenario transforms, continuity calculations, uncertainty primitives, and selected optimization/analytics kernels. Numerical operations require domain invariants and explicit tolerances; output ordering and tie-breaking must be deterministic where expected.

## Python boundary (only when proven useful)

PyO3 and maturin are research candidates, but the current Python project uses setuptools and does not ship a Rust Python extension. Do not switch the project-wide build backend as part of workspace setup. Prototype a narrow extension only after stable Rust APIs and conformance coverage exist, then make a separate packaging decision and test wheels for Python 3.12 and 3.13 on supported platforms.

## Performance evidence and release readiness

For each performance-oriented kernel, provide a Criterion release-mode benchmark, reproducible workload, baseline result, allocation/memory observations, profile evidence, and review of any statistically credible regression. Optimize only measured bottlenecks. C++/CUDA remains outside the current Rust scope and requires a separate evidence-backed proposal.

## Mandatory cross-language pipeline

```text
Python reference + contract
       ↓ review shared golden vector
Rust implementation
       ↓ load the canonical committed fixture
Rust vector test + Python/Rust differential test
       ↓ property tests and fuzzing where applicable
release-mode benchmark + memory/profile checks
       ↓ API review
candidate for stable public API or Python binding
```

## Rust exit criteria

Rust kernel expansion is complete only when the planned scope has reviewed APIs and a domain-by-domain conformance matrix; supported shared vectors pass; errors, boundaries, and tolerances are documented; property/differential tests cover important invariants; security/dependency review is active; performance claims have reproducible benchmarks; Python integration is tested if enabled; and release artifacts are reproducible. Passing current core vectors does not close the whole Rust roadmap. `contract_result`, `quantity`, and `time` remain pending Rust APIs and must not count as passing Rust conformance.
