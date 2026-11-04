# QEDTY architecture

QEDTY is a contract-driven platform for representing, querying, propagating, evaluating, and
governing evidence-backed models of interconnected systems and their continuity under
disruption.

This document describes the architecture visible in the repository and separates it from
future architectural targets. It is an engineering reference, not a claim that every
planned service or deployment capability has been implemented.

## Architectural objective

QEDTY aims to provide a common computational foundation for understanding interconnected
entities, capabilities, services, resources, events, dependencies, and flows. It preserves
the evidence and assumptions behind model results and supports scenario analysis,
propagation, continuity assessment, economic impact modelling, counterfactual comparison,
uncertainty handling, and optimization.

The platform is designed to support multiple domains through shared semantics and
versioned interfaces rather than creating unrelated domain-specific engines.

## Canonical information flow

The principal conceptual flow is:

```text
source acquisition
  -> evidence capture and provenance
  -> normalization and entity resolution
  -> canonical world model
  -> temporal / spatial graph
  -> scenario and intervention
  -> propagation
  -> continuity assessment
  -> economic assessment
  -> counterfactual comparison
  -> uncertainty analysis
  -> optimization
  -> governed, evidence-backed result
```

This is a logical dependency flow, not a requirement that every request execute every
stage. A result must retain the relevant source, model, contract, temporal, spatial,
assumption, and provenance context.

The repository-security source adapter is a bounded integration. It does not define the
platform's core domain model.

## Semantic authority and implementations

### Python

Python is the current semantic/reference and application implementation. The source tree
contains domain packages for core identity and types, ontology, evidence, temporal and
spatial semantics, graph structures, scenarios, propagation, continuity, economics,
counterfactuals, uncertainty, intelligence, optimization, governance, sources, storage,
orchestration, API, output, and CLI.

Python defines the reference behavior for the current application. Its presence does not
mean every domain has been independently validated against representative production data.

### Rust

The Rust workspace contains the shipped deterministic native core. It implements a bounded
set of operations including deterministic identity/canonicalization, checked geometry
helpers, quantities and contract-result primitives, timestamp and interval primitives,
selected spatial indexing, in-memory graph algorithms, and numeric/columnar adapter kernels.

Rust is not a complete duplicate implementation of the Python domain model. The supported
cross-language boundary is the operation-level conformance surface documented in
[Rust conformance](../rust/CONFORMANCE.md) and the engineering records.

### Contracts and interoperability

The repository contains machine-readable and typed interface surfaces including:

- JSON Schema for structured contract validation;
- Protobuf definitions for typed service and domain boundaries;
- RDF, Turtle, JSON-LD, OWL, and SHACL artifacts for semantic interoperability;
- Apache Arrow-oriented data contracts and optional Python Arrow/Parquet support;
- golden vectors for deterministic expected-value behavior.

A mapping to an external standard is a bounded interoperability profile, not proof of
complete conformance to every feature of that standard. The relevant contract and profile
must define the supported subset.

## Data and evidence model

QEDTY separates source acquisition, evidence integrity, provenance, quality, rights, and
interpretation.

- **Evidence integrity** concerns whether a captured representation matches its digest.
- **Provenance** records how a representation was acquired, transformed, or associated with
  a claim.
- **Quality** records explicit measurements and methods.
- **Rights** record licensing and permission state.
- **Interpretation** occurs downstream and must not silently rewrite source evidence.

The epistemic vocabulary distinguishes `observed`, `derived`, `inferred`, `modeled`,
`counterfactual`, and `unknown`. These states are not interchangeable. A model output is
not an observation merely because software produced it.

See [evidence documentation](evidence/README.md), [provenance policy](PROVENANCE.md), and
the relevant contract definitions for normative behavior.

## Temporal, spatial, and graph model

The world model represents entities and typed relationships with temporal and spatial
context. The current repository includes UTC-normalized time handling, interval semantics,
temporal indexes and snapshots, geospatial primitives, coordinate-reference boundaries,
and graph algorithms.

