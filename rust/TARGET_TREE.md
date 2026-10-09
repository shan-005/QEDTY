# QEDTY Rust target tree

This tree separates **current Rust tooling files** from the **later implementation targets**. It is intentionally grounded in the repository's existing `crates/qedty-core` layout.

## Immediate tree (files supplied by this bundle)

```text
QEDTY/
├── .github/
│   └── workflows/
│       └── rust.yml               # new; native checks, vector CLI
├── Cargo.toml                             # new root workspace; Python packaging unaffected
├── Cargo.lock                             # new root lock; regenerate/verify with Cargo on integration
├── rust-toolchain.toml                    # new pinned developer toolchain + tools
├── crates/
│   └── qedty-core/                        # EXISTING canonical crate; do not duplicate
│       ├── Cargo.toml                     # unchanged
│       ├── Cargo.lock                     # existing file; retire only after root lock is verified
│       ├── src/lib.rs                     # existing current implementation
│       └── tests/golden.rs                # existing 3 golden-vector tests
├── data/contracts/golden-vectors/core/   # EXISTING shared fixtures
│   ├── canonical_json.json
│   ├── geometry_ecef.json
│   ├── identity.json
│   ├── quantity.json                      # current Rust implementation pending
│   └── time.json                          # current Rust implementation pending
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
    ├── research/SOURCES.md
    ├── decisions/
    │   ├── ADR-0001-semantic-authority.md
    │   ├── ADR-0002-workspace-layout.md
    │   └── ADR-0003-python-binding-timing.md
    ├── scripts/verify.sh
    ├── benches/README.md
    ├── fuzz/README.md
    └── crates/
        └── qedty-conformance/
            ├── Cargo.toml
            ├── src/main.rs
            └── tests/cli.rs
```

## First production refactor target (not applied by this documentation scaffold)

```text
crates/qedty-core/
├── Cargo.toml
├── src/
│   ├── lib.rs              # public re-exports; keep existing API stable
│   ├── error.rs             # CoreError and typed validation errors
│   ├── types.rs             # EntityRef, TimeWindow, Quantity
│   ├── canonical.rs         # canonical JSON profile
│   ├── identity.rs          # SHA-256 and deterministic IDs
│   ├── geometry.rs          # WGS-84 ECEF + documented validation
│   └── tests.rs             # internal tests if useful
└── tests/
    ├── golden.rs            # preserve current cross-language tests
    ├── validation.rs        # malformed/edge inputs
    └── properties.rs        # proptest; add when dependency reviewed
```

Move one item at a time, preserve the re-exports in `lib.rs`, and keep `cargo test` green after every move. This refactor should be behavior-neutral.

## Later crate candidates (create only when the boundary is justified)

```text
crates/
├── qedty-core/              # existing; base types/errors/hash/canonicalization
├── qedty-temporal/          # later Rust temporal workstream; only after temporal API/vector set exists
├── qedty-spatial/           # later Rust spatial workstream; only after geometry scope exceeds core
├── qedty-graph/             # later Rust graph workstream; deterministic graph primitives
├── qedty-propagation/       # later deterministic-compute workstream; depends on core + graph/contracts
├── qedty-scenarios/         # later deterministic-compute workstream; only if independent crate boundary is useful
├── qedty-continuity/        # Rust milestone 2.6
├── qedty-uncertainty/       # Rust milestone 2.6; explicit numeric/epistemic contract
├── qedty-optimization/      # Rust milestone 2.6; benchmark-led
├── qedty-arrow/             # later Arrow adapter work; depends on the data-plane decision
└── qedty-python/            # late Rust integration; PyO3 only after API stabilizes
```

Do not create `qedty-model`, `qedty-ontology`, `qedty-evidence`, `qedty-economics`, `qedty-query`, `qedty-runtime`, `qedty-ffi`, or `qedty-wasm` just to make the tree look large. First prove what shared types and dependencies each crate owns. WIT/WASM, Go, and CUDA are separate future execution targets. They are not implemented by this Rust scaffold and require their own source, tests, and review gates.

## Tooling tree as the project grows

```text
rust/
├── decisions/               # architecture decision records
├── research/                # reviewed source links and evidence
├── scripts/                 # deterministic verify/benchmark helpers
├── benches/                 # bench methodology and named workloads
├── fuzz/                    # cargo-fuzz target project, when adopted
├── crates/qedty-conformance # executable bridge to shared vectors
└── results/                 # CI artifacts only; don't commit noisy local outputs
```

## More detailed Rust implementation map

These are **planned file names**, not all files to create in the initial patch. Create a file when its API has a Python reference, contract decision, and relevant tests.

```text
crates/qedty-core/
├── Cargo.toml
├── src/
│   ├── lib.rs
│   ├── error.rs
│   ├── types.rs
│   ├── canonical.rs
│   ├── identity.rs
│   ├── quantity.rs          # after quantity conversion contract is reviewed
│   ├── time.rs              # after normalization contract is reviewed
│   └── geometry/
│       ├── mod.rs
│       ├── wgs84.rs
│       └── validation.rs    # additive/fallible validation API
├── tests/
│   ├── golden.rs
│   ├── validation.rs
│   └── properties.rs        # add proptest only when properties are defined
└── benches/
    ├── canonical_json.rs    # after representative benchmark workloads exist
    ├── identity.rs
    └── geometry.rs

rust/crates/qedty-conformance/
├── Cargo.toml
├── src/main.rs
└── tests/cli.rs

rust/                         # engineering docs + shared integration tooling
├── HOW_TO_WORK.md
├── RUST_PLAN.md
├── ARCHITECTURE.md
├── CONFORMANCE.md
├── QUALITY_GATES.md
├── TARGET_TREE.md
├── RESEARCH_BASELINE.md
├── crate-map.toml
├── decisions/
│   ├── ADR-0001-semantic-authority.md
│   ├── ADR-0002-workspace-layout.md
│   └── ADR-0003-python-binding-timing.md
├── scripts/verify.sh
├── benches/README.md
├── fuzz/README.md
└── research/
    ├── SOURCES.md
    └── fixtures/             # audit copies only; executable checks read canonical data/

# Future only after each domain contract has an approved vector suite
crates/qedty-temporal/
├── Cargo.toml
├── src/lib.rs
├── src/interval.rs
├── src/relations.rs
├── src/timeline.rs
└── tests/golden.rs

crates/qedty-spatial/
├── Cargo.toml
├── src/lib.rs
├── src/wgs84.rs
├── src/operations.rs
└── tests/golden.rs

crates/qedty-graph/
├── Cargo.toml
├── src/lib.rs
├── src/model.rs
├── src/adjacency.rs
├── src/traversal.rs
└── tests/golden.rs

crates/qedty-propagation/
├── Cargo.toml
├── src/lib.rs
├── src/aggregation.rs
├── src/traversal.rs
├── src/intervention.rs
└── tests/golden.rs
```

### File creation rule

A planned file does not become an empty placeholder. Add it only alongside a useful API, unit tests, a shared vector, and the corresponding documentation. For a pure module decomposition, keep the old public API re-exported from `lib.rs` so downstream Rust users and future PyO3 bindings do not have to change imports merely because internal code was organized.
