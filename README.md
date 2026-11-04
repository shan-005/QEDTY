# QEDTY

**Evidence-backed planetary continuity intelligence**

QEDTY is a contract-driven platform for representing, querying, propagating, evaluating, and
governing evidence-backed models of interconnected systems and their continuity under
disruption.

Its long-term objective is to provide a shared computational foundation for understanding
complex dependencies, modelling cascading effects, evaluating uncertainty, comparing
interventions, and supporting auditable decisions across multiple domains.

> **Project status:** active alpha engineering system. The current repository implements a
> Python semantic/reference and application layer, a bounded Rust deterministic native
> core, and contract/interoperability surfaces. The broader multi-language and planetary-scale
> architecture is a development direction, not a claim that every planned component is
> already implemented or production-validated.

- Package: `qedty`
- Current package version: `0.1a0`
- Python: `>=3.12,<3.14`
- License: Apache-2.0
- Repository: [shan-005/QEDTY](https://github.com/shan-005/QEDTY)

## What QEDTY is designed to do

QEDTY models entities, capabilities, services, resources, relationships, events, dependencies,
and flows with explicit evidence, provenance, temporal and spatial context.

It supports questions such as:

- Which entities and capabilities exist, and how are they connected?
- What evidence and provenance support a record or claim?
- Where and when does a relationship or capability apply?
- How might an explicit shock or intervention propagate through a dependency graph?
- What continuity effects or economic exposures are represented by a scenario?
- How do baseline and intervention worlds differ under declared assumptions?
- What uncertainty enters a result, and how does it affect the conclusion?
- Which candidate interventions satisfy declared objectives and constraints?

The platform distinguishes `observed`, `derived`, `inferred`, `modeled`,
`counterfactual`, and `unknown` epistemic states. A model output is not silently promoted
to an observation.

## Current implementation boundary

The following table describes source and contract surfaces present in the repository. It
does not imply that every domain is complete, calibrated, or production-ready.

| Technology | Current status |
|---|---|
| Python | Semantic/reference and application implementation, tests, and conformance tooling |
| Rust | Bounded deterministic native core in `crates/qedty-core/` |
| Protobuf | Typed contract definitions under `proto/qedty/` |
| JSON Schema | Machine-readable contracts under `contracts/` and packaged schemas |
| RDF / Turtle / JSON-LD / SHACL | Semantic interoperability artifacts and bounded validation profiles |
| Arrow / Parquet | Arrow-oriented contract boundaries and optional Python support |
| SQLite | Local/reference storage capability in Python |
| Go | Future operational-service and agent target; no tracked Go implementation |
| C / C++ / CUDA | Future selective acceleration target; no tracked implementation |
| TypeScript / React | Future console target; no tracked frontend implementation |
| PostgreSQL / PostGIS services | Future production persistence target; not the current semantic authority |
| WIT / WASM | Future portable execution target; no tracked implementation |

Python remains the current semantic/reference authority. Rust implements a bounded operation
set; it is not a complete port of the Python domain model. Future execution targets must
conform to the established semantic contracts.

For exact current inventory, inspect `QEDTY-PROJECT-MANIFEST.json` and run the repository
inventory check. Do not copy static file counts into this README.

## Architecture

The principal conceptual pipeline is:

```text
sources
  -> evidence and provenance
  -> normalization and entity resolution
  -> canonical world model
  -> temporal / spatial graph
  -> scenario and intervention
  -> propagation
  -> continuity
  -> economics
  -> counterfactual comparison
  -> uncertainty
  -> optimization
  -> governed, evidence-backed result
```

Not every workflow executes every stage. Results retain the evidence, assumptions, model
scope, and contract context relevant to the computation.

The current Python domain surface includes core, ontology, evidence, temporal, spatial,
graph, scenarios, propagation, continuity, economics, counterfactual, uncertainty,
intelligence, optimization, governance, sources, storage, orchestration, API, output, and
CLI packages.

The Rust core provides selected deterministic identity/canonicalization, geometry, quantity,
time/interval, spatial-index, graph, and numeric/columnar primitives. Its supported boundary
is defined by code, fixtures, and the operation-level conformance documentation.

See [the architecture reference](docs/ARCHITECTURE.md) for component responsibilities,
data flow, boundaries, and future execution targets.

## Roadmap

The initial engineering roadmap is organized as P00–P15:

- **P00–P03:** project foundation, Python semantic/reference implementation, Rust core,
  and Python–Rust differential conformance.
- **P04:** canonical data contracts, identity, evidence, and provenance.
- **P05–P08:** ingestion and interoperability; temporal, spatial, and graph intelligence;
  modelling and simulation; uncertainty and evidence confidence.
- **P09–P13:** domain applications; performance and observability; operational services
  and agents; APIs and user interfaces; security, governance, and resilience.
- **P14–P15:** end-to-end integration and validation; production readiness and deployment.

The recorded engineering handoff identifies **Cross-Language Conformance Expansion** as the
active milestone, with canonical contract, identity, evidence, and provenance work in the
current P04 scope. Check the current branch, pull requests, issues, and CI before relying on
a historical status statement.

P15 is the initial production-readiness boundary, not the end of QEDTY's evolution. See
[the roadmap](docs/ROADMAP.md) for phase objectives, deliverables, and status discipline.

## Quick start

### Requirements

- Python `>=3.12,<3.14`
- `uv` compatible with the version declared in `pyproject.toml`
- Rust toolchain for native-core development and tests

### Install

```bash
git clone https://github.com/shan-005/QEDTY.git
cd QEDTY
uv sync
```

Activate the environment if desired:

```bash
source .venv/bin/activate
```

### Run the application

```bash
python -m qedty validate
python -m qedty demo
qedty --help
```

### Run tests and quality checks

```bash
uv run pytest -q --cov-fail-under=60
uv run ruff check src tests
uv run ruff format --check src tests
uv run mypy src
```

For the repository verification gate:

```bash
./scripts/verify.sh
```

For Rust:

```bash
cargo test --manifest-path crates/qedty-core/Cargo.toml --locked
```

Use the scripts and workflow definitions on the branch being tested as the authoritative
source for the current verification commands.

## Repository layout

| Path | Purpose |
|---|---|
| `src/qedty/` | Python semantic/reference and application implementation |
| `crates/qedty-core/` | Rust native core |
| `contracts/` | Machine-readable semantic and interface contracts |
| `proto/qedty/` | Protobuf definitions |
| `data/contracts/golden-vectors/` | Shared deterministic expected-value fixtures |
| `tests/` | Unit, integration, contract, and conformance tests |
| `scripts/` | Verification and conformance tooling |
| `docs/` | Architecture, roadmap, research, contracts, operations, and engineering records |
| `policies/` | Repository and domain control policies |
| `.github/` | CI, release, dependency, and collaboration workflows |

## Contract and change discipline

A semantic change should update the affected surfaces together:

1. canonical contract or schema;
2. golden vectors and fixtures;
3. Python reference behavior;
4. Rust implementation where the operation is supported cross-language;
5. tests and conformance tooling;
6. interoperability representations where affected;
7. documentation and migration notes;
8. release verification.

Do not silently change identity, epistemic, temporal, spatial, quantity, propagation, or
result semantics.

## Verification and non-claims

The current GitHub Actions runs for the exact commit are the source of truth for hosted
verification. A passing check proves only the behavior and scope that the check exercised.

The current alpha status does not establish:

- production-critical operational certification;
- authoritative forecasts of the physical world;
- empirical causal identification from graph propagation alone;
- complete conformance to every feature of mapped external standards;
- universal entity-resolution accuracy;
- calibrated probabilities for arbitrary confidence scores;
- global optimality where a heuristic or greedy fallback is used;
- planetary-scale performance without representative large-scale benchmarks;
- implementation of future Go, C/C++/CUDA, TypeScript/React, PostgreSQL service, or
  WIT/WASM targets.

Model results must be interpreted with their evidence, assumptions, uncertainty,
provenance, contract version, and model version.

## Documentation and project governance

- [Documentation index](docs/README.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Roadmap](docs/ROADMAP.md)
- [Documentation standards](docs/DOCUMENTATION_STANDARDS.md)
- [Research baseline](docs/RESEARCH_BASELINE.md)
- [Release readiness](docs/RELEASE_READINESS.md)
- [Operations](docs/OPERATIONS.md)
- [Contributing](CONTRIBUTING.md)
- [Code of Conduct](CODE_OF_CONDUCT.md)
- [Security policy](SECURITY.md)
- [Support](SUPPORT.md)
- [Changelog](CHANGELOG.md)

## Citation and license

Citation metadata is provided in [`CITATION.cff`](CITATION.cff). QEDTY is licensed under
the Apache License 2.0; see [`LICENSE`](LICENSE).