The exact behavior is bounded by the implemented contracts and tests. For example, a
valid-time snapshot is not automatically a complete bitemporal history query, and a
spherical Haversine calculation is not equivalent to an ellipsoidal geodesic solution.

See [temporal documentation](temporal/README.md), [graph contracts](graph/CONTRACTS.md),
and [geospatial documentation](GEOSPATIAL.md).

## Modelling and decision pipeline

The domain layers support a sequence of model operations:

1. **Scenarios** represent explicit changes or interventions against a declared baseline.
2. **Propagation** computes bounded effects through configured relationships and rules.
3. **Continuity** evaluates capacity, availability, substitution, recovery, and related
   continuity properties within the model's assumptions.
4. **Economics** represents direct and indirect modelled exposure and impact.
5. **Counterfactuals** compare declared baseline and intervention worlds; they are not
   empirical causal estimates by default.
6. **Uncertainty** represents uncertainty and sensitivity where the configured methods
   support them.
7. **Optimization** evaluates candidate interventions against declared objectives,
   constraints, and solver semantics.
8. **Governance** preserves constraints, review, provenance, and audit requirements.

The existence of a module does not establish that every model is calibrated, causally
identified, globally optimal, or suitable for an operational decision. Each claim requires
domain-specific validation.

## Storage, orchestration, and interfaces

The current Python implementation includes local/reference storage capabilities, source
adapters, deterministic orchestration, API routes, output representations, and a CLI.
The repository includes Protobuf and Arrow-related contracts, but their presence should not
be confused with a deployed distributed control plane or production data plane.

The root README and package documentation describe the currently runnable commands and
interfaces. Operational guarantees require deployment-specific validation.

## Future execution targets

The broader architecture has identified additional targets:

| Target | Intended responsibility | Repository status |
|---|---|---|
| Go | Operational services, agents, and edge execution | Future target; no Go implementation currently tracked |
| C/C++/CUDA | Selective specialized native or GPU acceleration | Future target; no such implementation currently tracked |
| TypeScript/React | Operator console and visualization | Future target; no frontend implementation currently tracked |
| PostgreSQL/PostGIS services | Production authoritative state and spatial persistence | Future deployment target; distinguish from current SQLite/reference storage |
| WIT/WASM | Portable component and execution boundary | Future target; no WIT/WASM implementation currently tracked |

These technologies must implement existing semantic contracts rather than independently
redefine domain meaning. Introduce them only when a measured requirement justifies the
additional operational and maintenance cost.

## Cross-cutting engineering requirements

Every component should make its boundaries explicit:

- inputs, outputs, and validation;
- semantic ownership and authoritative state;
- identity and canonicalization rules;
- temporal and spatial assumptions;
- evidence, provenance, and epistemic state;
- deterministic behavior and numerical tolerances;
- failure modes and resource limits;
- compatibility and versioning;
- tests, fixtures, and verification evidence.

Cross-language implementations must be compared against explicit contracts and independent
oracles. Performance claims must identify workload, hardware, runtime, method, and baseline.

## End-to-end validation

The platform is validated incrementally through unit tests, contract tests, golden vectors,
differential tests, integration tests, and hosted CI. Passing one layer does not prove the
entire pipeline.

A full end-to-end claim requires a reproducible workflow that begins with representative
source evidence and reaches a governed result, while preserving provenance and assumptions.
It also requires documented scope, expected outputs, failure behavior, performance limits,
and independent or domain-qualified validation where appropriate.

See [release readiness](RELEASE_READINESS.md), [cross-language conformance expansion](engineering/CROSS_LANGUAGE_CONFORMANCE_EXPANSION.md),
and the current GitHub Actions runs for commit-specific evidence.

## Related documents

- [Repository README](../README.md)
- [Documentation index](README.md)
- [Documentation standards](DOCUMENTATION_STANDARDS.md)
- [Data-source boundaries](DATA_SOURCES.md)
- [Geospatial boundaries](GEOSPATIAL.md)
- [Economics](ECONOMICS.md)
- [Space-domain boundaries](SPACE.md)
- [Operations](OPERATIONS.md)
- [Release readiness](RELEASE_READINESS.md)
