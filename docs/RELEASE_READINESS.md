# Release readiness

QEDTY is an alpha engineering system. These are release gates, not a production-certification claim. A release is not ready merely because CI is green.

1. **Locked dependencies:** verify the committed `uv.lock` with the pinned uv version using `uv lock --check`; verify Rust dependencies with `cargo test --workspace --locked`. Regenerate and commit a lockfile only when its dependency metadata changes.
2. **Hosted verification:** review the required Python 3.12/3.13, native Rust, declared Rust MSRV, package-build, and Dependency Review results for the exact tag commit. The current workflow runs on Ubuntu; do not call this a multi-OS matrix until other operating systems are actually tested.
3. **Installed-distribution smoke tests:** install the built wheel in a clean environment and exercise import, `qedty validate`, and representative CLI operations for every Python version and platform claimed as supported.
4. **Representative data integrations:** expand integration tests against representative space, geospatial, economic, and infrastructure datasets, including source-specific parser boundaries and failure cases.
5. **Licensing and data rights:** validate source-specific licenses, redistribution terms, and parser conformance. Preserve the source version, retrieval time, license, and provenance for external datasets.
6. **Model evidence:** validate calibration and uncertainty assumptions using held-out data. Document the limits of causal, forecast, optimization, and planetary-scale performance claims.
7. **Security scope:** confirm the repository-security adapter remains an intentionally scoped integration. Document enablement, permission boundaries, and any retained or removed behavior.
8. **Published release contents:** for a version tag, inspect the public GitHub Release and verify that the wheel, source distribution, SHA256SUMS, SPDX SBOM, and SLSA provenance are present. Download the assets and check the published checksums; workflow artifacts alone are not durable public release assets.
9. **Recovery and support:** verify release rollback/recovery instructions and ensure a release can be traced to its source commit, workflow run, toolchain, and locked dependency state.

Do not claim Go, C/C++/CUDA, TypeScript/React, standalone SQL service, WIT/WASM, or full Rust domain parity until each has implementation code, contracts, tests, and evidence appropriate to that target.
