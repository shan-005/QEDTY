# CHANGELOG.md

# Changelog

All notable changes to QEDTY will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/2.0.0/).

QEDTY uses **PEP 440-compatible version identifiers** rather than Semantic Versioning.

## [Unreleased]

### Added

* Expanded Python–Rust direct differential coverage to 51 fixed cases and seven deterministic generated families, totaling 499 comparisons at the default seed/count.
* Added an operation-level Python–Rust conformance matrix and a traceable research/standards register; documented unsupported or narrower parity boundaries explicitly.

### Changed

* Recorded the accepted outcome of Cross-Language Conformance Expansion (PR #33) and linked the detailed engineering acceptance record from the README.

### Fixed

* Removed the UTF-8 byte-order mark from `scripts/verify.sh`, allowing the verification script to execute directly with its Bash shebang.

### Verified

* Full Python test suite: 233 passed; total-suite coverage 67.21% (above the 60% gate).
* Differential suite: 499/499 cases passed with seed `20261010`; all eight operation totals are recorded in the engineering acceptance document.
* Rust workspace: 77 tests passed across core, CLI integration, boundary invariants, fuzz regressions, golden vectors, graph/spatial conformance, and expansion tests.
* Ruff lint/format, mypy, `uv run qedty validate`, `uv lock --check`, and manifest inventory/link/JSON checks passed.
* Post-merge [QEDTY CI](https://github.com/shan-005/QEDTY/actions/runs/38126849216), [QEDTY Rust](https://github.com/shan-005/QEDTY/actions/runs/38126849124), [QEDTY Python–Rust Differential](https://github.com/shan-005/QEDTY/actions/runs/38126849169), and [Platform Smoke](https://github.com/shan-005/QEDTY/actions/runs/38126849131) all succeeded on merge commit [`6c86b3f`](https://github.com/shan-005/QEDTY/commit/6c86b3fca5d945f8e544635d9e0f084a0839c28f).

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
