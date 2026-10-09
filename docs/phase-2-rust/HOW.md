# HOW — develop, verify, and extend QEDTY Rust

Commands assume the shell is at the QEDTY repository root.

## Prerequisites

- Git checkout of shan-005/QEDTY.
- Rust installed via rustup, with rustfmt and Clippy components.
- Existing Python environment managed by uv.

Do not change the crate's edition (2021) or MSRV (1.78) merely to adopt a newer toolchain. Compatibility changes require deliberate CI and dependency review.

## Baseline commands

    cargo test --manifest-path crates/qedty-core/Cargo.toml
    cargo fmt --manifest-path crates/qedty-core/Cargo.toml -- --check
    cargo clippy --manifest-path crates/qedty-core/Cargo.toml --all-targets --all-features -- -D warnings
    uv run pytest -q
    for script in scripts/check_*_conformance.py; do
      uv run python "$script" || exit 1
    done

The existing required native CI command is the first line. Format and Clippy are recommended local Phase 2 gates; don't call them required CI checks until the workflow is changed.

**Manifest inventory note:** after reviewing changes, stage the intended files before running `scripts/check_manifest_inventory.py`. QEDTY derives its inventory from `git ls-files`, which excludes new untracked paths until staged. Review `git diff` and `git status` before staging.

## Starter geometry API

- Keeps qedty_core::ecef_wgs84(f64, f64, f64) -> (f64, f64, f64) as the compatibility API.
- Adds qedty_core::geometry::{GeodeticCoordinate, EcefPoint, GeometryError, try_ecef_wgs84}.
- The checked path rejects non-finite values, latitude outside [-90, 90], and longitude outside [-180, 180]; negative height is accepted.
- The typed adapter calls the existing ECEF calculation; it does not fork the WGS-84 formula.
- The shared ECEF fixture checks both old and checked API paths.

The checked validation policy is an additive Rust convenience, not yet a normative cross-language contract. Mirror and test the acceptance/error rules in Python and the applicable contract before production callers rely on them as QEDTY-wide behavior.

## How to add the next kernel

1. Find the actual Python implementation and tests; don't infer semantics from a proposed filename.
2. Record inputs, units, temporal semantics, ordering, missing/unknown behavior, error policy, tolerances and determinism guarantees.
3. Freeze Python-authored expected outputs under data/contracts/golden-vectors/.
4. Implement the smallest typed Rust API that meets the contract.
5. Have Rust integration tests read the same fixtures using include_str!, matching tests/golden.rs.
6. Add invariant/property tests; fuzz parsers or complex boundaries as appropriate.
7. Run format, Clippy, native tests, Python tests and all scripts/check_*_conformance.py checks.
8. Document dependency, API/MSRV or serialized-output changes before review.

## Planned module boundaries

    crates/qedty-core/src/lib.rs           small public surface / compatibility APIs
    crates/qedty-core/src/geometry.rs      implemented in starter
    crates/qedty-core/src/temporal.rs      planned after semantic mapping
    crates/qedty-core/src/graph.rs         planned bounded graph primitives
    crates/qedty-core/src/arrow.rs         planned contract-backed Arrow mapping
    crates/qedty-core/src/propagation.rs   planned numerical kernels
    crates/qedty-core/src/scenario.rs      planned scenario kernels
    crates/qedty-core/src/continuity.rs    planned continuity kernels
    crates/qedty-core/src/uncertainty.rs   planned uncertainty primitives
    crates/qedty-core/src/economics.rs     planned measured numerical kernels
    crates/qedty-core/src/optimization.rs  planned optimization primitives
    crates/qedty-core/src/analytics.rs     planned query/analytics operations
    crates/qedty-core/tests/golden.rs      shared contract fixtures

Don't create empty placeholder modules. Add each public module only when its implementation compiles and has contract-backed tests.

## Arrow and Python bridge

Map Arrow from contracts/arrow/core.contract.json; don't invent a Rust-only schema or assume Rust Arrow and PyArrow version numbers map one-to-one.

PyO3/maturin is a later gate. Preserve the existing src/qedty package layout. When binding work is selected, decide extension-module name, Python compatibility, error conversion, wheel/source builds and dependency pins in a dedicated reviewed increment. Consult RESEARCH_SOURCES.md.

## Benchmark discipline

Record kernel, fixture/version, input size, Rust compiler, build profile, host CPU/OS, warm-up/sample policy, time distribution and allocation/peak-memory metrics as relevant. Criterion is a candidate harness when a stable workload exists. A fuzz corpus is not a substitute for normative vectors.
