# QEDTY Cross-Language Conformance Expansion

> **Authoritative current status — 15 October 2026 (Phase 4 bounded closeout).** PR #69 is merged, all required PR-head and post-merge workflows passed, and the matrix has zero remaining `PHASE4_GAP` rows. This closes only the explicitly accepted operation-level scope; it does not claim whole-domain Python–Rust parity. The broader follow-up plan is tracked in [`CROSS_LANGUAGE_CONFORMANCE_FOLLOW_UP.md`](CROSS_LANGUAGE_CONFORMANCE_FOLLOW_UP.md); those workstreams do not reopen this bounded acceptance gate.

**Latest accepted baseline:** PR #69 was tested at [`6feae34a09447dee75c92ea92a6dc852a273bc7d`](https://github.com/shan-005/QEDTY/commit/6feae34a09447dee75c92ea92a6dc852a273bc7d) and merged as [`4bd70a4912f3f0aaaeaf0030586d4f7cd3732fd8`](https://github.com/shan-005/QEDTY/commit/4bd70a4912f3f0aaaeaf0030586d4f7cd3732fd8).

**Control-plane PR #66 verification:** all five required checks passed on exact PR head [`ac4607b20ba9150d8fb04fa23589bb80232e50cd`](https://github.com/shan-005/QEDTY/commit/ac4607b20ba9150d8fb04fa23589bb80232e50cd): [QEDTY CI](https://github.com/shan-005/QEDTY/actions/runs/38253413532), [QEDTY Rust](https://github.com/shan-005/QEDTY/actions/runs/38253413360), [Python–Rust Differential](https://github.com/shan-005/QEDTY/actions/runs/38253413559), [Platform Smoke](https://github.com/shan-005/QEDTY/actions/runs/38253413503), and [Dependency Review](https://github.com/shan-005/QEDTY/actions/runs/38253413731). The change merged as the baseline commit above.

**Accepted bounded operations added after the older PR #57 baseline:** [PR #59](https://github.com/shan-005/QEDTY/pull/59) valid-time temporal graph snapshot; [PR #60](https://github.com/shan-005/QEDTY/pull/60) bitemporal temporal-graph traversal; [PR #61](https://github.com/shan-005/QEDTY/pull/61) temporal-graph history traversal integration/closeout; [PR #62](https://github.com/shan-005/QEDTY/pull/62) static weakly connected components; [PR #64](https://github.com/shan-005/QEDTY/pull/64) WGS-84 ECEF inverse conversion; and [PR #65](https://github.com/shan-005/QEDTY/pull/65) WGS-84 ellipsoidal inverse-geodesic distance. The duplicate/abandoned candidates #58 and #63 were not merged and are not acceptance evidence.

**PR #67 static PageRank acceptance:** exact tested head [`38054f9e9669b2fa3407e13347ce9ded42add324`](https://github.com/shan-005/QEDTY/commit/38054f9e9669b2fa3407e13347ce9ded42add324) passed all five required pull-request workflows: [QEDTY CI](https://github.com/shan-005/QEDTY/actions/runs/38255239087), [QEDTY Rust](https://github.com/shan-005/QEDTY/actions/runs/38255238996), [Python–Rust Differential](https://github.com/shan-005/QEDTY/actions/runs/38255238920), [Platform Smoke](https://github.com/shan-005/QEDTY/actions/runs/38255239089), and [Dependency Review](https://github.com/shan-005/QEDTY/actions/runs/38255241606). PR #67 merged as `808b3e73f57c3f3638fed4f177097453933c0288`.

**Verified PR #65 head:** `cea15b99783168bfb2cdc0a8c0c9156e127dd5ff`. All five required pull-request workflows passed on that exact head: [QEDTY CI](https://github.com/shan-005/QEDTY/actions/runs/38250705256), [QEDTY Rust](https://github.com/shan-005/QEDTY/actions/runs/38250705271), [Python–Rust Differential](https://github.com/shan-005/QEDTY/actions/runs/38250705397), [Platform Smoke](https://github.com/shan-005/QEDTY/actions/runs/38250705263), and [Dependency Review](https://github.com/shan-005/QEDTY/actions/runs/38250705257).

## Phase 4 disposition

Phase 4 is **closed for the matrix-defined bounded conformance scope**. PR #69 accepted the four remaining bounded operations, the matrix has no `PHASE4_GAP` rows, and all required hosted checks passed. This does not assert whole-domain parity.

The matrix uses `ACCEPTED_BOUNDED_SCOPE` for operations with direct same-input evidence and `DEFERRED_BY_DESIGN` for areas without an approved matching Python–Rust contract. Broader application domains are not presumed to require a Rust port.

## Bounded static PageRank contract — graph.static.pagerank@1

PR #67 adds a real Python reference (static_pagerank_labels) and a Rust adapter over DirectedGraph::pagerank. The request contains nodes, directed edges as label pairs, iterations in [1, 1000], and damping finite in (0, 1). Labels are trimmed and blank labels rejected; edge endpoints implicitly add nodes; duplicate edges count as distinct outgoing arcs. Scores start uniform, dangling-node mass is redistributed uniformly on each sweep, exactly the requested iteration count is applied, scores are normalized, and the result is a vector ordered by ascending unique label.

