# QEDTY documentation

This directory contains the technical documentation for QEDTY. Use this index to find the
authoritative document for a topic. Repository-wide project information and the quick start
are in the [root README](../README.md).

## Start here

| If you need to understand... | Read |
|---|---|
| The system architecture and component boundaries | [Architecture](ARCHITECTURE.md) |
| The P00–P15 engineering roadmap and acceptance boundaries | [Roadmap](ROADMAP.md) |
| How documentation is written and maintained | [Documentation standards](DOCUMENTATION_STANDARDS.md) |
| Release and validation requirements | [Release readiness](RELEASE_READINESS.md) |
| Operational procedures | [Operations](OPERATIONS.md) |
| Data sources and ingestion boundaries | [Data sources](DATA_SOURCES.md) |
| Evidence and provenance | [Evidence documentation](evidence/README.md) |
| Ontology and interoperability | [Ontology documentation](ontology/README.md) |
| Temporal modelling | [Temporal documentation](temporal/README.md) |
| Scenario modelling | [Scenario documentation](scenarios/README.md) |
| Propagation | [Propagation documentation](propagation/README.md) |
| Graph contracts and research | [Graph contracts](graph/CONTRACTS.md) |
| Cross-language implementation and verification | [Engineering records](engineering/CROSS_LANGUAGE_CONFORMANCE_EXPANSION.md) |
| Research sources for cross-language conformance | [Research references](research/CROSS_LANGUAGE_CONFORMANCE_REFERENCES.md) |

## Documentation areas

- `engineering/` — implementation records, conformance scope, and engineering decisions.
- `evidence/`, `ontology/`, `temporal/`, `scenarios/`, `propagation/`, and `graph/`
  — domain concepts, contracts, research, and validation.
- `qedty/` — component-level algorithm contracts and research baselines.
- `research/` — external references and standards research.

## Reading status

A document's presence does not imply that every described capability is implemented. Check
its implementation-status statements and follow the linked source, contract, tests, and
verification record. The root README describes the current repository boundary; release
readiness is governed by the checks on the exact release candidate.
