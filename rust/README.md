# Rust in QEDTY

This directory is the **Rust engineering and verification area**. It complements—not replaces—the production core at `crates/qedty-core/`.

## Current working components

- `crates/qedty-core/`: existing deterministic library, owned by the repository's current native CI contract.
- `rust/crates/qedty-conformance/`: a CLI that reads the already-committed, language-neutral core vectors and calls the current Rust API.
- `rust/scripts/verify.sh`: formatter, tests, Clippy, CLI conformance, and existing core tests.
- `rust/RUST_PLAN.md`: ordered implementation milestones and exit gates.

## Run

From the repository root:

```bash
cargo fmt --all -- --check
cargo test --workspace --locked
cargo clippy --workspace --all-targets --locked -- -D warnings
cargo run --locked -p qedty-conformance
./rust/scripts/verify.sh
```

The `qedty-conformance` CLI checks canonical JSON, deterministic identity, WGS-84 ECEF, UTC timestamp normalization, quantity conversion and contract-result normalization from shared vectors. `rust-expansion-conformance` additionally checks graph/spatial golden scenarios. These fixed checks are not a substitute for direct same-input differential comparison; see `docs/engineering/PYTHON_RUST_DIFFERENTIAL.md`.

## Do not duplicate semantics

Python remains QEDTY's semantic/reference authority. Rust kernels must be behavior-compatible with the existing Python implementation and contract fixtures. Do not create production Rust crates for every Python package before there is a stable API and a real dependency boundary. The planned crate map lives in `TARGET_TREE.md` and `crate-map.toml`; planned entries are not all implemented.
