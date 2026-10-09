# QEDTY Rust target tree

This document distinguishes the **checked-in Rust implementation** from future target designs. The tree below is based on the current repository, not an archive scaffold.

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
│       │   └── geometry.rs
│       └── tests/
│           └── golden.rs
├── data/contracts/golden-vectors/core/
│   ├── canonical_json.json
│   ├── contract_result.json            # no Rust API yet
│   ├── geometry_ecef.json
│   ├── geometry_ecef_antimeridian.json
│   ├── geometry_ecef_east_quarter_turn.json
│   ├── geometry_ecef_equator.json
│   ├── geometry_ecef_negative_height.json
│   ├── geometry_ecef_north_pole.json
│   ├── geometry_ecef_south_pole.json
│   ├── identity.json
│   ├── quantity.json                   # no Rust quantity conversion API yet
│   └── time.json                       # no Rust time normalization API yet
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
    │   └── fixtures/                   # audit copies; not the executable source of truth
    ├── scripts/verify.sh
    ├── benches/README.md               # methodology only; no benchmark target yet
    ├── fuzz/README.md                  # plan only; no cargo-fuzz target yet
    └── crates/qedty-conformance/
        ├── Cargo.toml
        ├── src/main.rs
        └── tests/cli.rs
```

The Python semantic/reference implementation and its contracts remain the semantic authority. The Rust workspace currently provides deterministic canonical JSON, identity, and WGS-84 ECEF functionality plus a CLI that checks the implemented shared vectors.

## Current Rust conformance scope

The canonical core fixture directory contains 12 JSON fixtures. Nine implemented behavior cases pass in Rust: canonical JSON (1), deterministic identity (1), and ECEF geometry (7). Three fixture types remain pending Rust APIs: `contract_result.json`, `quantity.json`, and `time.json`. A fixture being present is not evidence that a matching Rust API exists.

The ECEF fixture set uses independent expected values for the equator, 90-degree east, both poles, antimeridian, and negative height, plus the general reference vector. See `CONFORMANCE.md` and `research/SOURCES.md` for the comparison rules and WGS-84 references.

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

The hosted repository gate additionally runs the Python quality/conformance checks, locked dependency checks, distribution build, and package metadata validation. The root `Cargo.lock` is the one workspace lock; do not add a nested crate lockfile.

## Planned refactor boundaries (not current files)

Potential core internal modules are planned only where they improve maintainability and preserve the existing public API:

```text
crates/qedty-core/src/
├── lib.rs          # stable public exports
├── geometry.rs     # existing WGS-84 implementation
├── canonical.rs    # future extraction if justified
├── identity.rs     # future extraction if justified
├── types.rs        # future extraction if justified
└── error.rs        # future extraction if typed errors are introduced
```

Add files only with a useful API, relevant tests, shared expected-value fixtures, and documentation. Keep re-exports stable so internal refactors do not force downstream import changes.

## Later crate candidates

Create additional crates only when a contract boundary and evidence justify a separate crate. Candidate areas include temporal, spatial, graph, propagation, scenarios, continuity, uncertainty, optimization, Arrow adapters, and a later Python binding. These are roadmap targets, not present modules or completed milestone claims.

WIT/WASM, Go, C/C++/CUDA, TypeScript/React, and a standalone SQL service are separate future execution targets. They require their own source code, contracts, tests, and validation gates before being described as implemented.

## Benchmarking and fuzzing

`rust/benches/README.md` documents benchmark methodology; there is no checked-in Criterion benchmark target. `rust/fuzz/README.md` documents candidate fuzz targets; there is no checked-in `cargo-fuzz` target. Do not report either activity as executed until its target and run evidence exist.
