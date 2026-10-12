# CHANGELOG.md

# Changelog

All notable changes to QEDTY will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/2.0.0/).

QEDTY uses **PEP 440-compatible version identifiers** rather than Semantic Versioning.

## [Unreleased]

### Added

* Added bounded Python–Rust direct differential contracts for open-ended bitemporal membership and point/event timeline queries, including sequence ties and half-open/inclusive query boundaries.
* Added fixed cross-language cases for equivalent UTC instants expressed with different offsets, and equal/reversed half-open windows after UTC normalization.
* Added the bounded `graph.static.bfs` differential operation with an independent Python reference, native Rust adapter, reviewed fixed success/error cases, and an eighth replayable generated family.
* Added graph.static.scc as a bounded direct differential operation backed by the native SCC kernel, with deterministic label/component ordering, reviewed fixed oracles and an eleventh replayable generated family.
* Added named spherical Haversine distance and indexed radius-query differential operations, with an independent brute-force Python oracle and separately seeded twelfth/thirteenth generator families. These do not claim WGS-84 ellipsoidal parity.
* Added a bounded `temporal.index.query` differential operation for half-open `at`/overlapping scans, deterministic `all` ordering, idempotent duplicate insertion, key collisions, and get/remove/length/clear semantics.
* Added the accepted `temporal.history.query` differential contract for canonical `TemporalVersion` identity and selected `TemporalHistory` operations (`all`, `get`, `add`, bitemporal `as_of`, transaction-time-only `latest_known`), with independent ID oracles, fixed selection/error cases and a deterministic generated family.
* Added bounded `graph.static.shortest_path` conformance using the native additive-cost Dijkstra kernel, independent fixed path/error oracles, and a separately seeded deterministic generated family. This does not claim temporal-world-graph parity.
* Added the candidate `graph.temporal.snapshot` differential boundary against the production Python `TemporalGraph.snapshot` method, with four fixed half-open validity/UTC-offset oracles and a seventeenth deterministic ontology-backed generated family. This establishes snapshot membership only, not graph-history traversal or full temporal-world-graph parity.

* Added thirteen fixed swapped-input Python–Rust differential regressions covering the inverse mapping for all Allen interval relations; the accepted default inventory is 84 fixed + 448 generated comparisons (532 total).
* Expanded Python–Rust direct differential coverage to 71 fixed cases and seven deterministic generated families, totaling 519 comparisons with seed `20261010` and 64 generated inputs per family.
* Added an operation-level Python–Rust conformance matrix and a traceable research/standards register; documented unsupported or narrower parity boundaries explicitly.

### Changed

* Recorded the verified outcomes of the initial conformance expansion (PR #33) and bounded temporal-contract follow-up (PR #37); linked the operation matrix and engineering acceptance record from the README.

### Fixed

* Removed the UTF-8 byte-order mark from `scripts/verify.sh`, allowing the verification script to execute directly with its Bash shebang.

### Verified

* TemporalIndex scan/collision parity merged in PR #53 as `8130ac05a610b49e53470193513941fc376afc50` after **1,064/1,064** Python–Rust comparisons (including **82/82** `temporal.index.query` cases) and all five exact-head workflows passed; the post-merge CI, Rust, differential and smoke workflows also passed.
* TemporalVersion/TemporalHistory parity merged in PR #54 as [`fad44f62984614074799862ec5586f6dfdf4439e`](https://github.com/shan-005/QEDTY/commit/fad44f62984614074799862ec5586f6dfdf4439e): **1,145/1,145** differential comparisons passed (185 fixed + 960 generated, seed `20261010`, fifteen families, no unexpected skips); `temporal.history.query` passed **81/81**. All five required PR-head workflows passed on tested head `d7ed3c5a7a1ad270ccdcd3bb4fe27d77ed6ab531`; post-merge CI, Rust, Python–Rust Differential, and Platform Smoke workflows all passed on the merge commit. See [QEDTY CI](https://github.com/shan-005/QEDTY/actions/runs/38225392129), [QEDTY Rust](https://github.com/shan-005/QEDTY/actions/runs/38225392196), [Python–Rust Differential](https://github.com/shan-005/QEDTY/actions/runs/38225392186), and [Platform Smoke](https://github.com/shan-005/QEDTY/actions/runs/38225392267).

* The scoped temporal-edge/static-BFS slice (PR #42) passed **608/608** Python–Rust differential comparisons: **96 fixed + 512 generated**, seed `20261010`, 64 generated cases per each of eight families. Operation totals: `canonical_json 67/67`, `contract_result 2/2`, `geometry.ecef 72/72`, `graph.static.bfs 70/70`, `identity 69/69`, `interval.contains 79/79`, `quantity.convert 72/72`, `temporal.relation 91/91`, and `time.normalize 86/86`.
* Bitemporal membership and event-timeline parity (PR #49) was merged as [1aa505398945d49faf12b3396d4943dbff0d074b](https://github.com/shan-005/QEDTY/commit/1aa505398945d49faf12b3396d4943dbff0d074b): **763/763** differential comparisons passed (123 fixed + 640 generated), seed 20261010. All five required PR-head workflows passed on [56bad8d09daf85035478fcf1310c0c2cdf8cde4](https://github.com/shan-005/QEDTY/commit/56bad8d09daf85035478fcf1310c0c2cdf8cde4); main-branch CI, Rust, differential and smoke workflows also passed after merge.
* Static SCC parity (PR #50) merged as [337acc77700f604c0ac2cc882091417f6a5e011b](https://github.com/shan-005/QEDTY/commit/337acc77700f604c0ac2cc882091417f6a5e011b): **836/836** comparisons passed (132 fixed + 704 generated), and all eight visible PR-head checks plus the main-branch CI/Rust/differential/smoke checks passed.
* All five required workflows for scoped temporal-edge/static-BFS PR #42 passed on exact head `0b2d1d60878e56a9e7f656501dece0f09d4f75ff`: [QEDTY CI](https://github.com/shan-005/QEDTY/actions/runs/38145228618), [QEDTY Rust](https://github.com/shan-005/QEDTY/actions/runs/38145228592), [Platform Smoke](https://github.com/shan-005/QEDTY/actions/runs/38145228589), [Python–Rust Differential](https://github.com/shan-005/QEDTY/actions/runs/38145228585), and [Dependency Review](https://github.com/shan-005/QEDTY/actions/runs/38145228576). PR #42 was squash-merged as [`3546fbdf`](https://github.com/shan-005/QEDTY/commit/3546fbdf9a05d7a989ea530e782c7c3a7e059c5e). This accepts only the declared static directed BFS contract and listed temporal edge cases, not whole-domain parity.
* Following accepted PR #39, the full Python suite passed 244 tests with 67.24% total-suite coverage on Python 3.12 and 3.13.
* Following accepted PR #39, the differential suite passed 532/532 comparisons with seed `20261010` (84 fixed + 448 generated); operation totals and remaining parity boundaries are recorded in the engineering acceptance document.
* All eight visible PR #39 check runs passed before merge: [QEDTY CI](https://github.com/shan-005/QEDTY/actions/runs/38141225163), [QEDTY Rust](https://github.com/shan-005/QEDTY/actions/runs/38141225210), [Python–Rust Differential](https://github.com/shan-005/QEDTY/actions/runs/38141225164), [Platform Smoke](https://github.com/shan-005/QEDTY/actions/runs/38141225208), and [review check](https://github.com/shan-005/QEDTY/actions/runs/38141225209). PR #39 merged as [a80e0cd](https://github.com/shan-005/QEDTY/commit/a80e0cd704b45eed79468d064c963bcaf774c9fc).
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
