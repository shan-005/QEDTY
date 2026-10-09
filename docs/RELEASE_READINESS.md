# Release readiness

QEDTY is an alpha engineering baseline, not a production-certification claim. A green CI badge is evidence only for the checks that ran on that exact commit; it is not a release certification.

## Automated checks available in the repository

Before cutting a release, confirm the latest successful hosted runs are for the exact tag candidate:

1. Python 3.12 and 3.13 tests, lint/format, type checks, CLI smoke commands, manifest inventory, and executable domain conformance scripts.
2. Rust workspace formatting, locked tests, Clippy with warnings denied, shared core golden-vector conformance, native-crate compatibility tests, and the declared Rust 1.78 minimum-supported-version test.
3. Locked dependency resolution, Python distribution build, and distribution metadata checks.
4. Dependency Review and the configured SLSA provenance workflow where their triggers and permissions apply.

Read the job logs and verify the tested commit SHA rather than relying on a green badge or a run from an older commit.

## Release checks to maintain

- **Lockfile integrity:** use the repository-pinned `uv` version; run `uv lock --check` and locked installs. Regenerate and commit `uv.lock` only after intentional dependency metadata changes, review the diff, and rerun the complete checks. Keep the root `Cargo.lock` current and use Cargo `--locked` commands.
- **Substantive test coverage:** the audited CI report passed 211 tests but reported 26.54% coverage across 8,495 statements. The full-suite CI command enforces a 26% floor with `--cov-fail-under=26`; `pyproject.toml` leaves the default report threshold at zero so focused conformance subsets do not fail against a full-suite threshold. This is a regression guard, not a production-readiness target or proof every domain path is tested. Add behavior-focused tests across domain packages and raise the floor deliberately as coverage improves. Do not treat a green suite or test count alone as evidence that every domain path is validated.
- **Installed distribution:** install the built wheel in a clean environment and exercise imports, `qedty validate`, and representative CLI operations for each Python version and platform claimed as supported.
- **Platform claims:** the current required hosted matrix runs on Ubuntu and covers Python 3.12/3.13 plus the declared Rust MSRV. Do not call it multi-OS validation or claim Windows/macOS support is tested until those environments are actually exercised.
- **Representative data integration:** expand and run integration tests against representative space, geospatial, economic, and infrastructure datasets. Fixture-only conformance does not prove behavior at real-world data volumes or for every source edge case.
- **Data rights and source fidelity:** verify dataset licenses/terms, version/vintage handling, parser conformance, acquisition metadata, and provenance for each external source before enabling it in a release profile.
- **Model validity:** evaluate calibration, sensitivity, and uncertainty assumptions against appropriate held-out or otherwise independently justified data. Do not present unvalidated model output as observation or an empirically identified causal estimate.
- **Software bill of materials:** generate an SPDX SBOM from the source and dependency manifests associated with the exact release tag; review licenses and vulnerabilities, and publish the SBOM as a release asset. A lockfile or Dependency Review run is not a substitute for an SBOM.
- **Artifact provenance and integrity:** publish the wheel, source distribution, SHA256SUMS, SPDX SBOM, and SLSA provenance with the versioned release. Download the public assets, verify checksums, and validate provenance against the distribution digests; a temporary workflow artifact alone is not durable release publication.
- **Operational scope and recovery:** keep repository-security adapters limited to their declared purpose; verify data redaction, access boundaries, rollback/recovery, and supported deployment assumptions before any operational rollout.

## Current non-claims

The current CI is an engineering gate, not production certification. The repository has not thereby demonstrated planetary-scale performance, full conformance to every mapped external standard, calibration across every domain, or production readiness. The required release job runs on Ubuntu only. Rust `contract_result`, `quantity`, and `time` APIs remain pending; their fixtures must not be reported as passing Rust implementation.

Update this checklist whenever release automation changes. Before marking the published-asset check green, exercise the updated pipeline with a real version tag and confirm the resulting public release assets.
