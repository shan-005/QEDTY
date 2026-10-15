# Currency-Neutral Portfolio Optimization — Python Semantic Audit

**Status:** research/design only; no runtime behavior changed.
**Baseline:** `main` at `18fc0e725115ca7371d1684d868dda10602b6b04` (Phase 4 bounded closeout; all seven post-merge checks passed).
**Tracking:** [Issue #72](https://github.com/shan-005/QEDTY/issues/72).

## Decision

The next implementation workstream is the full currency-neutral portfolio optimizer, not the accepted integer 0/1 knapsack kernel. Preserve the current v1 USD-shaped contract for compatibility and define an explicitly versioned currency-neutral contract before changing the Python reference or adding Rust adapters.

“Full” means parity with the audited QEDTY Python optimizer surface and the semantics approved for the new contract; it does not mean every possible financial optimization model.

## Files inspected on main

- `src/qedty/optimization/models.py`
- `src/qedty/optimization/objectives.py`
- `src/qedty/optimization/constraints.py`
- `src/qedty/optimization/portfolio.py`
- `src/qedty/optimization/robustness.py`
- `src/qedty/optimization/engine.py`
- `src/qedty/economics/currency.py`
- `contracts/qedty/optimization/optimization-v1.json`
- `proto/qedty/optimization/v1/optimization.proto`
- `docs/engineering/CROSS_LANGUAGE_CONFORMANCE_FOLLOW_UP.md`
- `docs/engineering/CROSS_LANGUAGE_CONFORMANCE_MATRIX.csv`

## Observed current semantics and gaps

### 1. USD is embedded in public models and the wire contract

- `RankedIntervention` has `cost_usd`; `OptimizationResult` has `budget_usd` and `spent_usd`.
- `BudgetConstraint`, `feasible`, `efficiency`, `weighted_score`, `ResilienceOptimizer.rank`, and `knapsack_portfolio` all consume USD-named floats.
- `optimization-v1.json` requires numeric `budget_usd`.
- `optimization.proto` uses `double cost_usd`, `budget_usd`, and `spent_usd`.
- Keep these v1 fields and their existing meaning stable; do not silently reinterpret them as arbitrary currencies.

### 2. Currency primitives are not sufficient for portfolio parity

`src/qedty/economics/currency.py` currently defines `Money(value: float, currency: str = "USD")`, validates only non-negative values and a three-character code, rounds using Python `round`, and exposes `usd(value)`. It does not provide versioned currency metadata, minor-unit scales, explicit decimal arithmetic, FX snapshots, rate direction/as-of/provenance, conversion path rules, spread/fee semantics, or stale/missing-rate errors. ISO-4217-like three-letter syntax alone does not validate a supported currency or its precision.

### 3. Objective and risk semantics that must be preserved or explicitly versioned

- `efficiency(gain, cost_usd)`: rejects negative/non-finite inputs; returns gain per million cost, or gain for zero cost.
- `weighted_score`: weighted gain minus cost-in-millions and risk, with all values/weights finite and non-negative.
- `cvar` and `cvar_score`: lower-tail mean of the worst ceil((1-alpha)*N) scores under the current implementation's formula; `cvar` rejects empty input while `cvar_score` returns 0.
- `robust_floor`: minimum score or 0 for empty input; `dominance_score` returns 1 for zero mean.
- Do not accidentally unify these differing empty-input/error behaviors during a currency migration. Decide whether each belongs in the optimizer contract and test it.

### 4. Portfolio selection and fallback semantics

- `greedy_portfolio` orders by descending efficiency then `intervention_id`, selecting each item if it fits the remaining budget.
- `knapsack_portfolio` sorts the same way, computes utility as `efficiency * cost_usd / 1_000_000` clipped at zero, and uses deterministic branch-and-bound for up to 28 items; above 28 items it falls back to the stable greedy selection.
- The function currently returns selected items and spend but no explicit proof/status that distinguishes exact optimality from fallback. The new result must not claim globally optimal when greedy fallback ran.
- The engine filters individually infeasible interventions, computes counterfactual gain and risk score, sorts recommendations by robust score/efficiency/ID, selects a portfolio, computes a digest, and returns an `OptimizationResult`. The new contract must define stable digest inputs and versioning when currency/FX inputs become part of the result.

### 5. Validation is incomplete for a financial contract

The inspected functions do not consistently validate all item values as finite before arithmetic; `BudgetConstraint` and `feasible` only compare numeric values and do not enforce finite values or currency identity. Floating-point rounding and summation can change budget-boundary decisions. New v2 boundary validation must specify strict input types, finite/non-negative rules, currency metadata, FX snapshot identity/validity, arithmetic precision, rounding stage, overflow, budget feasibility, and typed failure/status outcomes.

## Proposed v2 contract design (not yet implementation)

1. **Monetary amount:** decimal string or integer minor units plus explicit ISO currency code and metadata-profile version. Avoid JSON binary floating-point as the authoritative money representation.
2. **Currency metadata:** versioned, explicit input describing currency code, minor-unit scale and rounding policy. The optimizer must not embed a fixed supported-currency allowlist in business logic.
3. **FX snapshot:** explicit immutable request input with base/quote currency, direction, positive finite rate representation, as-of/validity, source/provenance and snapshot ID. Define stale/missing/ambiguous paths and whether triangulation is allowed. Never fetch FX implicitly at runtime.
4. **Reporting/numeraire currency:** explicit target currency for cross-currency budget/objective aggregation, while retaining native item amounts and traceable conversions.
5. **Arithmetic:** explicit decimal/fixed-point precision, rounding mode and exact rounding points (rate application, item conversion, aggregate spend, objective); define overflow and conversion-error behavior.
6. **Optimization semantics:** define objective terms, constraints, risk/CVaR inputs, tie rules, deterministic ordering, solver/resource limits, exact-vs-fallback status and infeasible behavior. Keep Python authoritative.
7. **Versioning/compatibility:** preserve v1 models/schema/protobuf semantics; create v2 schema/protobuf/request-result surfaces rather than renaming or reinterpreting v1 fields.
8. **Evidence:** independent fixed oracles, cross-rate/reciprocal and rounding tests, mixed-currency budgets, equal objective and zero-cost ties, invalid/stale/missing FX, infeasible portfolios, resource/fallback boundaries, property/generated/adversarial cases and same-input Python–Rust differential comparisons.

## Required next actions

- [ ] Inventory all call sites and tests for the listed optimizer functions and `Money`; verify whether any hidden assumptions exist outside the inspected files.
- [ ] Read the full intervention/scenario/counterfactual models and current schema/proto consumers before finalizing the v2 request/result.
- [ ] Write a short ADR for money representation, FX snapshot semantics, rounding and v1 compatibility.
- [ ] Define the exact v2 request/result/error/status schema and independent examples.
- [ ] Add Python-only contract/reference tests first; do not implement Rust until Python behavior and independent oracles are approved.
- [ ] Implement the matched Rust adapter and differential suite in small PRs, then update the matrix only from verified evidence.

## Explicit non-claims

This audit does not claim full portfolio optimization parity, multi-currency support, correct FX conversion, or Rust parity. The current accepted `integer_knapsack` operation remains a generic bounded primitive and is not a substitute for the portfolio optimizer.
