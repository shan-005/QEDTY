# Research source register — QEDTY Rust

**Checked:** 2026-10-09. Links below are the primary/reference documentation for the decisions, rather than claims that every tool is already adopted in QEDTY.

| Topic | Reference | How it informs QEDTY |
|---|---|---|
| Current stable Rust | [Rust 1.99.0 announcement](https://blog.rust-lang.org/2026/10/01/Rust-1.99.0/) | Pin the current development toolchain for repeatable tooling; keep the declared crate MSRV as a separate tested promise. |
| WGS-84 ellipsoid | [EPSG:7030 — WGS 84 ellipsoid](https://epsg.io/7030-ellipsoid) and [NGA Geomatics — WGS 84](https://earth-info.nga.mil/?action=wgs84&dir=wgs84) | Independent defining parameters for checked-in ECEF axis/boundary vectors: semi-major axis 6,378,137 m and inverse flattening 298.257223563. |
| Cargo workspace | [Cargo workspaces reference](https://doc.rust-lang.org/cargo/reference/workspaces.html) | Use one workspace and root lockfile for the native members. |
| Edition compatibility | [Rust Edition Guide](https://doc.rust-lang.org/edition-guide/) | Avoid changing the existing Edition 2021 source as a side effect of Rust development. |
| PyO3 | [PyO3 user guide](https://pyo3.rs/) | Candidate for future native Python module; guide reviewed in this research snapshot was PyO3 0.29.3 and requires Rust 1.83+. |
| Maturin | [Maturin user guide](https://www.maturin.rs/) and [mixed project layout](https://github.com/PyO3/maturin/blob/main/guide/src/project_layout.md) | Documents Rust/Python package layout, wheels and build-backend integration; introduce only with a separate packaging change. |
| Property testing | [Proptest documentation](https://docs.rs/proptest/) and [Proptest book](https://altsysrq.github.io/proptest-book/) | Invariant testing and shrinking failing inputs to small reproducible cases. |
| Statistical benchmarks | [Criterion documentation](https://docs.rs/criterion/latest/criterion/) | Warm-up, measurement, statistical analysis, and comparison rather than single timing samples. |
| Fuzzing | [Rust Fuzz Book: cargo-fuzz](https://rust-fuzz.github.io/book/cargo-fuzz.html) | Coverage-guided fuzzing through libFuzzer; keep nightly requirements separate from stable CI. |
| Coverage | [cargo-llvm-cov](https://github.com/taiki-e/cargo-llvm-cov) and [rustc instrumentation coverage](https://doc.rust-lang.org/rustc/instrument-coverage.html) | Source-based coverage evidence when thresholds are agreed. |
| Dependency checks | [cargo-deny](https://github.com/EmbarkStudios/cargo-deny) | Advisory, license, ban and trusted-source checks as dependency policy matures. |
| QEDTY source of truth | [Repository](https://github.com/shan-005/QEDTY), [current README](https://github.com/shan-005/QEDTY/blob/main/README.md), [existing native crate](https://github.com/shan-005/QEDTY/tree/main/crates/qedty-core) | Establishes current source path, semantic authority, and existing core implementation instead of planning against a fictional repository tree. |

## Evidence-backed recommendations

1. **Do not upgrade edition/MSRV casually.** The current crate explicitly declares Edition 2021 and Rust 1.78; a current installed compiler is not proof the package must require that version.
2. **Do not migrate packaging yet.** The live `pyproject.toml` uses setuptools and supports Python 3.12/3.13. A maturin/PyO3 integration changes wheel build and import behavior, so isolate it from semantic changes.
3. **Do not port all domains first.** Get golden-vector conformance and benchmark discipline working, then expand by dependency order.
4. **Do not report unimplemented vectors as passes.** The current Rust crate and conformance executables implement quantity conversion and timestamp normalization against the shared `quantity.json` and `time.json` fixtures. Keep documentation tied to the exact runner output; broader randomized Python–Rust differential coverage is a separate engineering acceptance gate.
5. **Do not treat this research as immutable.** Re-check tool versions, support matrices and advisories when adding dependencies and before release.
