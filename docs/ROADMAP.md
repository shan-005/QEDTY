# QEDTY engineering roadmap

This roadmap describes the initial P00–P15 engineering programme. It defines intended
capability boundaries and acceptance outcomes; it is not evidence that a phase is complete.
Implementation status must be established from source, contracts, tests, pull requests, and
hosted checks on the relevant commit.

## Roadmap principles

- Build one integrated platform, not a collection of disconnected domain products.
- Preserve Python's current semantic/reference authority.
- Expand Rust only through explicit, tested operation contracts.
- Treat schemas, interfaces, fixtures, and compatibility rules as engineering artifacts.
- Keep evidence, provenance, uncertainty, and governance attached to model results.
- Separate implemented capabilities from planned execution targets.
- Validate end-to-end workflows using representative evidence and domain-qualified review.
- Treat P15 as the initial production-readiness boundary, not the end of product evolution.

## Phase map

| Phase | Name | Primary outcome |
|---|---|---|
| P00 | Project Foundation and Architecture | Repository, engineering standards, package foundation, and architectural boundaries |
| P01 | Python Semantic Reference and Application Foundation | Canonical domain semantics and reference workflows |
| P02 | Rust Deterministic Compute Core | Bounded native operations with deterministic behavior |
| P03 | Python–Rust Differential Conformance | Operation-level compatibility evidence |
| P04 | Canonical Data Contracts, Identity, Evidence, and Provenance | Versioned canonical interfaces and traceable evidence |
| P05 | Data Ingestion, Interoperability, and Quality | Reliable acquisition and normalization of external data |
| P06 | Temporal, Geospatial, and Graph Intelligence | A coherent representation of entities, relationships, location, and time |
| P07 | Analytics, Modelling, and Simulation | Reproducible system and scenario computation |
| P08 | Uncertainty, Evidence, and Confidence Modelling | Explicit treatment of incomplete, conflicting, and uncertain information |
| P09 | Domain Models and Planetary-Continuity Applications | Reusable applications across interconnected domains |
| P10 | Performance, Scaling, and Observability | Measured performance, operational visibility, and scalable execution |
| P11 | Operational Services and Edge Agents | Distributed collection, coordination, and execution services |
| P12 | APIs, Console, and User Integration | Interfaces for users, developers, and external systems |
| P13 | Security, Governance, and Resilience | Institutional security and operational control foundations |
| P14 | End-to-End Integration and System Validation | Verified data-to-decision workflows across the integrated platform |
| P15 | Production Readiness, Deployment, and Maintenance | Deployable, supportable, versioned initial platform |

## Phase objectives and acceptance outcomes

### P00 — Project Foundation and Architecture

Establish repository identity, package layout, engineering practices, versioning, CI,
documentation, contribution policy, and architectural boundaries.

Acceptance evidence includes reproducible development setup, repository checks, documented
ownership boundaries, and a maintainable contribution workflow.

### P01 — Python Semantic Reference and Application Foundation

Establish the canonical domain concepts and reference behavior for identity, ontology,
evidence, temporal and spatial semantics, graphs, scenarios, propagation, continuity,
economics, counterfactuals, uncertainty, intelligence, optimization, governance, sources,
storage, orchestration, APIs, outputs, and CLI workflows.

Acceptance evidence must identify the implemented domain scope, tests, contract versions,
and limitations. Module presence alone is not semantic validation.

### P02 — Rust Deterministic Compute Core

Implement selected performance-sensitive operations in Rust without independently
redefining Python-owned domain semantics.

Each operation requires a bounded contract, deterministic behavior, input validation,
error semantics, tests, and documented performance rationale.

### P03 — Python–Rust Differential Conformance

Establish independent reference oracles, fixed edge cases, deterministic generated cases,
replayable seeds, and operation-level conformance reporting.

A conformance result applies only to the named operations, versions, fixtures, and tested
inputs. It does not imply that the entire Python domain model has been ported.

### P04 — Canonical Data Contracts, Identity, Evidence, and Provenance

Stabilize canonical identity, schemas, contract versioning, evidence records, provenance
links, and cross-language interpretation rules.

Acceptance evidence includes explicit contract ownership, compatibility policy, golden
vectors where appropriate, validation tooling, and documented migration behavior.

### P05 — Data Ingestion, Interoperability, and Quality

Expand source adapters and ingestion workflows for structured and unstructured sources.
Provide validation, normalization, entity resolution, source metadata, rights tracking,
refresh behavior, and data-quality measurement.

Acceptance evidence must use representative source fixtures and document licensing,
coverage, parser limitations, and failure behavior. Connector count alone is not quality.

### P06 — Temporal, Geospatial, and Graph Intelligence

