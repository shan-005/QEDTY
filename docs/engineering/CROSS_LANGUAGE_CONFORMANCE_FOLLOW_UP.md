# Full-Domain Cross-Language Conformance Follow-up

**Status:** follow-up execution plan after the bounded Phase 4 closeout. This plan does not reopen or invalidate Phase 4's accepted bounded matrix. The follow-up is complete only when each selected domain has a versioned semantic contract and direct, independently verified Python–Rust evidence.

**Baseline:** `main` at `18fc0e725115ca7371d1684d868dda10602b6b04`, after PR #70. All seven post-merge checks on that commit passed.

## Objective and governing rules

Expand cross-language conformance from the currently accepted operation-level kernels toward the full QEDTY domain semantics, without pretending that similar-looking primitives establish whole-domain parity.

- Python remains the semantic and reference authority. A Rust implementation must not define new meaning simply because a native operation is easier to implement.
- Each workstream starts by inventorying the existing Python models, public functions, error behavior, contracts, and tests. Name the exact request/result boundary before adding a Rust adapter.
- Preserve accepted bounded operations and existing v1 wire/schema compatibility. Add versioned contracts for genuinely expanded semantics; do not silently redefine existing v1 fields.
- Every result must preserve deterministic ordering, units, explicit failure/status semantics, and provenance where the Python reference requires them.
- External data such as currency metadata, exchange rates, coordinate-reference definitions, and calibration datasets must be explicit inputs or versioned dependencies. Do not fetch live external data implicitly inside a deterministic kernel.
- “Full” means parity against the declared Python semantic surface, not an unsupported claim that every theoretical problem or all future QEDTY capabilities have been implemented.

## Workstream 1 — Full, currency-neutral portfolio optimization

**Priority:** first contract/design workstream, because the current bounded Rust knapsack is not the QEDTY portfolio optimizer.

### Existing reference surface to audit

At minimum, audit and test the semantic relationships among:

- `src/qedty/optimization/models.py`
- `src/qedty/optimization/objectives.py`
- `src/qedty/optimization/constraints.py`
- `src/qedty/optimization/portfolio.py`
- `src/qedty/optimization/robustness.py`
- `src/qedty/optimization/engine.py`
- `src/qedty/economics/currency.py`
- `contracts/qedty/optimization/optimization-v1.json`
- `proto/qedty/optimization/v1/optimization.proto`

The current v1 uses `cost_usd`, `budget_usd`, `spent_usd` and USD-specific protobuf fields. The accepted Rust `integer_knapsack` is a bounded primitive with integer weights/values. Neither establishes parity with the complete Python portfolio selection, objective, constraints, robustness, currency handling, result and fallback semantics.

### Required contract properties

1. **No USD assumption.** Represent each monetary amount with an explicit currency code and a versioned metadata profile describing its decimal/minor-unit scale and rounding policy. Currency support must be data/metadata driven rather than a currency-code allowlist embedded in the optimizer. Existing USD v1 interfaces remain compatible while the new version supports a declared reporting/numeraire currency and item-native currencies.
2. **Explicit FX snapshot.** FX inputs must identify base and quote currencies, rate direction, positive finite rate, as-of time/validity, source and provenance. Missing, stale, ambiguous or inconsistent conversion paths must produce defined errors. Do not make network calls to discover rates during optimization. Any reciprocal/triangulation rules, spread and fees must be specified and deterministic.
3. **Monetary arithmetic.** Use an explicit decimal or fixed-point representation for monetary values at the contract boundary. Define conversion precision, rounding mode and the exact stage where rounding occurs. Reject overflow, non-finite values, invalid codes and unsupported metadata instead of silently coercing them.
4. **Complete existing optimization semantics.** Conform the selected intervention IDs, total spend, budget feasibility, objective construction, stable tie rules, constraints, worst-case/robustness and lower-tail CVaR behavior, and the existing exact-solver versus greedy-fallback boundary. The contract must not label a fallback as globally optimal when optimality was not proven.
5. **Declared constraints and decision status.** Specify the supported budget and feasibility constraints, rejected combinations, solver/resource limits, deterministic output ordering, status taxonomy (for example, optimal, feasible-but-not-proven-optimal, and infeasible), and failure behavior. Add new objective/constraint types in Python first, with reference tests, rather than creating native-only features.
6. **Evidence.** Fixed independent oracles, FX cross-rate and rounding cases, multi-currency budget cases, zero-cost and equal-objective ties, infeasible portfolios, negative/invalid monetary values, stale/missing rates, resource-bound fallback, property/generated and adversarial cases, and same-input Python–Rust comparisons. Add a versioned contract, schema/protobuf surface as appropriate, golden/differential cases, the matrix row and hosted workflows.

