# Currency-Neutral Portfolio Optimization v2 Conformance Audit

**Status:** `ACCEPTED_BOUNDED_SCOPE` (2026-11-04).
**Accepted main baseline:** `f449093c52094b44529b9a261c9eda215a0f443d`.
**Implementation PRs:** FX/currency v2.1 in PR #77; portfolio resilience objective in PR #81.

## Legacy v1 surface

| Surface | Preserved semantics | Compatibility control |
|---|---|---|
| `economics/currency.py` and v1 models | Existing USD-default floating-point money and USD-named request/result fields. | No v1 schema, protobuf, or wire-field migration. |
| `optimization/objectives.py` | Legacy efficiency and weighted-score helpers; lower-tail CVaR helper does not imply that the legacy engine selects on every helper. | v1 objective behavior remains owned by the existing Python reference. |
| `optimization/constraints.py` | USD budget and fixed-overhead feasibility. | No implicit reinterpretation as a reporting-currency budget. |
| `optimization/portfolio.py` | Exact branch-and-bound through 28 items; efficiency/ID-ordered greedy fallback above the threshold. Exact utility is `efficiency * cost_usd / 1_000_000`. | A regression test pins the legacy zero-cost behavior: a positive-gain, zero-cost candidate contributes zero exact-solver utility and is not selected by the v1 knapsack. |
| `optimization/engine.py` | `ResilienceOptimizer.rank` computes counterfactual gain/risk, orders recommendations, then selects through the legacy knapsack. | It is not silently redirected to the new v2 request contract. |

The v1 JSON Schema and protobuf compatibility guards remain in `tests/test_optimization_v1_compatibility.py`. That file now also pins the v1 zero-cost selection behavior. The v2 tests separately prove that the opt-in v2.1 `continuity_gain`/`resilience_gain` selection contract can select a positive-gain zero-cost candidate. This difference is intentional and visible, not an accidental claim of behavioral identity.

## Versioned currency and portfolio contracts

- Currency v2.0 uses Decimal amounts, caller-supplied versioned currency metadata, explicit immutable FX snapshots, declared scale/rounding rules, and direct/reciprocal quote conversion. It rejects nonzero spread/fee fields.
- Opt-in currency v2.1 adds deterministic fewest-hop FX triangulation with lexicographic currency-path tie-breaking, per-quote spread/fee haircuts, path provenance, final-target-only rounding, and the declared 34-significant-digit arithmetic profile. It does not fetch live FX rates.
- Portfolio v2.0 remains unchanged. Portfolio v2.1 adds the opt-in request/result schema and FX-path audit, and the `resilience_gain` objective. The five declared objectives are `continuity_gain`, `resilience_gain`, `weighted_score`, `robust_floor`, and `lower_tail_cvar`.
- Requests use a reporting-currency budget, explicit currency metadata, candidate costs, optional fixed overhead, scenario IDs/scores, and an optional FX snapshot. Results carry conversion audit data, deterministic recommendations/digest, solver mode, and explicit `optimal`, `feasible_not_proven_optimal`, or `infeasible` status.
- Exact selection is bounded to 28 eligible items and 200,000 search nodes. Larger inputs use the documented greedy fallback; node exhaustion returns a feasible result without claiming optimality. These are explicit resource/optimality limits, not an unlimited exact-optimality guarantee.
- Python and Rust are compared through the named `currency.convert.v2` and `portfolio.optimize.v2` differential adapters and versioned fixtures.

## Compatibility decision

**v1 is preserved; v2/v2.1 are parallel, explicitly selected contracts.** No automatic migration or silent mapping of USD v1 fields/semantics to v2 is performed. The v2.1 `resilience_gain` objective aligns its declared gain-ranking and lexical tie policy with the QEDTY resilience ranking intent, but it is not a promise that the entire legacy `ResilienceOptimizer.rank` pipeline is behaviorally identical. In particular, the legacy zero-cost knapsack behavior is deliberately retained in v1 while v2.1 selects a positive-gain zero-cost intervention.

A Rust-shared v1 portfolio API is not required for acceptance of the separately versioned v2/v2.1 contract and remains deferred until an independently approved v1 cross-language contract exists. This avoids silently changing existing callers or inventing a second v1 semantic authority.

## Acceptance evidence

- PR #77 merged at `7050fdaa56d8785d0944cc5d706f57b7a587e755`. Its hosted merge-commit check runs all completed successfully: package, dependency graph update, Rust workspace, Python quality 3.12/3.13, Python–Rust differential, native, and platform smoke.
- PR #81 merged at `f449093c52094b44529b9a261c9eda215a0f443d`. Its exact PR-head checks completed successfully; all seven check runs on the merge commit also completed successfully (package, Rust workspace, Python–Rust differential, Python quality 3.12/3.13, native, and platform smoke). The four push-triggered workflows on the merge commit—QEDTY CI, QEDTY Rust, QEDTY Python-Rust Differential, and QEDTY Platform Smoke—also completed successfully.
- The recorded differential evidence is 2,099/2,099 overall, including 24/24 currency conversion cases and 73/73 portfolio optimization cases. The tested portfolio boundaries include exact 28-item behavior, 29-item feasible fallback, the 200,000-node limit, deterministic tie-breaking, zero-cost behavior, FX path audit, fees/spread, and conversion rounding.
- The v1 JSON Schema/protobuf guards and the added v1 zero-cost behavior regression protect the declared compatibility boundary.

## Accepted scope and explicit exclusions

This workstream is accepted for the named, versioned currency and portfolio v2/v2.1 contracts and their tested Python–Rust differential boundaries. It does **not** claim full parity for every QEDTY optimization/application domain, a Rust port of the legacy v1 engine, optimality above the documented solver limits, live FX ingestion, an authoritative ISO-4217 registry, arbitrary-precision arithmetic beyond the declared profile, or unbounded cross-language equivalence.

There are no remaining acceptance gates inside this declared bounded scope. Any expansion beyond these boundaries requires a separately versioned semantic contract, independent/adversarial vectors, differential coverage, and exact-head plus post-merge CI.
