# QEDTY Cross-Language Conformance Expansion

**Status:** implementation bundle / proposed baseline, pending execution in the target checkout
**Repository baseline reviewed:** `dcae063b6d30b4b74a46be69349762ceb368da26` (`main`, 2026-10-11)
**Semantic authority:** Python reference implementation
**Native counterpart:** `crates/qedty-core/`
**Contract and adapter:** `contracts/json-schema/differential-cases.schema.json`, `scripts/check_python_rust_differential.py`, `rust/crates/qedty-conformance/src/bin/qedty-differential.rs`

## Purpose and non-goals

This milestone expands the set of behaviors that are demonstrably conformant between QEDTY's Python reference APIs and corresponding Rust kernels. It does not assert that Rust is a second semantic authority or that every Python application module must be ported. A domain only enters direct conformance when both implementations expose a deliberately shared semantic boundary.

This bundle makes two concrete expansions to the existing testing system:

1. Adds ten fixed differential cases for JSON, identity, quantities, timestamp normalization, interval membership and Allen interval relations.
2. Extends the deterministic generator from five to seven families by adding interval-membership and Allen-relation inputs. With the default `--generated-count 64`, this changes the intended run size from 41 fixed + 320 generated = 361 comparisons to 51 fixed + 448 generated = 499 comparisons. These are expected counts from the bundle inputs, not a test-pass claim.

It also adds a checked-in domain-by-domain matrix, a test which validates the matrix's status vocabulary and repository paths, a research/standards register, and a safe bundle-application script. The current graph, spatial-index, bitemporal-timeline, propagation, uncertainty and optimization rows remain explicitly scoped rather than being granted broad parity claims.

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

## Ordered work plan

### Gate A — Baseline and scope

- Record the reviewed commit, local commit, Python/Rust versions, workflow URLs and current fixed/generated counts.
- Review this matrix and correct paths/statuses against the actual target checkout.
- Update the stale repository README milestone entry so Systematic Python–Rust Differential Testing is recorded as completed and Cross-Language Conformance Expansion as current.
- Do not change production algorithms in the baseline-only change.

### Gate B — Shared-core edge expansion

- Integrate `data/contracts/differential/cases/cross_language_edges.json`.
- Extend `generate_cases()` with deterministic `interval.contains` and `temporal.relation` families while leaving the existing five-family generated sequence intact.
- Update differential tests to expect seven reproducible families and permit additional fixed relation cases while asserting that every one of the thirteen relation labels remains represented.
- Run the Python fixed-oracle tests first, then the native differential command. Treat every mismatch as a real failure to investigate; do not weaken comparison modes.

### Gate C — Temporal depth

The ten fixed cases and two generated families are an initial expansion, not exhaustive temporal coverage. Next audit timestamp parser boundary behavior, dates around the representable year range, offset normalization crossing calendar boundaries, fractional precision, invalid offsets, empty/reversed intervals, one-sided/unbounded windows, equal instants expressed by different offsets, and inverse Allen relations. Add direct adapters for bitemporal/timeline operations only after matching Python/Rust APIs and output semantics are specified.

### Gate D — Graph, spatial, propagation and uncertainty

Do not implement domain adapters by guessing:

- **Graph:** first define a versioned static-kernel contract and independent Python reference functions for matching primitive requests. Separate this from the temporal ontology graph (entities, relationship identity, valid-time filtering, provenance and snapshots). Define deterministic tie-breaking and disconnected/negative-weight behavior.
- **Spatial:** choose a bounded operation (for example, radius query under a named spherical metric) and identify the actual Python reference operation. Specify coordinate order/ranges, antimeridian/polar behavior, candidate completeness, output ordering, duplicate IDs and units. Do not compare spherical distances to ellipsoidal geodesic distances as if they were identical.
- **Temporal graph/propagation:** the native linear matrix kernel is not automatically the Python time-respecting propagation engine. A matching contract must address departure-time relationship validity, delays, arrival validity, cycles/hop limits, multi-shock aggregation, truncation and epistemic status.
- **Uncertainty:** select one shared primitive such as bounded interval arithmetic or a weighted mean, not the full Python distribution/calibration/sensitivity subsystem by implication.
- **Optimization:** native knapsack is not the entire Python portfolio engine. Specify objective, constraint, tie-breaking, resource bounds and infeasible-case semantics.

Each added operation requires updates to the contract/case schema operation allowlist, Python reference API, Rust adapter, fixed vectors, unit/integration tests, matrix and CI in one reviewable change.

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

## Initial acceptance checklist

- [ ] Confirm local `main` matches the intended current `origin/main` before branching.
- [ ] Inspect the bundle diff; preserve all existing user work.
- [ ] Run `uv run pytest -q tests/differential`.
- [ ] Run the native differential command with the default seed/count.
- [ ] Inspect operation-by-operation totals, not only the overall total.
- [ ] Run Rust formatting/tests/Clippy and the full repository gates.
- [ ] Run manifest inventory and link/JSON checks after adding files.
- [ ] Review the matrix statuses and all changed fixtures.
- [ ] Obtain CI results on the final pull-request commit.
- [ ] Merge only after required checks pass, then repeat/record verification against the merge commit.

## Delivery boundary

This bundle is an additive implementation package based on a live source audit. It is not a claim that the entire milestone has already passed. The target checkout must execute all tests and CI before the work may be called complete. If current `main` has changed so an expected patch anchor no longer matches, the application script fails rather than guessing or overwriting newer work.