The contract is deliberately unweighted and fixed-iteration. It does not claim parity for weighted transitions, convergence-based stopping, temporal filters/relationship types, or the full temporal world graph. Independent expected-value fixtures cover sink/dangling behavior, a two-node cycle, a three-node chain, duplicate arcs, implicit endpoints/trimmed labels, empty graphs, invalid damping/iteration bounds and malformed edges. A twenty-second replayable generated family uses seed 20261010 and 64 inputs by default. The exact-head workflow results on PR #67 are the acceptance evidence; this bounded operation does not imply whole-domain graph parity.

## Bounded static maximum-flow contract — graph.static.max_flow@1

PR #68 defines direct scalar-value parity between the Python reference helper `static_max_flow_value` and Rust `DirectedGraph::max_flow`. Inputs are `nodes`, directed `edges` as `[from, to, capacity]` triples, `source`, and `sink`. Labels are trimmed; edge endpoints implicitly add nodes; capacities must be finite and non-negative; parallel capacities for the same ordered pair are aggregated; residual adjacency is traversed lexically; source and sink must exist and differ. The output is the scalar maximum-flow value.

Independent fixed oracles cover a single edge, bottleneck network, residual rerouting, antiparallel arcs, parallel capacity aggregation, zero capacity, a disconnected target, trimmed/implicit labels and malformed/invalid input. A twenty-third deterministic generated family adds 64 integer-capacity graphs per default run using seed `20261010`. This does not claim parity for QEDTY's richer temporal relationship-level flow API: temporal filtering, relationship-level flow decomposition, provenance and cut-certificate parity remain excluded.

### Four-gap acceptance and closeout record

PR #69 accepted closed geographic bounding-box membership, propagation contribution aggregation, scalar weighted mean, and integer 0/1 knapsack.

Acceptance evidence: 21 new fixed cases; 2,002/2,002 local differential comparisons with seed `20261010` and 64 generated cases per family; all nine local quality gates passed; all five required PR-head workflows passed; and all four post-merge workflows passed on `4bd70a4912f3f0aaaeaf0030586d4f7cd3732fd8`.

The shared `propagation.aggregate` contract rejects non-finite and out-of-range inputs before delegating valid contributions to the Python reference helper. The helper's standalone clamping behavior for out-of-range values is outside this shared contract and is not claimed as Python–Rust parity.

The four bounded gaps are closed. Broader spatial-index/CRS behavior, the full time-aware propagation engine, uncertainty distributions/sampling/calibration, and USD-budget portfolio optimization remain outside this parity claim. Rust-only kernels without an approved Python reference remain deferred by design.

### Rules for every remaining operation

The Python reference remains the semantic authority. Each added operation must have a versioned shared boundary, actual reference and Rust calls on the same logical input, independent fixed expected values, explicit invalid-input/error cases, deterministic generated inputs (seed `20261010`, 64 per family unless reviewed otherwise), operation-level totals and no unexpected skips. Update the matrix, schema allowlist, case files, Python reference adapter, Rust adapter, focused tests and engineering record together. Run the repository’s required hosted workflows on the exact candidate head; after merge, verify the actual merge commit. Do not merge a red/incomplete candidate, do not manufacture evidence, and do not state Phase 4 is complete while any `PHASE4_GAP` remains.

---

## Execution and acceptance record — base expansion (PR #33)

