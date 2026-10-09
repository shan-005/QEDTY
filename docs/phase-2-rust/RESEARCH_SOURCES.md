# Phase 2 research and source register

Research snapshot: 2026-10-09. Prefer the live repository and upstream documentation when implementing. These sources guide design; they do not override QEDTY contracts.

## QEDTY source of truth

| Source | Why it matters |
|---|---|
| [QEDTY README](https://github.com/shan-005/QEDTY/blob/main/README.md) | Defines Python as semantic/reference implementation and Rust as the small deterministic native core; other execution targets are future work. |
| [Core Cargo.toml](https://github.com/shan-005/QEDTY/blob/main/crates/qedty-core/Cargo.toml) | Actual package metadata, edition/MSRV and dependency surface. |
| [Rust core source](https://github.com/shan-005/QEDTY/blob/main/crates/qedty-core/src/lib.rs) | Current canonical JSON, SHA-256 identity and WGS-84 ECEF implementation. |
| [Rust golden tests](https://github.com/shan-005/QEDTY/blob/main/crates/qedty-core/tests/golden.rs) | Existing include_str! pattern for shared cross-language JSON vectors. |
| [Canonical JSON vector](https://github.com/shan-005/QEDTY/blob/main/data/contracts/golden-vectors/core/canonical_json.json) | Expected canonical JSON bytes; nested object keys ordered, arrays preserve order. |
| [Identity vector](https://github.com/shan-005/QEDTY/blob/main/data/contracts/golden-vectors/core/identity.json) | Fixed cross-language deterministic identity. |
| [ECEF vector](https://github.com/shan-005/QEDTY/blob/main/data/contracts/golden-vectors/core/geometry_ecef.json) | WGS-84 input/output with absolute tolerance in metres. |
| [Python temporal intervals](https://github.com/shan-005/QEDTY/blob/main/src/qedty/temporal/intervals.py) | UTC-aware extents, finite start < end and canonical half-open [start, end) semantics. |
| [Arrow core contract](https://github.com/shan-005/QEDTY/blob/main/contracts/arrow/core.contract.json) | Existing field boundary for later Rust/Python mapping. |
| [CI workflow](https://github.com/shan-005/QEDTY/blob/main/.github/workflows/ci.yml) | Native command uses cargo test --manifest-path crates/qedty-core/Cargo.toml; Python CI runs tests and conformance checks. |

## Official Rust/Cargo guidance

- [Cargo workspaces](https://doc.rust-lang.org/cargo/reference/workspaces.html): workspace members share a lockfile and target directory; avoid a root workspace until justified and CI migration is deliberate.
- [Cargo dependency resolver](https://doc.rust-lang.org/cargo/reference/resolver.html): resolver and Rust-version compatibility affect dependency selection; keep MSRV explicit.
- [Cargo tests](https://doc.rust-lang.org/cargo/guide/tests.html): unit tests can live beside source and integration tests in tests/, matching the existing golden-test seam.
- [Clippy usage](https://doc.rust-lang.org/clippy/usage.html): conventional lint path; make it required CI only after a clean baseline.
- [Criterion.rs](https://github.com/criterion-rs/criterion.rs): stable-Rust statistics-driven benchmarks for a later, reproducible workload.

## Rust/Python integration

- [Maturin project layout](https://github.com/PyO3/maturin/blob/main/guide/src/project_layout.md): mixed-layout and submodule guidance; QEDTY already has src/qedty, so avoid a second top-level package.
- [Maturin tutorial](https://www.maturin.rs/tutorial): extension build workflow; verify details when choosing a PyO3 version.
- [PyO3 user guide](https://pyo3.rs/): Rust/Python API, error conversion and compatibility reference.

Before later gates, re-check stable Rust, dependency MSRV, Python 3.12/3.13 wheel support, independent Arrow/PyArrow versions, and current proptest/cargo-fuzz/Criterion guidance. QEDTY's Python implementation and contracts take precedence over generic examples.
