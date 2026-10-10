# QEDTY Rust target tree

This document distinguishes the **checked-in Rust implementation** from future target designs. The tree below reflects the live repository; a planned crate or README is not evidence that an implementation exists.

## Current checked-in implementation

```text
QEDTY/
├── Cargo.toml
├── Cargo.lock                         # single lockfile for the root Cargo workspace
├── rust-toolchain.toml
├── crates/
│   └── qedty-core/
│       ├── Cargo.toml
│       ├── src/
│       │   ├── lib.rs
│       │   ├── geometry.rs
│       │   ├── temporal.rs
│       │   ├── quantity.rs
│       │   ├── contract_result.rs
│       │   ├── temporal_relations.rs
│       │   ├── geodesy.rs
│       │   ├── spatial.rs
│       │   ├── graph.rs
│       │   ├── compute.rs
│       │   └── columnar.rs
│       └── tests/
│           ├── golden.rs
│           └── rust_expansion.rs
├── data/contracts/golden-vectors/core/
│   ├── canonical_json.json
│   ├── canonical_json_numbers.json       # Python-compatible float exponent spelling
│   ├── contract_result.json            # shared Rust contract-result vector
│   ├── geometry_ecef.json
│   ├── geometry_ecef_antimeridian.json
│   ├── geometry_ecef_east_quarter_turn.json
│   ├── geometry_ecef_equator.json
│   ├── geometry_ecef_negative_height.json
│   ├── geometry_ecef_north_pole.json
│   ├── geometry_ecef_south_pole.json
│   ├── identity.json
│   ├── quantity.json                   # shared Rust unit-conversion vector
│   └── time.json                       # shared Rust UTC-normalization vector
└── rust/
    ├── README.md
    ├── HOW_TO_WORK.md
    ├── ARCHITECTURE.md
    ├── RUST_PLAN.md
    ├── CONFORMANCE.md
    ├── QUALITY_GATES.md
    ├── TARGET_TREE.md
    ├── RESEARCH_BASELINE.md
    ├── crate-map.toml
    ├── decisions/
    │   ├── ADR-0001-semantic-authority.md
    │   ├── ADR-0002-workspace-layout.md
    │   ├── ADR-0003-python-binding-timing.md
    │   └── README.md
    ├── research/
    │   ├── SOURCES.md
    │   └── fixtures/                   # documentation audit copies, not canonical inputs
    ├── scripts/verify.sh
    ├── benches/README.md               # methodology only; no benchmark target yet
    ├── fuzz/README.md                  # plan only; no cargo-fuzz target yet
    └── crates/qedty-conformance/
        ├── Cargo.toml
        ├── src/main.rs
        ├── src/bin/rust-expansion-conformance.rs
        └── tests/cli.rs
```

The Python semantic/reference implementation and its contracts remain the semantic authority. The Rust workspace includes canonical JSON, identity, checked WGS-84 ECEF, inverse ECEF, RFC 3339 normalization, temporal relations/bitemporal timelines, dimension-checked quantities, contract-result normalization, deterministic graph algorithms, point-grid spatial queries, numeric propagation/uncertainty/selection kernels, and an Arrow-neutral columnar batch seam. The primary CLI checks the implemented shared core vectors; the separate expanded runner also verifies graph/spatial scenarios.

## Current Rust conformance scope

The canonical core fixture directory contains 13 JSON fixtures. The Rust conformance runner now checks all 13 behavior cases: canonical JSON (2), deterministic identity (1), ECEF geometry (7), timestamp normalization (1), quantity conversion (1), and contract-result canonicalization (1). The graph conformance runner also checks eight versioned scenarios. Additional property/differential evidence is still required; a fixture pass does not prove every domain integration or release gate is complete.

The ECEF fixture set contains independently stated expected values for the general reference case, equator, 90-degree east, both poles, antimeridian, and negative height. See `CONFORMANCE.md` and `research/SOURCES.md` for comparison rules and WGS-84 references.

## Required local/hosted verification

```bash
cargo fmt --all -- --check
cargo test --workspace --locked
cargo clippy --workspace --all-targets --locked -- -D warnings
cargo run --locked -p qedty-conformance
cargo test --locked --manifest-path crates/qedty-core/Cargo.toml
cargo +1.78.0 test --workspace --locked
uv run python scripts/check_manifest_inventory.py
```

The hosted repository gate additionally runs Python quality/conformance checks, locked dependency checks, distribution build, and package metadata validation. The root `Cargo.lock` is the only workspace lock; do not add a nested crate lockfile.

## Planned decomposition (not current source files)

Split the core only when each boundary has a reviewed API, a Python/reference contract, and suitable tests:

```text
crates/qedty-core/src/
├── lib.rs          # stable public exports
├── geometry.rs     # existing WGS-84 implementation
├── canonical.rs    # future extraction only if justified
├── identity.rs     # future extraction only if justified
├── types.rs        # future extraction only if justified
└── error.rs        # future extraction if typed errors are introduced
```

Add files only with a useful API, relevant tests, shared expected-value fixtures, and documentation. Preserve public exports so internal refactors do not force downstream import changes.

## Possible future crate boundaries

Create additional crates only when a stable contract and justified dependency boundary exist. Candidate domains include temporal, spatial, graph, propagation, scenarios, continuity, uncertainty, optimization, Arrow adapters, and a future Python binding. These are roadmap targets, not present modules or completed milestones.

WIT/WASM, Go, C/C++/CUDA, TypeScript/React, and standalone SQL services are separate future execution targets. They require their own source code, contracts, tests, and validation before being described as implemented.

## Benchmarking and fuzzing

`rust/benches/README.md` documents methodology; there is no checked-in Criterion benchmark target. `rust/fuzz/README.md` documents candidate fuzz targets; there is no checked-in `cargo-fuzz` target. Do not report either activity as executed until its target and run evidence exist.


## Expanded core modules

The following source modules are now included in `qedty-core`: `quantity.rs`, `contract_result.rs`, `temporal_relations.rs`, `geodesy.rs`, `spatial.rs`, `graph.rs`, `compute.rs`, and `columnar.rs`. The columnar module deliberately avoids claiming Arrow IPC support. `rust/CORE_EXPANSION.md` defines the APIs and residual release gates.
