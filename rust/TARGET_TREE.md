# QEDTY Rust target tree

This document distinguishes the **current tracked Rust implementation** from **planned work**. It is an implementation map, not a promise that every proposed crate, benchmark, or fuzz target already exists.

## Current repository tree

```text
QEDTY/
├── Cargo.toml                         # Workspace manifest
├── Cargo.lock                         # Single committed workspace dependency lock
├── rust-toolchain.toml                # Development toolchain and components
├── crates/
│   └── qedty-core/
│       ├── Cargo.toml
│       ├── src/
│       │   ├── lib.rs
│       │   └── geometry.rs
│       └── tests/
│           └── golden.rs              # Shared core-vector integration tests
├── data/contracts/golden-vectors/core/
│   ├── canonical_json.json
│   ├── contract_result.json           # Rust API pending
│   ├── geometry_ecef*.json            # Base vector plus independent edge vectors
│   ├── identity.json
│   ├── quantity.json                  # Rust API pending
│   └── time.json                      # Rust API pending
└── rust/
    ├── ARCHITECTURE.md
    ├── CONFORMANCE.md
    ├── HOW_TO_WORK.md
    ├── QUALITY_GATES.md
    ├── README.md
    ├── RESEARCH_BASELINE.md
    ├── RUST_PLAN.md
    ├── TARGET_TREE.md
    ├── crate-map.toml
    ├── decisions/
    │   ├── ADR-0001-semantic-authority.md
    │   ├── ADR-0002-workspace-layout.md
    │   ├── ADR-0003-python-binding-timing.md
    │   └── README.md
    ├── research/
    │   ├── SOURCES.md
    │   └── fixtures/                  # Documentation audit copies, not canonical inputs
    ├── scripts/verify.sh
    ├── benches/README.md              # Method and candidate workloads only; no benchmark suite yet
    ├── fuzz/README.md                 # Plan only; no cargo-fuzz target yet
    └── crates/qedty-conformance/
        ├── Cargo.toml
        ├── src/main.rs
        └── tests/cli.rs
```

The root `Cargo.lock` is the only workspace dependency lock. Do not recreate a nested `crates/qedty-core/Cargo.lock`; use the root workspace commands with `--locked`.

## Current conformance boundary

The executable Rust surface currently covers canonical JSON, deterministic identity, and WGS-84 ECEF conversion. Geometry vectors include independently stated axis/boundary expected values and explicit tolerances. The CLI and core integration tests load the canonical fixtures under `data/contracts/golden-vectors/core/`.

The fixtures `contract_result.json`, `quantity.json`, and `time.json` are present as contract/reference inputs but do **not** mean the matching Rust APIs exist. Do not count these as Rust passes until production APIs, tests, and conformance support are implemented.

## Planned decomposition (not implemented source files)

Split the core only when each boundary has a reviewed API, a Python/reference contract, and suitable tests:

```text
crates/qedty-core/src/
├── lib.rs              # Public exports; keep existing API stable
├── error.rs            # Typed validation errors
├── types.rs            # Shared core value types
├── canonical.rs         # Canonical JSON profile
├── identity.rs          # Hashing and deterministic IDs
├── quantity.rs          # Only after quantity contract review
├── time.rs              # Only after normalization contract review
└── geometry/
    ├── mod.rs
    ├── wgs84.rs
    └── validation.rs    # Additive fallible APIs where required
```

These are targets, not files that should be created merely to make the tree look complete. Preserve current public exports and vector behavior during any behavior-neutral refactor.

## Possible future crate boundaries

Create additional crates only when a stable contract and a justified dependency boundary exist:

- `qedty-temporal`: time intervals, normalization and temporal operations;
- `qedty-spatial`: spatial operations beyond the current core geodesy primitive;
- `qedty-graph`: deterministic graph structures and algorithms;
- `qedty-propagation`, `qedty-scenarios`, `qedty-continuity`: domain kernels with shared vectors;
- `qedty-uncertainty`, `qedty-optimization`: explicit numerical and epistemic contracts;
- `qedty-arrow`: an adapter if the data-plane boundary justifies one;
- `qedty-python`: a Python binding only after the native API stabilizes and wheel/platform tests are defined.

Potential files under those targets are not current code. Do not create `qedty-model`, `qedty-ontology`, `qedty-evidence`, `qedty-economics`, `qedty-query`, `qedty-runtime`, `qedty-ffi`, or `qedty-wasm` without first establishing what contract and responsibility each would own.

Go, C/C++/CUDA, TypeScript/React, SQL service deployments, and WIT/WASM are separate future execution targets. They are not implemented by this Rust workspace and require their own sources, tests, and release gates.

## Verification expectations

For every new implemented kernel:

1. Identify the Python/reference behavior and contract.
2. Review independently sourced expected-value fixtures.
3. Test success, boundaries, invalid inputs, and documented errors.
4. Run shared-vector and differential tests where the same semantics exist in Python.
5. Add property tests or fuzzing when justified by the input boundary.
6. Establish reproducible release-mode benchmark evidence before making performance claims.
7. Update this tree and the conformance matrix when tracked implementation files actually change.

See `rust/CONFORMANCE.md` for the current vector status and `rust/QUALITY_GATES.md` for the engineering gates.
