# Rust research baseline

**Research cutoff:** 2026-10-09. Check versions again at implementation/release time.

## Recommended platform/tooling decisions

| Area | Recommendation | Why / constraint |
|---|---|---|
| Compiler | Rust `1.99.0` pinned for current development tooling; `rust-version = 1.78` remains the existing crate MSRV pending a dedicated compatibility test | Current stable release was announced on 2026-10-01. Avoid silently increasing the minimum supported compiler. |
| Edition | Keep Edition 2021 through the initial Rust work | The current crate declares Edition 2021. Edition 2024 has been stable since Rust 1.85, but changing edition is a separate source-compatibility/lint review, not a performance optimization. |
| Workspace | One root Cargo workspace containing `crates/qedty-core` and the new conformance CLI | Preserves existing source location while making lockfile, tooling and future crate integration coherent. |
| Serialization | Continue using existing `serde` / `serde_json` until contract tests show a need to replace them | Canonical bytes and identity preimages are externally observable behavior; a serializer change needs vector-wide review. |
| Digest | Preserve SHA-256 and the existing deterministic-ID preimage/profile | IDs are cross-language contract behavior, not an implementation detail. |
| Geometry | Start from current WGS-84 ECEF function; add edge cases and validation additively | Current function is already covered by a shared vector, with a tolerance in meters. |
| Property tests | `proptest` for invariants and shrinking; introduce only with first meaningful property suite | Generated counterexamples help expose edge cases; do not use random-only tests without reproducible regression. |
| Benchmarks | Criterion in release mode for repeatable statistical microbenchmarks | Separate actual performance improvement from timer noise; record hardware/workload. |
| Fuzzing | `cargo-fuzz` / libFuzzer for complex parsers and adversarial input, in a separate non-blocking/nightly job initially | Fuzz tooling commonly needs nightly and LLVM sanitizer support. |
| Static quality | `cargo fmt`, Clippy with warnings denied, `cargo test --workspace --locked` | Fast, deterministic baseline suitable for required checks. |
| Supply chain | Commit Cargo.lock; add `cargo-deny` advisory/license/source checks after baseline review | Avoid introducing extra crates without checking license, maintenance, MSRV, source and advisories. |
| Python bridge | PyO3 + maturin candidate, deferred until APIs and vectors stabilize | Existing Python project uses setuptools; a build-backend switch can alter editable installs, wheel builds, and all CI matrices. |
| Coverage | `cargo-llvm-cov` as a local/CI coverage tool when meaningful thresholds are agreed | Coverage percentage alone is not a conformance or correctness proof. |

## Why not port every Python package immediately?

A naive one-Python-module-per-crate translation creates duplicated types and dependency churn before the internal API is stable. The safer path is to decompose `qedty-core` first, validate behavior against shared vectors, add a handful of independent kernels, and split into separate crates only when compile-time or dependency boundaries justify it.

## Why no Arrow dependency in the first Rust change?

The Arrow/Parquet/analytics work establishes the analytical data plane. Rust should define deterministic primitive behavior first and then add Arrow adapters where real schemas and batch operations exist. It is not necessary to make the tiny core depend on all future analytical libraries now.

## Why no PyO3 yet?

PyO3's official guide identifies Rust 1.83+ as the requirement for the currently reviewed 0.29.3 guide and describes native Python modules. Maturin's guide documents the mixed Python/Rust build backend and `abi3` options. Those are appropriate later, but `pyproject.toml` currently uses `setuptools.build_meta` and supports Python `>=3.12,<3.14`. Changing that during initial core refactoring would combine semantic, packaging, wheel, and CI risk in one patch. Use a separate ADR after the pure Rust interface is proven.

## Performance standard

The word “planetary-scale” is not a benchmark result. Establish a baseline before making speed claims; benchmark with `--release`, name the workload, record CPU/compiler/features and compare equivalent runs. Profile first, then optimize the hotspot. GPU work remains Phase 7.