This base implementation was merged in [PR #33](https://github.com/shan-005/QEDTY/pull/33). The merge commit is `6c86b3fca5d945f8e544635d9e0f084a0839c28f`. The original local checkout was synchronized to that commit at that stage; PR #34 and PR #37 subsequently advanced `main`, so the original checkout must be fast-forwarded again.

- **Fixed differential cases:** 51, including all thirteen Allen relations and reviewed negative cases.
- **Default differential run:** 499/499 cases passed with `--generated-count 64 --seed 20261010`; seven generated families and eight supported operation IDs were exercised. Totals by operation: `canonical_json 67/67`, `contract_result 2/2`, `geometry.ecef 72/72`, `identity 69/69`, `interval.contains 70/70`, `quantity.convert 72/72`, `temporal.relation 78/78`, and `time.normalize 69/69`. No unexpected skips were reported.
- **Python:** 233 tests passed; total-suite coverage was 67.21%, above the repository's 60% gate. Focused differential tests passed (8 tests).
- **Rust:** 77 tests passed across core, CLI integration, boundary invariants, fuzz regressions, golden vectors, graph/spatial conformance, and expansion tests. Rust formatting and Clippy with warnings denied passed.
- **Quality and inventory:** Ruff lint/format, mypy, `uv run qedty validate`, `uv lock --check`, and the manifest inventory/link/JSON validation passed. Inventory matched 577 tracked paths.
- **Post-merge hosted CI:** [QEDTY CI](https://github.com/shan-005/QEDTY/actions/runs/38126849216), [QEDTY Rust](https://github.com/shan-005/QEDTY/actions/runs/38126849124), [Python–Rust Differential](https://github.com/shan-005/QEDTY/actions/runs/38126849169), and [Platform Smoke](https://github.com/shan-005/QEDTY/actions/runs/38126849131) all completed successfully on the merge commit.

These results accept the base implementation in PR #33—not exhaustive Python–Rust parity. The bounded timestamp/window subset was accepted in PR #37, Allen inverse-mapping regressions in PR #39, and the scoped temporal-edge/static-BFS slice in PR #42. Additional temporal, graph, spatial, propagation, uncertainty, and optimization operations still require independent semantic contracts and verification.

## Temporal-contract depth follow-up — accepted in PR #37

The bounded temporal follow-up was merged in [PR #37](https://github.com/shan-005/QEDTY/pull/37) at [`8cfd0de6601542be5d61cbfb65a6599b232390b7`](https://github.com/shan-005/QEDTY/commit/8cfd0de6601542be5d61cbfb65a6599b232390b7).

- **Additional fixed cases:** 20, increasing the fixed inventory from 51 to **71**. They cover offset-driven calendar rollover, the supported ±23:59 offset boundary, year-range endpoints, UTC normalization underflow/overflow, malformed date/time/offset inputs, half-open interval boundaries, unbounded ends, and reversed intervals.
- **Differential run:** **519/519 comparisons passed** with seed `20261010` and `generated_per_family=64`: 71 fixed + 448 generated over seven deterministic families. Operation totals: `canonical_json 67/67`, `contract_result 2/2`, `geometry.ecef 72/72`, `identity 69/69`, `interval.contains 77/77`, `quantity.convert 72/72`, `temporal.relation 78/78`, and `time.normalize 82/82`.
- **Python:** 243 tests passed; coverage was **67.24%** on both Python 3.12 and 3.13, above the repository 60% gate.
- **Rust:** 77 workspace/conformance tests passed; Rust formatting, Clippy, shared vectors, graph/spatial checks, benchmark-harness compilation, Arrow IPC interoperability, and the declared Rust 1.78 minimum-toolchain test passed.
- **Other gates:** Ruff lint/format, mypy, Bandit, dependency audit, package build and Twine metadata validation, `uv run qedty validate`, manifest inventory, legacy-identifier/milestone audit, CLI demonstrations, and `uv lock --check` passed.

All five required PR-head workflows passed before merge: [QEDTY CI](https://github.com/shan-005/QEDTY/actions/runs/38132560494), [QEDTY Rust](https://github.com/shan-005/QEDTY/actions/runs/38132560447), [Python–Rust Differential](https://github.com/shan-005/QEDTY/actions/runs/38132560404), [Platform Smoke](https://github.com/shan-005/QEDTY/actions/runs/38132560364), and [Dependency Review](https://github.com/shan-005/QEDTY/actions/runs/38132560437).

The temporal parser change fixed a demonstrated mismatch: Python's `datetime.fromisoformat` could normalize a malformed offset such as `+14:60` rather than reject it. The Python reference now validates the supported timestamp syntax and offset fields before conversion and maps UTC range overflow/underflow into the declared timestamp error. This is a bounded profile, not exhaustive RFC 3339 grammar or comprehensive timestamp standards certification.

The expansion remains operation-level conformance, not whole-domain parity. The fixed corpus has a swapped-input regression pair for each of the thirteen Allen relations, and PR #42 adds fixed pairs for equivalent UTC instants across representative positive/negative offsets plus equal/reversed windows after offset normalization. Those specific fixed-case gaps are accepted; bitemporal/timeline parity remains deferred until matching APIs and versioned semantics are specified.

## Bounded static weighted shortest path — operation contract

The `graph.static.shortest_path` contract is intentionally narrower than the ontology-backed temporal world-graph. Inputs use node labels, directed edge triples `[from, to, cost]`, a source and a target. Labels are trimmed; edge endpoints implicitly add nodes; costs must be finite and non-negative. The output is the inclusive node path with additive cost, or JSON `null` for an unreachable target. Equal-cost predecessor selection follows the existing native Dijkstra kernel's settled-label ordering and smaller-parent rule. This operation does not include relationship IDs, valid-time filtering, provenance, uncertainty, or snapshots.

Acceptance requires independent fixed-oracle cases, deterministic generated same-input cases, matrix/schema path validation, exact-head differential execution, and all required hosted workflows. Do not interpret this one operation as completed graph-domain or Phase 4 parity.

## Purpose and non-goals

This milestone expands the set of behaviors that are demonstrably conformant between QEDTY's Python reference APIs and corresponding Rust kernels. It does not assert that Rust is a second semantic authority or that every Python application module must be ported. A domain only enters direct conformance when both implementations expose a deliberately shared semantic boundary.

The initial PR #33 bundle made two concrete expansions to the existing testing system:

1. Added ten fixed differential cases for JSON, identity, quantities, timestamp normalization, interval membership and Allen interval relations.
2. Extended the deterministic generator from five to seven families by adding interval-membership and Allen-relation inputs. With the default `--generated-count 64`, this changes the intended run size from 41 fixed + 320 generated = 361 comparisons to 51 fixed + 448 generated = 499 comparisons. These are expected counts from the bundle inputs, not a test-pass claim.

It also added a checked-in domain-by-domain matrix, a test which validates the matrix's status vocabulary and repository paths, a research/standards register, and a safe bundle-application script. The current graph, spatial-index, bitemporal-timeline, propagation, uncertainty and optimization rows remain explicitly scoped rather than being granted broad parity claims.

## Starting source of truth

At the reviewed baseline:

- The direct differential runner supports eight operation IDs: `canonical_json`, `identity`, `quantity.convert`, `time.normalize`, `geometry.ecef`, `contract_result`, `interval.contains`, and `temporal.relation`.
- The committed fixed inventory contains 41 cases and one fixed case for each of the thirteen Allen relations.
- The generated run has five families: canonical JSON, identity, quantity conversion, ECEF geometry and timestamp normalization.
- The current GitHub Actions workflow runs the locked Rust workspace tests, `cargo fmt`, Clippy with warnings denied, the differential case contract tests and the native same-input differential command.
- The current native graph primitive is documented as narrower than QEDTY's Python temporal world-graph. The current Rust spatial primitive uses a spherical mean-Earth-radius model and is not a drop-in replacement for all Python geospatial operations.

Relevant source files should be read from the target checkout, not assumed unchanged if `main` has advanced since the reviewed baseline.

## Matrix statuses

`docs/engineering/CROSS_LANGUAGE_CONFORMANCE_MATRIX.csv` is the required scope inventory. Allowed status values mean:

- `DIRECT_DIFFERENTIAL`: same-input Python/Rust comparison exists for the precise operation described; it does not mean all behavior in that domain is covered.
- `SHARED_GOLDEN_ONLY`: both implementations or related harnesses use selected golden expectations, but direct same-input Python/Rust parity has not been established for the complete surface.
- `LANGUAGE_UNIT_ONLY`: local language-specific tests exist; they do not establish cross-language equivalence.
- `NO_SHARED_CONTRACT`: a semantic boundary must be agreed and versioned before direct parity can be asserted.
- `PYTHON_ONLY`: no Rust counterpart is currently claimed for the listed application domain.

The matrix deliberately uses operation-level precision. A single passing kernel never makes the entire domain green.

## Conformance rules

1. Python implementation and versioned language-neutral contracts are the behavioral reference. Do not copy Rust output into a golden vector to make a failure disappear.
2. Invoke production Python and Rust functions on the same logical input. The adapter must remain protocol glue, not an independent reimplementation of application semantics.
3. Exact contract values (canonical text, identities, normalized timestamp strings, enum labels and error categories) use exact comparisons.
4. Approximate numerical comparisons require a per-case absolute/relative tolerance, units, a rationale and independently reviewed expected values where available. Reject non-finite numerical results unless the contract explicitly allows them.
5. Negative cases compare stable categories, not raw exception wording. Both failure shape and validation boundary matter.
6. Minimize every confirmed mismatch and keep it permanently as a fixed regression case with a unique ID.
7. Keep generated inputs deterministic and replayable. The seed, generated count, toolchain versions and command must appear in the CI evidence or pull-request record.
8. Property/metamorphic relations complement fixed vectors; they do not replace independently reviewed expected examples.
9. Keep experimental fuzzing separate from stable required CI if it requires nightly or non-portable sanitizer support.
10. Add an adapter only after writing down the matched semantic boundary and the intentionally excluded behavior.

## Original implementation plan and remaining follow-up

### Gate A — Baseline and scope (completed for PR #33)

- Record the reviewed commit, local commit, Python/Rust versions, workflow URLs and current fixed/generated counts.
- Review this matrix and correct paths/statuses against the actual target checkout.
- Update the stale repository README milestone entry so Systematic Python–Rust Differential Testing is recorded as completed and Cross-Language Conformance Expansion as current.
- Do not change production algorithms in the baseline-only change.

### Gate B — Shared-core edge expansion (completed for PR #33)

- Integrate `data/contracts/differential/cases/cross_language_edges.json`.
- Extend `generate_cases()` with deterministic `interval.contains` and `temporal.relation` families while leaving the existing five-family generated sequence intact.
- Update differential tests to expect seven reproducible families and permit additional fixed relation cases while asserting that every one of the thirteen relation labels remains represented.
- Run the Python fixed-oracle tests first, then the native differential command. Treat every mismatch as a real failure to investigate; do not weaken comparison modes.

### Gate C — Temporal depth (bounded timestamp/window and offset-normalization edge cases accepted in PRs #37 and #42; broader temporal parity remains)

The PR #37 follow-up added 20 fixed timestamp/window regressions and corrected the demonstrated malformed-offset mismatch. PR #39 added fixed swapped-input regressions for all thirteen Allen inverse relations. PR #42 then added equivalent-instant pairs across representative positive and negative UTC offsets and equal/reversed windows whose endpoints require offset normalization. **At the PR #42 checkpoint**, bitemporal/timeline parity was still pending; it was subsequently accepted in the bounded scopes recorded under PRs #49, #53, #54 and #59–#61. Those later operations remain separately bounded and do not imply whole-domain temporal-world-graph parity.


## Allen inverse-regression acceptance — PR #39

PR [#39](https://github.com/shan-005/QEDTY/pull/39) was merged at [a80e0cd704b45eed79468d064c963bcaf774c9fc](https://github.com/shan-005/QEDTY/commit/a80e0cd704b45eed79468d064c963bcaf774c9fc).

- **Fixed inventory:** 84 cases (71 prior cases plus 13 swapped-input inverse cases).
- **Differential run:** **532/532 comparisons passed**, seed `20261010`, 64 generated cases in each of seven families. Per-operation totals: `canonical_json 67/67`, `contract_result 2/2`, `geometry.ecef 72/72`, `identity 69/69`, `interval.contains 77/77`, `quantity.convert 72/72`, `temporal.relation 91/91`, and `time.normalize 82/82`. The test verifies every canonical Allen fixture has a swapped-input fixed case with the correct inverse label.
- **Python:** 244 tests passed with 67.24% total-suite coverage on both Python 3.12 and 3.13.
- **Rust:** 77 workspace/conformance tests passed.
- **PR-head checks:** all eight visible check runs passed, including Python 3.12/3.13 quality, package, native compatibility, Rust workspace, differential, smoke, and review. See [QEDTY CI](https://github.com/shan-005/QEDTY/actions/runs/38141225163), [QEDTY Rust](https://github.com/shan-005/QEDTY/actions/runs/38141225210), [Python–Rust Differential](https://github.com/shan-005/QEDTY/actions/runs/38141225164), [Platform Smoke](https://github.com/shan-005/QEDTY/actions/runs/38141225208), and [review check](https://github.com/shan-005/QEDTY/actions/runs/38141225209).

This proves the declared inverse-mapping fixtures for the shared Allen-relation operation. It does not prove complete temporal ontology, bitemporal/timeline, or whole-domain Python–Rust parity.
### Gate D — Graph, spatial, propagation and uncertainty (status refreshed 2026-10-12)

The accepted bounded operations now include static BFS, SCC, weighted shortest path and WCC; valid-time temporal graph snapshots; bitemporal temporal-graph reachability/history traversal; spherical Haversine/radius query; WGS-84 ECEF forward/inverse conversion; and WGS-84 ellipsoidal inverse-distance parity. See the `phase4_disposition` column in the matrix for the current status of each bounded scope.

The remaining graph direct-differential candidates are PageRank and max-flow. Python and Rust functions exist for both, but their input/output, tie, numeric/convergence, error and resource semantics still need versioned contracts. Rust also exports `most_reliable_path`; no matching Python reference API currently exists, so the matrix marks that kernel `DEFERRED_BY_DESIGN` until a real Python semantic/reference API is approved and implemented. Broader spatial-index parity also remains distinct from the accepted distance-only operations.

For propagation, uncertainty and optimization, do not add adapters by comparing superficially similar functions. The Python propagation engine is time-aware and provenance-bearing; Rust `propagate_linear` is a synchronous numeric kernel. Rust interval/weighted-mean primitives are not the full Python uncertainty API. Rust integer-capacity/value knapsack is not automatically equivalent to Python's USD-budget portfolio optimizer. Each workstream must select and approve one comparable operation before implementation.

Each newly accepted operation still requires an updated schema allowlist, independent fixed vectors, deterministic generated same-input cases, focused tests, matrix entries and exact-head CI. A passing static kernel never establishes temporal-world-graph or full-domain parity.

### Gate E — CI and property strategy

Required stable gates should keep the current locked setup:

```bash
cargo fmt --all -- --check
cargo test --workspace --locked
cargo clippy --workspace --all-targets --locked -- -D warnings
uv run pytest -q tests/differential
uv run python scripts/check_python_rust_differential.py --generated-count 64 --seed 20261010
uv run python scripts/check_manifest_inventory.py
```

Then run the repository's full canonical verification procedure as required by the current README/CI, including Python tests, Ruff, mypy, package/CLI checks, lockfile validation and all required GitHub Actions jobs. Do not assume the commands in this document supersede updated repository instructions.

Use the existing Rust property tests where sufficient; add Proptest only when its shrinking/generation makes a concrete case stronger. Add Hypothesis tests only for well-defined Python invariants and keep them replayable. Fuzz parsers/serializers only when a target and resource budget are specified; keep nightly-only fuzzing outside stable required gates unless the repository explicitly adopts it.

### Gate F — Review and acceptance

The milestone is accepted only when:

- the matrix accounts for every public kernel in the Rust core and every declared direct operation;
- new direct parity has a shared contract, matching functions, stable error categories and reviewed fixed vectors;
- all confirmed mismatches have fixed regressions;
- numeric tolerance rationale/units are documented;
- stable required workflow runs pass on the exact merged commit;
- the project manifest is regenerated by the repository's canonical inventory updater and inventory/link/JSON checks pass;
- the closeout records commit SHA, toolchain versions, command outcomes, fixed/generated counts, seed and workflow URLs;
- uncovered or unsupported behavior remains explicitly listed.

## Acceptance checklist (completed for PR #33)

- [x] Confirm local `main` matches the intended current `origin/main` before branching.
- [x] Inspect the bundle diff; preserve all existing user work.
- [x] Run `uv run pytest -q tests/differential`.
- [x] Run the native differential command with the default seed/count.
- [x] Inspect operation-by-operation totals, not only the overall total.
- [x] Run Rust formatting/tests/Clippy and the full repository gates.
- [x] Run manifest inventory and link/JSON checks after adding files.
- [x] Review the matrix statuses and all changed fixtures.
- [x] Obtain CI results on the final pull-request commit.
- [x] Merge only after required checks pass, then repeat/record verification against the merge commit.

## Scoped temporal-edge and static-BFS acceptance — PR #42

PR [#42](https://github.com/shan-005/QEDTY/pull/42) was merged as [`3546fbdf9a05d7a989ea530e782c7c3a7e059c5e`](https://github.com/shan-005/QEDTY/commit/3546fbdf9a05d7a989ea530e782c7c3a7e059c5e). The accepted candidate head was `0b2d1d60878e56a9e7f656501dece0f09d4f75ff`; all required hosted workflows below passed on that exact head before merge.

- **Fixed inventory:** 96 cases: 84 previously accepted + six static-BFS fixed cases + six timestamp/window fixed cases.
- **Generated inventory:** 512 cases, 64 cases in each of eight deterministic families, seed `20261010`.
- **Differential result:** **608/608 passed**, with no unexpected skips. Per-operation totals: `canonical_json 67/67`, `contract_result 2/2`, `geometry.ecef 72/72`, `graph.static.bfs 70/70`, `identity 69/69`, `interval.contains 79/79`, `quantity.convert 72/72`, `temporal.relation 91/91`, and `time.normalize 86/86`.
- **Exact-head hosted workflows:** [QEDTY CI](https://github.com/shan-005/QEDTY/actions/runs/38145228618), [QEDTY Rust](https://github.com/shan-005/QEDTY/actions/runs/38145228592), [Platform Smoke](https://github.com/shan-005/QEDTY/actions/runs/38145228589), [Python–Rust Differential](https://github.com/shan-005/QEDTY/actions/runs/38145228585), and [Dependency Review](https://github.com/shan-005/QEDTY/actions/runs/38145228576) all completed successfully. The differential job also passed 13 focused Python-side contract tests before the 608-case native/Python comparison.
- **Acceptance boundary:** this closes the scoped temporal-edge/static-BFS slice—offset-equivalence/equal-reversed-window edge regressions plus one static directed BFS kernel. It does not complete whole-domain Python–Rust parity, the temporal world graph, bitemporal/timeline adapters, spatial parity, propagation, uncertainty, optimization, production-scale benchmarks, or production certification.

## Bitemporal membership and point timeline — accepted in PR #49

PR [#49](https://github.com/shan-005/QEDTY/pull/49) was merged into main as [1aa505398945d49faf12b3396d4943dbff0d074b](https://github.com/shan-005/QEDTY/commit/1aa505398945d49faf12b3396d4943dbff0d074b). The descriptive source branch is feature/cross-language-conformance-expansion-bitemporal-timeline.

- **Fixed inventory:** 123 cases, including 9 legacy bitemporal.contains compatibility fixtures and 18 structured bitemporal/timeline fixtures.
- **Generated inventory:** 640 cases across ten deterministic families (64 per family), seed 20261010.
- **Differential result:** **763/763 comparisons passed**, with no unexpected skips. Operation totals: bitemporal.contains 9/9, canonical_json 67/67, contract_result 2/2, geometry.ecef 72/72, graph.static.bfs 70/70, identity 69/69, interval.contains 79/79, quantity.convert 72/72, temporal.bitemporal.contains 72/72, temporal.relation 91/91, temporal.timeline.query 74/74, and time.normalize 86/86.
- **Local validation:** 248 Python tests passed; 79 Rust workspace tests passed; Rust formatting and strict Clippy passed.
- **Exact-head hosted workflows:** all five required pull-request workflows passed on head 56bad8d09daf85035478fcf1310c0c2cdf8cde4: [QEDTY CI](https://github.com/shan-005/QEDTY/actions/runs/38214117101), [QEDTY Rust](https://github.com/shan-005/QEDTY/actions/runs/38214117034), [Python–Rust Differential](https://github.com/shan-005/QEDTY/actions/runs/38214117113), [Platform Smoke](https://github.com/shan-005/QEDTY/actions/runs/38214117041), and [Dependency Review](https://github.com/shan-005/QEDTY/actions/runs/38214117107).
- **Post-merge workflows:** [QEDTY CI](https://github.com/shan-005/QEDTY/actions/runs/38214317031), [QEDTY Rust](https://github.com/shan-005/QEDTY/actions/runs/38214316898), [Python–Rust Differential](https://github.com/shan-005/QEDTY/actions/runs/38214317223), and [Platform Smoke](https://github.com/shan-005/QEDTY/actions/runs/38214316943) passed on the merge commit.

This accepts the declared open-ended bitemporal membership and point/event timeline operations. TemporalIndex at/overlap scans, collision policy, TemporalVersion/history queries, and the temporal world graph still require separate contracts and acceptance evidence.

## Static strongly connected components — accepted in PR #50

PR [#50](https://github.com/shan-005/QEDTY/pull/50) was merged into main as [337acc77700f604c0ac2cc882091417f6a5e011b](https://github.com/shan-005/QEDTY/commit/337acc77700f604c0ac2cc882091417f6a5e011b). The accepted candidate head was [b645be2ab428a927445adafa624c6c8b14c5fb9a](https://github.com/shan-005/QEDTY/commit/b645be2ab428a927445adafa624c6c8b14c5fb9a).

- **Inventory:** 132 fixed + 704 generated = **836 comparisons**, seed 20261010, 64 cases per each of eleven deterministic families.
- **Direct differential:** 836/836 passed with no unexpected skips; the SCC operation has nine independently reviewed fixed cases and 64 generated cases.
- **Hosted quality:** the exact-head Python 3.12 and 3.13 quality jobs, native compatibility, differential, review, smoke, package, and Rust workspace checks all passed. The post-merge [QEDTY CI](https://github.com/shan-005/QEDTY/actions/runs/38217091992), [QEDTY Rust](https://github.com/shan-005/QEDTY/actions/runs/38217091949), [Python–Rust Differential](https://github.com/shan-005/QEDTY/actions/runs/38217092028), and [Platform Smoke](https://github.com/shan-005/QEDTY/actions/runs/38217092039) workflows passed on the merge commit.

This accepts only label-only static directed SCC decomposition using the documented canonical output order. It does not imply parity for the temporal world graph, other graph algorithms, or graph-wide behavior.

## Spherical Haversine distance and radius query — accepted in PR #51

PR [#51](https://github.com/shan-005/QEDTY/pull/51) was merged as [`8e11844f40becf88aea5a8bf09b3de4a97aece8c`](https://github.com/shan-005/QEDTY/commit/8e11844f40becf88aea5a8bf09b3de4a97aece8c). The accepted candidate head was [`4becdffa07cc02d10bae7f1635f467794ec815d6`](https://github.com/shan-005/QEDTY/commit/4becdffa07cc02d10bae7f1635f467794ec815d6).

- **Inventory:** 150 fixed + 832 generated = **982 comparisons**, seed `20261010`, 64 generated inputs in each of thirteen families.
- **Differential result:** **982/982 passed** with no unexpected skips. Operation totals include `spatial.distance.haversine 71/71` and `spatial.radius.query 75/75`.
- **Exact-head hosted workflows:** all five required workflows passed: [QEDTY CI](https://github.com/shan-005/QEDTY/actions/runs/38219924045), [QEDTY Rust](https://github.com/shan-005/QEDTY/actions/runs/38219924051), [Python–Rust Differential](https://github.com/shan-005/QEDTY/actions/runs/38219924037), [Platform Smoke](https://github.com/shan-005/QEDTY/actions/runs/38219924077), and [Dependency Review](https://github.com/shan-005/QEDTY/actions/runs/38219924061).
- **Post-merge workflows:** [QEDTY CI](https://github.com/shan-005/QEDTY/actions/runs/38220204853), [QEDTY Rust](https://github.com/shan-005/QEDTY/actions/runs/38220204830), [Python–Rust Differential](https://github.com/shan-005/QEDTY/actions/runs/38220205096), and [Platform Smoke](https://github.com/shan-005/QEDTY/actions/runs/38220205160) ran on the merge commit; the differential and smoke runs passed. The Rust and CI runs were still in progress at the last status check.

The contract is intentionally limited to a sphere with mean-Earth radius 6,371,008.8 m. It does not establish WGS-84 ellipsoidal geodesy or parity for the full Python spatial-index API.

## TemporalIndex scan and key semantics — accepted in PR #53

The accepted operation `temporal.index.query` is a bounded direct contract for QEDTY's actual Python `TemporalIndex` reference, with JSON string payloads. It covers insertion-ordered `at`/`overlapping` scans with half-open boundaries and unbounded endpoints; `all` ordering by start then lexical key; idempotent equal adds; collisions, missing and malformed key errors; and `get`, `remove`, `len`, and `clear`.

- **Merged commit:** [`8130ac05a610b49e53470193513941fc376afc50`](https://github.com/shan-005/QEDTY/commit/8130ac05a610b49e53470193513941fc376afc50) (PR #53). Tested PR head: [`033a4ad7c0b7eb62f5bba90c08fb9754c4c28af4`](https://github.com/shan-005/QEDTY/commit/033a4ad7c0b7eb62f5bba90c08fb9754c4c28af4).
- **Exact-head differential:** **1,064/1,064 passed**, with no unexpected skips; `temporal.index.query` passed **82/82** (18 fixed + 64 generated), seed `20261010`. [Workflow](https://github.com/shan-005/QEDTY/actions/runs/38222323138).
- **Python:** 254 tests passed on Python 3.12 and 3.13, with 68.10% total-suite coverage. [QEDTY CI](https://github.com/shan-005/QEDTY/actions/runs/38222323086) passed Ruff, manifest inventory, repository identifier/milestone audit, executable conformance, demos, and lockfile checks.
- **Rust:** workspace tests, formatting, strict Clippy, expanded conformance, Arrow IPC and MSRV checks passed. [QEDTY Rust](https://github.com/shan-005/QEDTY/actions/runs/38222323123).
- **Other required workflows:** [Platform Smoke](https://github.com/shan-005/QEDTY/actions/runs/38222323147) and [Dependency Review](https://github.com/shan-005/QEDTY/actions/runs/38222323197) passed.
- **Post-merge verification on the merge commit:** [QEDTY CI](https://github.com/shan-005/QEDTY/actions/runs/38222701258), [QEDTY Rust](https://github.com/shan-005/QEDTY/actions/runs/38222701262), [Python–Rust Differential](https://github.com/shan-005/QEDTY/actions/runs/38222701260), and [Platform Smoke](https://github.com/shan-005/QEDTY/actions/runs/38222701275) all passed.

This establishes only the versioned string-valued TemporalIndex boundary; it does not establish version-history or temporal-world-graph parity.

## TemporalVersion identity and history semantics — accepted in PR #54

The `temporal.history.query` contract compares the Python `TemporalVersion`/`TemporalHistory` reference with a native implementation using JSON values:

- `create` recomputes canonical identity from `record_key`, valid-time extent, transaction-time extent, and `value`; `supersedes` and `metadata` are payload fields but are intentionally excluded from the identifier preimage.
- `all` sorts by version ID; `get` returns a matching version or `missing_version`; `add` is idempotent for identical records and returns `version_collision` when the same ID maps to different content.
- `as_of` filters using both valid-time and transaction-time membership, selects the latest transaction-start version per record key (version ID breaks exact-start ties), and returns records ordered by record key.
- `latest_known` filters by record key and transaction-time membership only, intentionally not valid-time membership, then applies the same latest-start/version-ID ordering.

PR [#54](https://github.com/shan-005/QEDTY/pull/54) merged as [`fad44f62984614074799862ec5586f6dfdf4439e`](https://github.com/shan-005/QEDTY/commit/fad44f62984614074799862ec5586f6dfdf4439e). The tested PR head was [`d7ed3c5a7a1ad270ccdcd3bb4fe27d77ed6ab531`](https://github.com/shan-005/QEDTY/commit/d7ed3c5a7a1ad270ccdcd3bb4fe27d77ed6ab531), with **185 fixed + 960 generated = 1,145/1,145 comparisons passed**, seed `20261010`, 64 generated cases in each of fifteen deterministic families, and no unexpected skips.

- **Exact-head differential:** **1,145/1,145 comparisons passed** with seed `20261010`, 64 generated inputs per each of fifteen families, and no unexpected skips. The `temporal.history.query` operation passed **81/81** (17 fixed + 64 generated); 22 focused Python differential-contract tests also passed.

- **Exact-head hosted workflows:** all five required checks passed for tested head [`d7ed3c5a7a1ad270ccdcd3bb4fe27d77ed6ab531`](https://github.com/shan-005/QEDTY/commit/d7ed3c5a7a1ad270ccdcd3bb4fe27d77ed6ab531): [QEDTY CI](https://github.com/shan-005/QEDTY/actions/runs/38224666054), [QEDTY Rust](https://github.com/shan-005/QEDTY/actions/runs/38224665990), [Python–Rust Differential](https://github.com/shan-005/QEDTY/actions/runs/38224666011), [Platform Smoke](https://github.com/shan-005/QEDTY/actions/runs/38224666169), and [Dependency Review](https://github.com/shan-005/QEDTY/actions/runs/38224665992).

- **Post-merge hosted verification:** all four workflows triggered on merge commit [`fad44f62984614074799862ec5586f6dfdf4439e`](https://github.com/shan-005/QEDTY/commit/fad44f62984614074799862ec5586f6dfdf4439e) completed successfully: [QEDTY CI](https://github.com/shan-005/QEDTY/actions/runs/38225392129), [QEDTY Rust](https://github.com/shan-005/QEDTY/actions/runs/38225392196), [Python–Rust Differential](https://github.com/shan-005/QEDTY/actions/runs/38225392186), and [Platform Smoke](https://github.com/shan-005/QEDTY/actions/runs/38225392267).

- **Operation totals from the accepted exact-head run:** `bitemporal.contains 9/9`, `canonical_json 67/67`, `contract_result 2/2`, `geometry.ecef 72/72`, `graph.static.bfs 70/70`, `graph.static.scc 73/73`, `identity 69/69`, `interval.contains 79/79`, `quantity.convert 72/72`, `spatial.distance.haversine 71/71`, `spatial.radius.query 75/75`, `temporal.bitemporal.contains 72/72`, `temporal.history.query 81/81`, `temporal.index.query 82/82`, `temporal.relation 91/91`, `temporal.timeline.query 74/74`, and `time.normalize 86/86`.

- **Contract boundary:** this accepts only the declared JSON-value `TemporalVersion` identity and selected `TemporalHistory` operations. Snapshot parity, temporal-world-graph history traversal, and whole-domain temporal equivalence remain open.

## Current delivery boundary and closeout checklist

At current `main` commit `808b3e73f57c3f3638fed4f177097453933c0288`, PR #67 adds bounded static PageRank. PR #65 WGS-84 ellipsoidal inverse-distance and PR #67 PageRank passed all five required pull-request workflows on their exact heads; the exact evidence is recorded above. The matrix’s `phase4_disposition` column is the authoritative machine-readable queue.

Post-merge verification on merge commit [`808b3e73f57c3f3638fed4f177097453933c0288`](https://github.com/shan-005/QEDTY/commit/808b3e73f57c3f3638fed4f177097453933c0288) passed all four applicable workflows: [QEDTY CI](https://github.com/shan-005/QEDTY/actions/runs/38255644673), [QEDTY Rust](https://github.com/shan-005/QEDTY/actions/runs/38255644561), [Python–Rust Differential](https://github.com/shan-005/QEDTY/actions/runs/38255644601), and [Platform Smoke](https://github.com/shan-005/QEDTY/actions/runs/38255644625).

**Phase 4 exit checklist:**

- [ ] Every public Rust kernel and every direct differential operation is explicitly classified in the matrix.
- [x] Direct static PageRank and scalar max-flow contracts accepted with independent oracles, deterministic generated comparisons and stable errors; Rust-only reliability path and convergence-based PageRank remain deferred by design.
- [ ] One reviewed broader spatial-index operation has a common metric and candidate-completeness contract; spherical and ellipsoidal distance semantics stay separate.
- [ ] One semantically matched propagation slice has a shared contract; no equation of `propagate_linear` with the full time-aware propagation engine.
- [ ] One bounded uncertainty operation has matching semantics and independent boundary vectors.
- [ ] One bounded optimization operation has matching objective, units, ties and resource/infeasibility rules.
- [ ] `tests/differential/test_conformance_matrix.py`, focused differential tests, full Python CI, Rust workspace/MSRV checks, differential totals, manifest inventory, link/JSON checks, and required hosted jobs pass on exact final head.
- [ ] The required workflows pass on the resulting merge commit where configured.
- [ ] The final record lists exact commits, workflow URLs, operation totals/seed and explicitly excluded behavior.

The current `DEFERRED_BY_DESIGN` row for Python-only application domains is not a failed Phase 4 gate: it prevents the existence of Python modules from being misread as a requirement to invent a Rust port. Conversely, any row marked `PHASE4_GAP` remains open until an operation-specific acceptance record justifies closing it. Production certification, arbitrary-scale performance and complete Python/Rust domain equivalence are outside this milestone and must not be claimed from these tests.
