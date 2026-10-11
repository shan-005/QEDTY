# CHANGELOG.md

# Changelog

All notable changes to QEDTY will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/2.0.0/).

QEDTY uses **PEP 440-compatible version identifiers** rather than Semantic Versioning.

## [Unreleased]

### Added

* Added thirteen fixed swapped-input Python–Rust differential regressions covering the inverse mapping for all Allen interval relations; the candidate default inventory is 84 fixed + 448 generated comparisons.
* Expanded Python–Rust direct differential coverage to 71 fixed cases and seven deterministic generated families, totaling 519 comparisons with seed `20261010` and 64 generated inputs per family.
* Added an operation-level Python–Rust conformance matrix and a traceable research/standards register; documented unsupported or narrower parity boundaries explicitly.

### Changed

* Recorded the verified outcomes of the initial conformance expansion (PR #33) and bounded temporal-contract follow-up (PR #37); linked the operation matrix and engineering acceptance record from the README.

### Fixed

* Removed the UTF-8 byte-order mark from `scripts/verify.sh`, allowing the verification script to execute directly with its Bash shebang.

### Verified

* Full Python suite after temporal expansion: 243 passed; total-suite coverage 67.24% on Python 3.12 and 3.13 (above the 60% gate).
* Differential suite: 519/519 cases passed with seed `20261010` (71 fixed plus 448 generated); operation totals and scope boundaries are recorded in the engineering acceptance document.
* Rust workspace: 77 tests passed across core, CLI integration, boundary invariants, fuzz regressions, golden vectors, graph/spatial conformance, and expansion tests; minimum Rust 1.78 and Arrow IPC interoperability gates passed.
* Ruff lint/format, mypy, Bandit, dependency audit, package build/Twine metadata validation, `uv run qedty validate`, `uv lock --check`, manifest inventory, and CLI demos passed.
* Contract verification reports `status: ok`.
* API contract version verified as `1.0.0`; world graph schema verified as `qedty-world-graph@1.0.0`.
* QEDTY modeled demonstration executes successfully, and direct execution of `scripts/verify.sh` succeeds after removal of the UTF-8 BOM.
* Post-merge [QEDTY CI](https://github.com/shan-005/QEDTY/actions/runs/38126849216), [QEDTY Rust](https://github.com/shan-005/QEDTY/actions/runs/38126849124), [QEDTY Python–Rust Differential](https://github.com/shan-005/QEDTY/actions/runs/38126849169), and [Platform Smoke](https://github.com/shan-005/QEDTY/actions/runs/38126849131) all succeeded on merge commit [`6c86b3f`](https://github.com/shan-005/QEDTY/commit/6c86b3fca5d945f8e544635d9e0f084a0839c28f).
* For PR #37, all five required PR-head checks passed before merge: [QEDTY CI](https://github.com/shan-005/QEDTY/actions/runs/38132560494), [QEDTY Rust](https://github.com/shan-005/QEDTY/actions/runs/38132560447), [Python–Rust Differential](https://github.com/shan-005/QEDTY/actions/runs/38132560404), [Platform Smoke](https://github.com/shan-005/QEDTY/actions/runs/38132560364), and [Dependency Review](https://github.com/shan-005/QEDTY/actions/runs/38132560437). PR #37 merged as [`8cfd0de`](https://github.com/shan-005/QEDTY/commit/8cfd0de6601542be5d61cbfb65a6599b232390b7).

## [0.1a0] - 2026-10-06

QEDTY's initial alpha development baseline for evidence-backed planetary continuity intelligence.

### Added

* Core semantic and contract foundation.
* Ontology, evidence, temporal, spatial, graph, scenario, propagation, continuity, economics, counterfactual, and uncertainty capabilities.
* Intelligence, optimization, governance, sources, storage, orchestration, and API/output/CLI layers.
* JSON Schema, RDF, SHACL, Arrow, and Protobuf contract surfaces.
* Golden-vector conformance data for core, evidence, ontology, temporal, and scenario semantics.
* Rust native core with golden-vector conformance tests.
* Python semantic/reference implementation and CLI/API surfaces.
* Evidence, provenance, temporal, spatial, graph, scenario, propagation, uncertainty, economics, governance, and world-model components.
* Research, architecture, provenance, geospatial, economics, operations, algorithm, and release-readiness documentation.
* Repository CI, dependency, security, release, signing, and supply-chain workflow definitions.

### Changed

* Stabilized the project dependency and build configuration for the QEDTY alpha baseline.
* Established contracts and golden vectors as cross-language semantic conformance anchors.
* Established the project architecture separating semantic/reference responsibilities from high-performance native computation.

[Unreleased]: https://github.com/shan-005/QEDTY/compare/0.1a0...HEAD
[0.1a0]: https://github.com/shan-005/QEDTY/releases/tag/0.1a0