Develop a coherent world representation for entities and relationships across time and
space. Define temporal validity, historical state, coordinate-reference behavior, spatial
operations, graph semantics, and dependency queries.

Acceptance evidence includes contract-level boundary tests and representative temporal,
spatial, and graph workflows.

### P07 — Analytics, Modelling, and Simulation

Develop reproducible analytical models and scenario simulation across connected systems.
Make model assumptions, inputs, outputs, numerical behavior, and failure conditions explicit.

Acceptance evidence includes independent oracles where feasible, sensitivity tests,
benchmark workloads, and representative domain validation.

### P08 — Uncertainty, Evidence, and Confidence Modelling

Represent uncertainty, missingness, conflicting evidence, assumptions, sensitivity, and
confidence without conflating them. Define how uncertainty enters and propagates through
each supported computation.

Acceptance evidence requires method-specific validation and calibration where the method
claims probabilistic meaning. A confidence score is not automatically a calibrated
probability.

### P09 — Domain Models and Planetary-Continuity Applications

Build reusable domain models and integrated applications across areas such as supply
chains, energy, infrastructure, finance, economics, environmental systems, government,
defence, cyber, urban systems, science, and space.

Applications must reuse shared contracts and preserve domain-specific assumptions. The
phase does not imply that every possible domain is implemented or validated.

### P10 — Performance, Scaling, and Observability

Measure and improve throughput, latency, memory use, storage behavior, parallelism, and
operational observability. Add acceleration only where profiling demonstrates a need.

Acceptance evidence must state workload size, data shape, hardware, software versions,
baseline, method, and reproducibility. Planetary-scale claims require representative
large-scale evidence.

### P11 — Operational Services and Edge Agents

Develop service and agent infrastructure for data collection, coordination, distributed
execution, and integration with external systems. Define service identity, permissions,
retries, backpressure, telemetry, and failure recovery.

Go is an identified target, not an implementation claim until source and tests exist.

### P12 — APIs, Console, and User Integration

Provide stable APIs and usable interfaces for analysts, engineers, developers, and
institutional operators. Include visualization, scenario exploration, result inspection,
and auditable workflows.

TypeScript/React is an identified target, not an implementation claim until source and
tests exist.

### P13 — Security, Governance, and Resilience

Establish authentication, authorization, isolation, secrets management, audit, policy
enforcement, backup, recovery, incident response, and deployment hardening.

Acceptance evidence must include threat modelling, security testing, operational procedures,
and deployment-specific controls. Repository CI alone is not a security certification.

### P14 — End-to-End Integration and System Validation

Verify complete workflows from source acquisition through evidence, world modelling,
simulation, uncertainty, optimization, governance, and decision outputs.

Acceptance evidence includes reproducible end-to-end fixtures, exact commit references,
integration and failure-path tests, representative data, performance boundaries, and
independent or domain-qualified review where required.

### P15 — Production Readiness, Deployment, and Maintenance

Establish supported deployment profiles, versioned releases, upgrade and migration
procedures, monitoring, incident response, documentation, artifact integrity, and
maintenance ownership.

Production readiness is scoped to a defined deployment profile and service commitment. It
does not mean universal suitability for every domain or environment.

## Recorded engineering status

The repository has substantial Python semantic/reference work and a bounded Rust native
core. Cross-language differential testing and canonical contract work have been active
engineering areas.

The last recorded project handoff identifies **Cross-Language Conformance Expansion** as
the active milestone and P04 as the current contract/identity/evidence/provenance scope.
This statement is a handoff snapshot, not a live status guarantee. Check the current
`main` commit, open pull requests, issues, and GitHub Actions before treating it as current.

For each phase, maintain an implementation record with:

- accepted scope and dependencies;
- source paths and contract versions;
- tests and fixtures;
- exact commit and pull request references;
- hosted verification on the exact head SHA;
- accepted exclusions and unresolved gaps;
- completion decision and reviewer rationale.

## Beyond P15

P15 establishes the initial production-readiness boundary. It does not cap the future
platform.

Later generations may extend continuous intelligence, real-time evidence updates,
distributed and federated computation, more advanced system models, additional scientific
domains, autonomous evidence discovery, new hardware, and new interoperability boundaries.
Such work must preserve versioned contracts, migration discipline, security, and
backward-compatibility policy.

## Related documents

- [Architecture](ARCHITECTURE.md)
- [Documentation standards](DOCUMENTATION_STANDARDS.md)
- [Release readiness](RELEASE_READINESS.md)
- [Cross-language conformance expansion](engineering/CROSS_LANGUAGE_CONFORMANCE_EXPANSION.md)
- [Contributing](../CONTRIBUTING.md)
