# Phase 2 file tree — present vs planned

Legend: EXISTS = present at inspected base; STARTER = added in this increment; PLANNED = future Phase 2 deliverable, not an empty placeholder.

    QEDTY/
    ├── .github/workflows/ci.yml                         EXISTS: native job uses manifest path
    ├── contracts/
    │   ├── arrow/core.contract.json                     EXISTS: Arrow field contract
    │   └── json-schema/core.contract.schema.json        EXISTS: shared core schema
    ├── data/contracts/golden-vectors/core/
    │   ├── canonical_json.json                          EXISTS: canonical byte string
    │   ├── geometry_ecef.json                           EXISTS: WGS-84 ECEF fixture
    │   └── identity.json                                EXISTS: deterministic identity fixture
    ├── docs/phase-2-rust/
    │   ├── README.md                                    STARTER: charter and exit gates
    │   ├── HOW.md                                       STARTER: commands and workflow
    │   ├── FILE_TREE.md                                 STARTER: this tree
    │   ├── IMPLEMENTATION_MATRIX.md                      STARTER: reference/kernel mapping
    │   ├── DECISIONS.md                                 STARTER: accepted decisions/open gates
    │   └── RESEARCH_SOURCES.md                           STARTER: sources/rationale
    └── crates/qedty-core/
        ├── Cargo.toml                                   EXISTS: edition 2021, MSRV 1.78
        ├── src/
        │   ├── lib.rs                                   EXISTS plus module declaration
        │   ├── geometry.rs                              STARTER: checked typed WGS-84 boundary
        │   ├── temporal.rs                              PLANNED: UTC half-open interval behavior
        │   ├── graph.rs                                 PLANNED: deterministic graph primitives
        │   ├── arrow.rs                                 PLANNED: contract-backed Arrow mapping
        │   ├── propagation.rs                           PLANNED: propagation kernels
        │   ├── scenario.rs                              PLANNED: scenario kernels
        │   ├── continuity.rs                            PLANNED: continuity kernels
        │   ├── uncertainty.rs                            PLANNED: uncertainty primitives
        │   ├── economics.rs                              PLANNED: measured numerical kernels
        │   ├── optimization.rs                           PLANNED: optimization primitives
        │   └── analytics.rs                              PLANNED: query/analytics operations
        └── tests/golden.rs                              EXISTS plus checked-path assertion

## Deliberately not created

- A root Cargo.toml workspace: absent at the inspected base; CI targets the crate manifest explicitly.
- A duplicate rust/ source tree: crates/qedty-core is already the canonical Rust home.
- Empty future modules: create only with a Python reference, contract, fixture and compiling implementation.
- PyO3/maturin packaging or a duplicate qedty package: reserve for the later binding gate.
- Criterion/proptest/cargo-fuzz/Arrow dependencies: add only when needed by their implementation gate.
