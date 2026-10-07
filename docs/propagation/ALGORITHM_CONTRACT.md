# Propagation algorithm contract

## Signal semantics

For an edge `u -> v`, a path contribution is:

`candidate = parent_impairment × relationship_strength × relationship_capacity_fraction × explicit_propagation_factor × target_attenuation`

where target attenuation is derived only from explicit intervention/state controls.

## Time semantics

A signal leaves the current entity at `effective_at`. Relationship validity is checked at departure. An optional explicit delay is then applied. By default the same relationship must still be valid at arrival.

## Path semantics

A path is a sequence of entity IDs and relationship IDs. Cycles are disallowed by default. When cycles are explicitly enabled, `max_hops` remains a hard bound.

## Aggregation

- `max`: strongest path only.
- `sum_cap`: sum path contributions and clip at 1.
- `noisy_or`: combine path contributions as independent bounded effects: `1 - product(1-c_i)`.

These are model forms, not universal causal laws. The selected form is persisted in the result summary and rule digest.

## Bounds

`max_hops`, `max_signals`, and `max_paths_per_entity` are hard computational safety controls. If a bound truncates execution, the result is explicitly marked `TRUNCATED` and records a termination reason.

## Epistemic boundary

Every engine-generated effect is `MODELED`, or `COUNTERFACTUAL` when explicit mitigation/override inputs are used. A source shock may itself be observed, but the propagated result remains a model output.
