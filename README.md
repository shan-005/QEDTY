# QEDTY

**QEDTY (Planetary Continuity Intelligence)** is an evidence-backed world-model and scenario-analysis platform for understanding how disruptions propagate through space, geospatial systems, critical infrastructure, services, supply networks and economic functions.

The canonical computation chain is:

```text
evidence
  -> entity resolution
  -> canonical world model
  -> temporal/spatial graph
  -> world state
  -> shock/scenario
  -> propagation
  -> continuity
  -> economic impact
  -> counterfactual intervention
  -> uncertainty
  -> resilience optimization
  -> governed claims
```

Repository security is **one source adapter**, not the platform architecture.

## Native architecture

QEDTY owns its internal semantics: deterministic identities, assertions, temporal validity, spatial scope, capabilities, services, flows, events, scenarios, evidence lineage and epistemic state. External standards are interoperability boundaries rather than internal dependencies.

Relevant standards currently used at the boundaries include OGC API – Features and OGC JSON-FG for geospatial exchange, CCSDS orbit/tracking message families for space data, IGS RINEX/SSR formats for GNSS, W3C PROV-O for provenance interoperability, the UN 2025 System of National Accounts for macroeconomic semantics, and SLSA 1.2 for software-supply-chain attestation. citeturn862166search5turn862166search2turn862166search4turn862166search0turn862166search1turn862166search7turn862166search6

## Epistemic discipline

Every material result is explicitly one of:

- `OBSERVED` — directly supported by source evidence.
- `DERIVED` — deterministic transformation of supported inputs.
- `INFERRED` — analytical inference from declared evidence.
- `MODELED` — output of a declared computational model.
- `COUNTERFACTUAL` — result under an explicit intervention/scenario.
- `UNKNOWN` — insufficient support to make a defensible determination.

QEDTY does not treat model output as observation, and it does not claim universal forecasting, causal truth, complete world coverage, or superiority over another platform merely because a test passes.

## Quick start

```bash
uv sync --all-groups --all-extras
uv run qedty validate
uv run qedty demo
uv run pytest -q
```

World-state workflow:

```bash
uv run qedty entity create --type satellite --name "DemoSat"
uv run qedty scenario demo
uv run qedty impact demo
uv run qedty resilience demo
```

## Security subsystem

The repository-security subsystem lives under `qedty.sources.repository_security`. It emits normalized security observations into the same evidence/world-model contracts. It is not the canonical intelligence object and cannot redefine the world-model schema.

## Scope and limitations

The current release is a production-oriented architecture and deterministic engine foundation. Live external acquisition is adapter-driven and must be configured with source-specific authentication, licensing and refresh policy. Economic and shock engines expose explicit assumptions and model status; they are not substitutes for official statistics, domain-qualified forecasting, or operational control systems.

## License

Apache-2.0. See `LICENSE`.
