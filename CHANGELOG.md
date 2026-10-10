# CHANGELOG.md

# Changelog

All notable changes to QEDTY will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/2.0.0/).

QEDTY uses **PEP 440-compatible version identifiers** rather than Semantic Versioning.

## [Unreleased]

### Fixed

* Removed the UTF-8 byte-order mark from `scripts/verify.sh`, allowing the verification script to execute directly with its Bash shebang.

### Verified

* Full Python verification suite passes: 203 tests passed with 1 expected skip.
* Contract verification reports `status: ok`.
* API contract version verified as `1.0.0`.
* World graph schema verified as `qedty-world-graph@1.0.0`.
* QEDTY modeled demonstration executes successfully.
* Direct execution of `scripts/verify.sh` succeeds after removal of the UTF-8 BOM.

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
