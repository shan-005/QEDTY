# Release readiness

QEDTY is an alpha engineering baseline, not a production certification. The repository now commits both `uv.lock` and the workspace `Cargo.lock`; do not treat lockfile creation as an outstanding task. The release gate must verify committed dependency state and keep release claims tied to the exact source commit and artifacts.

## Automated checks available in the repository

Before cutting a release, confirm the latest successful GitHub Actions runs are for the exact commit/tag candidate:

1. Python 3.12 and 3.13 tests, lint/format, type checks, CLI smoke commands, manifest inventory, and executable domain conformance scripts.
2. Rust workspace formatting, locked tests, Clippy with warnings denied, shared core golden-vector conformance, native-crate compatibility tests, and the declared Rust 1.78 minimum-supported-version test.
3. Locked dependency resolution, Python distribution build, and distribution metadata checks.
4. Dependency Review and the configured release-provenance workflow where its trigger and permissions apply.

A successful job is evidence only for the checks that actually ran. Read the job logs and confirm the tested commit SHA rather than relying on a green badge or a run from an older commit.

## Release checks to maintain

- **Lockfile integrity:** use the repository-pinned `uv` version; run `uv lock --check` and locked installs. When dependencies change, regenerate and commit `uv.lock` deliberately, review the diff, and rerun the complete checks. Keep the root `Cargo.lock` current and use Cargo's `--locked` mode.
- **Representative data integration:** expand and run integration tests against representative space, geospatial, economic, and infrastructure datasets. Fixture-only conformance does not prove behavior on real-world data volumes or edge cases.
- **Data rights and source fidelity:** verify dataset licenses/terms, version/vintage handling, parser conformance, acquisition metadata, and provenance for each external source before enabling it in a release profile.
- **Model validity:** evaluate calibration, sensitivity, and uncertainty assumptions against appropriate held-out or otherwise independently justified data. Do not present an unvalidated model output as an observation or an empirically identified causal estimate.
- **Software bill of materials:** generate and validate a machine-readable SBOM for the exact release artifacts, review vulnerabilities and licenses, and retain it with the release evidence. The existence of a dependency lockfile or a Dependency Review check alone is not an SBOM.
- **Artifact provenance and integrity:** build the exact candidate from the reviewed tag, record checksums, and verify the generated provenance/attestation against the same artifact digests. Confirm the release artifacts and their verification evidence are actually published and retrievable.
- **Operational scope:** keep repository-security adapters limited to their declared purpose; verify data redaction, access boundaries, recovery procedures, and supported deployment assumptions for any operational rollout.

## Current non-claims

The current CI is an engineering gate, not release certification. The project has not thereby demonstrated planetary-scale performance, full conformance to every mapped external standard, calibration across every domain, or production readiness. Rust quantity/time and `contract_result` APIs remain pending; the shared conformance report must continue to identify them as unimplemented rather than passing.

Update this checklist whenever release automation changes so the documented steps remain consistent with the workflows actually checked into `.github/workflows/`.
