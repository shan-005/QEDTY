# Portfolio v2 Conformance Audit

**Status:** follow-up in progress; this is not a full-domain acceptance claim.
**Audited main baseline:** `671563b468cef39247f94ea95caa40de128e30db`.

## Legacy Python surface

| Surface | Observed semantics | Conformance implication |
|---|---|---|
| `src/qedty/economics/currency.py` | Floating-point `Money`; USD default; currency validation checks only three-character length; `round()` handles rounding. No versioned currency profile or explicit FX snapshot. | Not interchangeable with v2 Decimal/profile-based money. |
| `optimization/models.py` | USD-named cost/budget/spend fields; result includes recommendations, selection, robust floor, status and digest. | The v1 data model is USD-specific. |
| `optimization/objectives.py` | Efficiency uses gain divided by cost in millions when cost is nonzero; weighted score subtracts normalized cost and risk; lower-tail CVaR is available as a helper. | Existence of these helpers does not mean the legacy engine uses every objective. |
| `optimization/constraints.py` | Budget and fixed-overhead checks use USD floating-point amounts. | v2 defines reporting-currency conversion and a separate request contract. |
| `optimization/portfolio.py` | Exact solver for at most 28 items; larger sets use greedy sorting by efficiency then ID. The exact objective uses `efficiency * cost_usd / 1_000_000`. | Legacy and v2 fallback orderings/objective calculations differ, particularly around zero-cost items. |
| `optimization/robustness.py` | Helpers provide robust floor, lower-tail CVaR and dominance score. | Helpers alone do not specify a complete portfolio-level scenario contract. |
| `optimization/engine.py` | `ResilienceOptimizer.rank` calculates counterfactual gain, derives risk from counterfactual capacity, ranks recommendations and selects using `knapsack_portfolio`. Its named objective is `robust_continuity_gain_then_cost_efficiency`. | Ranking, recommendation semantics and selection are not a literal match for v2's explicit objective contract. |
| v1 JSON Schema and protobuf | USD-named fields and a compact legacy result shape. | Keep these v1 interfaces unchanged; do not redefine them silently. |

## Versioned v2 surface

- `contracts/qedty/economics/currency-v2.json` and `src/qedty/economics/currency_v2.py` define v2.0 Decimal amounts, caller-supplied versioned currency metadata, scale/rounding rules and explicit FX snapshots with validity, source and provenance. v2.0 accepts direct or reciprocal quotes only and rejects nonzero spread/fee fields.
- `contracts/qedty/economics/currency-v2.1.json` adds an explicitly opt-in v2.1 profile: deterministic fewest-hop, lexicographically tie-broken FX paths, per-quote spread/fee haircuts, auditable path provenance and final-target-only rounding. Arithmetic is bounded to the declared 34-significant-digit profile; no live FX fetching is performed.
- `contracts/qedty/optimization/optimization-v2.json` defines the unchanged v2.0 portfolio contract. `optimization-v2.1.json` adds the opt-in v2.1 request/result schema and conversion path audit while preserving the v2.0 schema.
- `src/qedty/optimization/portfolio_v2.py` defines reporting-currency budgets, optional fixed overhead, scenario IDs/scores, deterministic output and explicit `optimal`, `feasible_not_proven_optimal` and `infeasible` statuses.
- The declared v2 objectives are `continuity_gain`, `weighted_score`, `robust_floor` and `lower_tail_cvar`. The exact-item threshold is 28 and the branch-and-bound node budget is 200,000. Larger portfolios use `greedy_fallback`; node exhaustion uses `node_limit_fallback`.
- Rust is compared through the shared `currency.convert.v2` and `portfolio.optimize.v2` adapters. Existing positive fixed cases are in `data/contracts/differential/cases/cross_language_edges.json`.

## Compatibility disposition: v1 preserved, v2 opt-in

The v2 adapter introduces a new, explicitly versioned contract; it is **not** a literal behavior-preserving port of `ResilienceOptimizer.rank` and `knapsack_portfolio`. The legacy engine's counterfactual-driven ranking, USD floating-point arithmetic, recommendation ordering and efficiency-sorted greedy fallback differ from v2's objectives and fallback rules.

**Compatibility disposition for this milestone:** Keep v1 as a backward-compatible legacy contract, with no silent schema, protobuf, or wire-field changes and no automatic migration. Treat v2 as a parallel, explicitly selected, opt-in contract. Do not silently map v1 fields or semantics onto v2. Legacy behavior remains governed by the existing Python reference implementation. A Rust-shared v1 contract is a separate deferred work item requiring an independently approved semantic contract. The present v2 differential evidence establishes only the named v2 request boundary.

This decision does not establish full portfolio-domain parity or complete Workstream 1. The remaining acceptance gates below still apply.

## Local evidence and remaining gates

Latest local evidence from the active worktree: the full Python suite passed **325 tests**; the official Python–Rust differential runner passed **2,099/2,099** cases with seed 20261010 and 64 generated cases per family, with no unexpected skips. The currency.convert.v2 operation matched 24/24 cases, and portfolio.optimize.v2 matched 73/73. The suite includes the standalone v2.1 triangulation fixture, three decimal-boundary differential cases, the portfolio-integrated v2.1 FX-path fixture, 18 permanent currency/portfolio error fixtures, 28/29-item solver-boundary cases, the 200,000-node fallback boundary and complementary-scenario fallback cases. A Python regression now covers quantization of a large target amount produced by a small reciprocal FX quote. The Rust workspace passed **101 tests**; `cargo fmt --all -- --check`, `cargo clippy --locked --workspace --all-targets -- -D warnings`, Ruff on the changed Python files and `git diff --check` also passed. These are local results for the uncommitted worktree, not hosted CI results.

The independent threshold oracle is now present and passing: unit costs and gains 1 through 28 produce objective 406 with `optimal`; gains 1 through 29 produce objective 435 with `feasible_not_proven_optimal`. The node-limit test also reached exactly 200,000 nodes and required the non-optimal status.

Remaining acceptance gate:

1. Run and verify the required hosted exact-head workflows after these changes are committed/pushed, then verify required workflows on the actual merge commit. Keep both matrix dispositions as `FOLLOW_UP_IN_PROGRESS` until those remote checks pass.

The local evidence supports bounded direct conformance for the named currency and portfolio v2/v2.1 contracts and their tested cases. It does not establish full QEDTY portfolio-domain parity, arbitrary-precision arithmetic, live FX data integration or unbounded cross-language equivalence.
