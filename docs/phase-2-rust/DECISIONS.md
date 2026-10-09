# Phase 2 decision log

## Accepted for this starter

1. crates/qedty-core remains the one Rust home; no root workspace or duplicate rust/ tree now.
2. Preserve qedty_core::ecef_wgs84(f64, f64, f64) -> (f64, f64, f64).
3. The typed geometry adapter delegates to the existing calculation; do not fork the WGS-84 formula.
4. No new dependency is required; this code uses thiserror already in the core manifest.
5. Keep edition 2021 and MSRV 1.78 unless a separate decision and CI evidence justify raising them.
6. Never change expected golden values merely to make Rust pass.
7. Checked coordinate ranges are an additive Rust convenience, not the QEDTY-wide semantic contract yet. Mirror acceptance/error rules in Python and update contracts before depending on them cross-language.

## Decisions for later gates

- Temporal representation: decide only after assessing UTC normalization, precision, serialization, unbounded ends and RFC 3339 behavior.
- Numeric parity: define tolerances and rounding per kernel; don't claim bit-for-bit equality without evidence.
- Randomness: specify RNG algorithm, seed format and draw order before Monte Carlo/uncertainty ports.
- Graph ordering: establish whether output order is semantic or canonicalized.
- Arrow: map the existing field contract and separate in-memory interchange from Parquet/full Phase 3 data plane.
- Benchmarking: add Criterion after defining a stable workload and baseline.
- Property/fuzz tooling: add proptest/cargo-fuzz after dependency/MSRV review.
- Python binding: decide PyO3/maturin module name, Python compatibility, error conversion, wheel and source distribution in a dedicated PR.
- Workspace: consider only when multiple actual Rust crates justify the CI/lockfile/resolver change.

## Out of scope

No semantic rewrite, DB backend, gRPC service, Arrow Flight server, CUDA code, Go service, web UI, WASM component or external data ingestion layer.
