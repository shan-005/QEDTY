# QEDTY Phase 2 — Rust deterministic compute kernel

**Status:** implementation blueprint plus one additive geometry starter module  
**Repository base:** [shan-005/QEDTY](https://github.com/shan-005/QEDTY), main at 0e395232fc609ac5c12fc1ff64353ef6869f4c3a  
**Prepared:** 2026-10-09

## Purpose

Phase 2 expands the existing Rust crate into deterministic native kernels that implement existing QEDTY contracts. Python remains the semantic/reference authority. Rust becomes a compatible compute implementation, not a second ontology, evidence model, or policy system.

This is a starter increment plus an implementation plan, not a claim that all Phase 2 kernels are implemented. The only new code is an opt-in typed WGS-84 ECEF boundary around the current calculation. Temporal, graph, propagation, economics and other kernels stay planned until their Python reference behavior has been mapped and frozen in golden vectors.

## Verified repository baseline

- crates/qedty-core/Cargo.toml: package qedty-core version 1.0.0, edition 2021, rust-version 1.78.
- crates/qedty-core/src/lib.rs: canonical JSON, SHA-256, deterministic IDs, core reference structs and ecef_wgs84.
- crates/qedty-core/tests/golden.rs: integration tests use shared JSON vectors.
- Shared vectors: data/contracts/golden-vectors/core/{identity,canonical_json,geometry_ecef}.json.
- .github/workflows/ci.yml runs cargo test --manifest-path crates/qedty-core/Cargo.toml in the native job.
- No root Cargo.toml was present at the inspected base; keep the existing package/CI entry point stable.

## Non-negotiable rules

1. Python is the oracle. Read its implementation and tests before writing a port.
2. Extend/reuse shared contracts and vectors; don't mint Rust-only semantics for time, evidence, identifiers, epistemic states or geometry.
3. Golden vectors first. Expected results come from the Python reference or approved specification, never from Rust under test.
4. Preserve public API compatibility. Signature or serialized-output changes require a reviewed compatibility decision.
5. Benchmark before optimizing; record workload, environment and result distributions.
6. Keep unsafe out of the core unless a narrow, documented and reviewed use is proven.
7. Avoid premature dependencies. Add Arrow, PyO3, property, fuzz or benchmark tooling only when its gate needs it.
8. CUDA is Phase 7; Phase 2 establishes correctness and benchmark baselines first.

## Phase 2 sub-phases

| Gate | Scope | Mandatory output | Exit condition |
|---|---|---|---|
| 2.0 | Baseline and API inventory | API inventory, baseline test results | Existing golden vectors pass unchanged |
| 2.1 | Geometry/geodesy seam | Typed input/result, checked boundary, shared ECEF vectors | Existing API intact; checked path passes shared vector and input-error cases |
| 2.2 | Identity/canonical hardening | Serialization notes, error cases and edge vectors | Byte-exact parity with Python on shared cases |
| 2.3 | Temporal primitives | Port src/qedty/temporal/intervals.py and qedty.core.time semantics | UTC conversion, unbounded ends and half-open [start, end) operations pass differential tests |
| 2.4 | Arrow boundary spike | Mapping from current Arrow contract to Rust representation | Fields, order, types, nullability and metadata tested; full data plane remains Phase 3 |
| 2.5 | Graph and spatial primitives | Small graph operations and selected spatial-index boundary | Edge cases, output ordering and invariants match Python |
| 2.6 | Propagation/scenario/continuity | Bounded independent numerical kernels | Shared vectors for shocks, no-op, cycles/limits and missing inputs |
| 2.7 | Uncertainty/economics/optimization | Kernels selected by evidence/profiling | Numeric policy, units, repeatability and edge cases explicit |
| 2.8 | Hardening/performance | Property/fuzz tests and benchmark baseline | No conformance regressions; measured workload and memory behavior where relevant |
| 2.9 | Python bridge decision | PyO3/maturin prototype for stable APIs only | Python 3.12/3.13 builds, errors, wheel and source distribution verified |

A gate isn't complete because a module exists; it is complete when its reference, contract, tests and review evidence exist.

## Phase 2 exit criteria

- All existing Rust golden tests pass without editing expected values to match Rust.
- Each production kernel names its Python reference, normative contract, shared vector and differential test.
- Determinism and floating-point tolerance are documented per kernel.
- Property tests cover invariants; fuzzing targets parsers/complex boundaries where appropriate.
- Benchmarks compare identical workloads and report toolchain/host/profile; memory is measured where material.
- Format, lint, native tests, Python tests and repository conformance checks pass.
- A chosen PyO3 boundary translates errors deliberately and does not implement domain logic.
- API/MSRV/dependency changes have explicit review notes.

See HOW.md, FILE_TREE.md, IMPLEMENTATION_MATRIX.md, DECISIONS.md and RESEARCH_SOURCES.md.