### Acceptance gate

Do not call portfolio parity complete because `integer_knapsack` passes. Accept the full optimizer only when the new contract covers the audited Python reference surface and every required objective, constraint, FX and status case has fixed and generated evidence. Benchmarking may compare performance but must not replace semantic conformance.

## Workstream 2 — Full time-aware propagation

Match the existing Python propagation engine, not merely `propagate_linear` or contribution aggregation. The request/result contract must cover temporal edge validity, departure and arrival time semantics, delays, paths and cycles, hop/resource limits, truncation, competing paths, combination rules, provenance and epistemic result state. Define exact behavior for empty, invalid, unreachable, and boundary-time cases. Keep numeric aggregation as a separate bounded operation.

Acceptance requires independent time-boundary and path oracles, generated temporal graphs, error/resource cases, same-input output and provenance comparisons, and a matrix entry whose scope states precisely what is and is not covered.

## Workstream 3 — Full uncertainty semantics

Audit the Python uncertainty models and public operations before choosing individual Rust boundaries. Separate scalar aggregation from intervals, probability distributions, sampling, calibration, sensitivity, Monte Carlo propagation and uncertainty-bearing result reporting. Contracts must declare distribution parameters, random-number generator/algorithm and seed behavior, sample-count bounds, statistical tolerances, calibration datasets/version, invalid parameter behavior, and provenance. Deterministic sampled operations must be replayable from an explicit seed; statistical comparisons must have predeclared tolerances and independent expected-value checks rather than relying solely on two implementations agreeing.

Accept each operation only when its mathematical domain, parameters, numerical tolerances, failure behavior and evidence are named. Do not mark the whole uncertainty domain covered after weighted-mean parity.

## Workstream 4 — Broader spatial and CRS semantics

Extend beyond the accepted bounding-box, spherical-radius and ellipsoidal inverse-distance slices. Inventory Python spatial models/indexes and define separate contracts for coordinate-reference metadata/transformation, geometry validation and predicates, candidate completeness, and index queries. Specify axis order, units, datum/ellipsoid, coordinate epoch when relevant, transformation pipeline and accuracy, antimeridian/polar behavior, degenerate geometry, missing CRS, invalid geometry, duplicate IDs and deterministic ordering. Preserve the distinction among spherical distances, WGS-84 ellipsoidal geodesics, ECEF conversion and general CRS transformations.

Acceptance requires independent geospatial oracles, explicit CRS/axis/units fixtures, boundary and invalid-geometry vectors, generated queries with a candidate-completeness check, and operation-specific accuracy tolerances. Performance is measured separately from semantic equivalence.

## Execution order and gates

1. **Inventory and contract review:** map the current Python public surface, schemas, tests, dependencies and behavior before changing implementation.
2. **Portfolio contract first:** approve the currency-neutral portfolio v2 boundary and add Python contract/reference tests while preserving v1.
3. **Dependency-aware domain implementation:** build matched reference/native operations in small PRs. Complete propagation, uncertainty and spatial/CRS slices only against versioned contracts; do not group unrelated domain changes into one giant PR.
4. **Per-operation conformance:** independent fixed vectors, same-input differential tests, deterministic generated/property cases, malformed/error/resource cases, and accurate matrix scope.
5. **Exact-head and merge verification:** all required PR-head workflows must pass; after merge, verify the actual merge SHA and all required post-merge workflows. Update the authoritative matrix and this record only from observed evidence.

A failed, incomplete or skipped required gate blocks acceptance. An operation may remain explicitly deferred without blocking the already accepted Phase 4 bounded baseline.

## Completion definition

The follow-up is not “done” because the four prior gap labels are gone. For every domain claimed complete, its inventory must have no unreviewed semantic operations; all required contract cases must run on both Python and Rust; no unexplained skips or mismatches may remain; and the matrix must distinguish direct parity, accepted bounded slices and deliberate deferrals. The portfolio workstream additionally must demonstrate multi-currency conversion and complete audited Python optimizer behavior, not only USD or integer-knapsack parity.
