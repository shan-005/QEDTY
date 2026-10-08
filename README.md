# QEDTY

**QEDTY — evidence-backed planetary continuity intelligence**

QEDTY is a contract-driven platform for representing, querying, propagating, evaluating, and governing evidence-backed models of interconnected planetary systems and their continuity under disruption.

The repository is an **active alpha engineering system**. Its current implementation is intentionally narrower than the long-term polyglot architecture: **Python is the semantic/reference and application implementation, Rust provides the shipped deterministic native core, and Protobuf/JSON Schema/RDF/SHACL/Arrow are contract and interoperability surfaces.** Other execution environments described in research and architecture documents are future targets, not source trees already present in this repository.

- **Current product version:** `0.1a0`
- **License:** Apache-2.0
- **Repository:** `https://github.com/shan-005/QEDTY`
- **Default branch:** `main`
- **Current release state:** alpha / engineering development

## What QEDTY is for

QEDTY is designed for questions such as:

- What entities, capabilities, services, relationships, and flows exist?
- Where are they, and during which validity intervals do they apply?
- What evidence and provenance support a record or claim?
- Which dependencies connect capabilities and services?
- What happens when capacity, availability, or another system attribute changes?
- How does an explicit shock or intervention propagate through a dependency graph?
- What is the modeled continuity effect of an intervention or counterfactual?
- What uncertainty attaches to a result, and where does it enter the computation?
- What economic exposure or modeled impact accompanies a scenario?
- Which statements are `observed`, `derived`, `inferred`, `modeled`, `counterfactual`, or `unknown`?

QEDTY therefore treats important results as evidence-bearing, provenance-preserving objects rather than unexplained scalar values.

## Current implementation: what is actually in this repository

The current Git tree contains the following source/interface surface at the `5fff1e2` alpha baseline:

| Technology | Current repository status | What is present now |
|---|---|---|
| **Python** | **Implemented** | 263 tracked `.py` files covering the semantic/reference and application layers, tests, conformance tooling, and scripts |
| **Rust** | **Implemented** | `crates/qedty-core/` with the deterministic native core and golden-vector tests |
| **Protobuf** | **Implemented as contract source** | 18 `.proto` service/domain definitions under `proto/qedty/` |
| **JSON Schema** | **Implemented as contracts** | Machine-readable semantic and interface schemas under `contracts/` and packaged schemas |
| **RDF / Turtle / JSON-LD / SHACL** | **Implemented as interoperability contracts/boundaries** | RDF/Turtle, JSON-LD, and SHACL artifacts under `contracts/` |
| **Apache Arrow** | **Implemented as data-plane contract/boundary** | Arrow-oriented contract artifacts and optional Python Arrow/Parquet support |
| **SQL / SQLite** | **Reference capability in Python** | Python storage/query code includes an SQLite reference backend and database adapters; there are **no standalone `.sql` source files** in the current tree |
| **Go** | **Not yet implemented in this repository** | No tracked `.go` files; described only as a future operational/edge/service target |
| **C / C++ / CUDA** | **Not yet implemented in this repository** | No tracked C/C++/CUDA source; described only as future selective native/GPU acceleration |
| **TypeScript / React** | **Not yet implemented in this repository** | No tracked `.ts`, `.tsx`, `.js`, or `.jsx` source; the web console is a future target |
| **WIT / WASM** | **Not yet implemented in this repository** | No tracked WIT/WASM source; described as a future portable execution/component boundary |

This distinction is deliberate. QEDTY has one semantic authority and multiple planned execution boundaries; future languages must conform to the existing contracts rather than silently redefining domain meaning.

### Repository inventory snapshot

The current `main` tree contains **481 tracked files**:

- 263 Python files
- 2 Rust files
- 18 Protobuf files
- 63 Markdown files
- 77 JSON files
- 24 Turtle (`.ttl`) files
- 18 YAML/YML files
- 3 shell scripts
- additional project metadata and lock/configuration files

There are currently **zero tracked files** for Go, C/C++, CUDA, TypeScript/TSX/JavaScript/JSX, standalone SQL, WIT, or WASM.

## Architecture

QEDTY is structured around a shared semantic and contract surface.

### Implemented now

```text
                    QEDTY semantic/reference surface
                                Python
                                  │
        ┌─────────────────────────┼─────────────────────────┐
        │                         │                         │
   contracts                  execution                 verification
        │                         │                         │
 JSON Schema / RDF /        Rust native core        tests / vectors /
 SHACL / JSON-LD /          (qedty-core)            conformance /
 Protobuf / Arrow                                   policies / CI
```

The primary Python implementation contains these established layers:

- `core`
- `ontology`
- `evidence`
- `temporal`
- `spatial`
- `graph`
- `scenarios`
- `propagation`
- `continuity`
- `economics`
- `counterfactual`
- `uncertainty`
- `intelligence`
- `optimization`
- `governance`
- `sources`
- `storage`
- `orchestration`
- API / output / CLI

### Native core implemented now

`crates/qedty-core/` is the shipped Rust component. Its current role is deliberately small and deterministic. It provides reference-native behavior for:

- canonical JSON ordering;
- SHA-256 digests;
- deterministic IDs;
- core reference value types;
- WGS-84 ECEF conversion;
- golden-vector conformance tests.

The Rust crate is **not** a duplicate implementation of the whole Python domain model.

### Future execution targets

The architecture and research documents discuss additional execution environments, but they are not part of the current source tree:

```text
Go                 -> operational / edge / agent services
C++ / CUDA         -> selective specialized native/GPU acceleration
TypeScript / React -> web console / visualization / operator UI
SQL / PostgreSQL   -> production relational + spatiotemporal persistence
WIT / WASM         -> portable component/execution boundary
```

Those targets are roadmap architecture. They must conform to the same contracts, identifiers, temporal semantics, spatial semantics, epistemic states, evidence/provenance rules, and golden vectors.

## Contract-first design

Contracts are executable interoperability surfaces, not documentation-only descriptions.

Current contract technologies include:

- JSON Schema Draft 2020-12 for machine-readable document validation;
- Protobuf for typed service/control boundaries;
- Apache Arrow for columnar data interchange;
- RDF / OWL / JSON-LD for semantic-web interoperability;
- SHACL for bounded RDF graph validation;
- golden vectors for deterministic cross-implementation conformance;
- content-addressed SHA-256 identities for evidence and provenance integrity.

The contract directories under `contracts/` are accompanied by tests and conformance tooling. Golden vectors under `data/contracts/golden-vectors/` are normative expected-value fixtures for implementations.

## Epistemic and provenance model

QEDTY explicitly distinguishes:

```text
observed
   ↓
derived
   ↓
inferred
   ↓
modeled
   ↓
counterfactual
   ↓
unknown
```

These states are not interchangeable. A model output is not relabeled as an observation merely because it is produced by software.

Evidence and provenance are separate concerns:

- **integrity** means the captured representation matches its digest;
- **provenance** records how and why the representation entered the pipeline;
- **quality** records explicit measurements and methods;
- **rights** record licensing/permission state;
- **interpretation** occurs downstream of evidence acquisition.

## Domain capabilities currently represented

### Core and ontology

Stable identity, deterministic hashing, quantities, time windows, geodetic primitives, epistemic states, entity resolution, relationships, events, capabilities, services, flows, assertions, world-model aggregation, snapshots, and contract versioning.

### Evidence and provenance

Content-addressed evidence, acquisition metadata, selectors, normalization lineage, provenance graphs, quality measurements, rights metadata, and evidence registries.

### Temporal and spatial

UTC-normalized temporal intervals, half-open validity semantics, Allen relations, bitemporal coordinates, temporal snapshots and indexing, WGS-84 geodesy, GeoJSON/JSON-FG boundaries, coordinate reference handling, and spatial query/operation primitives.

### Graph and propagation

Typed directed property-graph structures, temporal graph queries, deterministic traversal and path algorithms, connectivity measures, max-flow/min-cut behavior, and bounded time-respecting propagation of explicit shocks.

### Scenarios, continuity, counterfactuals, uncertainty

Deterministic scenario patches and branches, intervention modeling, continuity/recovery/substitution logic, explicit modeled counterfactual comparison, uncertainty distributions/sampling/calibration/sensitivity helpers, and provenance-preserving results.

### Economics, intelligence, optimization, governance

Economic accounts/flows/trade and scenario impact modeling; deterministic anomaly/forecast/fusion/explanation primitives; intervention portfolio selection and robustness criteria; governance and assurance controls for evidence/provenance/epistemic constraints.

### Sources, storage, orchestration, API/output/CLI

Source adapters for Earth/geospatial, economy, infrastructure, repository-security observations, and space/CCSDS/RINEX/GNSS/space-weather inputs; local SQLite and evidence/provenance storage; deterministic orchestration; FastAPI routes as an optional API layer; deterministic JSON/table/GeoJSON/JSON-FG/report outputs; and a Python CLI.

## Data and standards boundaries

QEDTY intentionally uses established standards where they solve a natural interoperability problem:

- OGC GeoJSON / JSON-FG / API Features for geospatial exchange;
- CCSDS/IGS/RINEX-oriented boundaries for space-source ingestion;
- W3C PROV, DCAT, DQV, Web Annotation, OWL, SHACL, SSN/SOSA, and SKOS at semantic/provenance boundaries;
- Apache Arrow / Parquet for columnar data movement and analytics;
- Protobuf for typed service boundaries;
- OpenAPI 3.1.1 for HTTP API description;
- SQL/PGQ and PostgreSQL/PostGIS as future/adapter-level database interoperability targets rather than current semantic authorities.

Mapping to a standard is not a claim of complete conformance to every feature of that standard. QEDTY documents its bounded profiles explicitly.

## Verification status

The latest completed local verification of this repository reported:

- **Python tests:** 203 passed, 1 skipped
- **Coverage:** 66.08%
- **Contract verification:** `status: ok`
- **World graph schema:** `qedty-world-graph@1.0.0`
- **API contract:** `1.0.0`
- **Modeled demonstration:** successful
- **Rust golden tests:** 3 passed
- **Rust unit/doc tests:** no failures
- **Dependency lock check:** passed

The skipped Python test intentionally exercises the missing-PyArrow condition while PyArrow is installed in the active verification environment.

Coverage is an engineering signal, not a claim of semantic completeness or production readiness.

## Quick start

### Requirements

- Python `>=3.12,<3.14`
- `uv` compatible with the repository's `tool.uv.required-version`
- Rust toolchain for the native core

### Install

```bash
git clone https://github.com/shan-005/QEDTY.git
cd QEDTY
uv sync
source .venv/bin/activate
```

### Validate the reference implementation

```bash
python -m qedty validate
python -m qedty demo
```

### Run the full repository verification gate

```bash
chmod +x scripts/verify.sh
./scripts/verify.sh
```

### Test the Rust core

```bash
cargo test --manifest-path crates/qedty-core/Cargo.toml
```

### Inspect the CLI

```bash
qedty --help
qedty --version
qedty validate
qedty demo
```

## Repository map

| Path | Purpose |
|---|---|
| `src/qedty/` | Python semantic/reference/application implementation |
| `crates/qedty-core/` | Shipped Rust native core |
| `contracts/` | Machine-readable semantic and interface contracts |
| `data/contracts/golden-vectors/` | Cross-implementation expected-value fixtures |
| `proto/qedty/` | Protobuf service/domain definitions |
| `tests/` | Unit, integration, contract, and conformance tests |
| `scripts/` | Verification, conformance, and vector tooling |
| `docs/` | Architecture, research baselines, algorithms, standards boundaries, operations, and release guidance |
| `policies/` | Repository and domain control policies |
| `.github/` | CI, release, dependency, signing, and collaboration automation |
| `pyproject.toml` | Python package, optional dependencies, development groups, and tool configuration |
| `uv.lock` | Locked Python dependency resolution |
| `Cargo.lock` | Locked Rust dependency resolution |

## Contract/version discipline

A semantic change should normally update all affected surfaces together:

1. canonical contract/schema;
2. golden vectors;
3. Python reference implementation;
4. conformance/integration tests;
5. interoperability representation where affected;
6. documentation and migration notes;
7. release verification.

Do not silently change the meaning of existing IDs, epistemic states, temporal intervals, spatial reference behavior, quantities, propagation rules, or output fields.

## Development checks

Before submitting changes, run at minimum:

```bash
uv run pytest -q
uv run ruff check src tests
uv run ruff format --check src tests
uv run mypy src
uv run qedty validate
```

For the repository-level gate:

```bash
./scripts/verify.sh
cargo test --manifest-path crates/qedty-core/Cargo.toml
uv lock --check
```

## Alpha-stage boundaries and non-claims

QEDTY is a serious engineering and research platform, but this alpha release is not a certification.

The project does **not** claim, merely from the existence of these modules or mappings:

- production-critical operational certification;
- authoritative forecasts of the physical world;
- causal identification from graph propagation alone;
- complete ontology, RDF, SHACL, PROV, SPDX, OGC, CCSDS, or database conformance;
- universal entity-resolution accuracy;
- calibrated probabilities from arbitrary confidence scores;
- global optimality when a deterministic greedy optimization fallback is used;
- performance at planetary scale before representative large-scale benchmarks have been executed;
- complete Go, C++/CUDA, TypeScript/React, SQL-service, or WASM implementations.

Model outputs must be interpreted with their evidence, assumptions, uncertainty, provenance, contract version, and model version.

## Documentation map

Start with:

- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)
- [`docs/RESEARCH_BASELINE.md`](docs/RESEARCH_BASELINE.md)
- [`docs/PROVENANCE.md`](docs/PROVENANCE.md)
- [`docs/DATA_SOURCES.md`](docs/DATA_SOURCES.md)
- [`docs/OPERATIONS.md`](docs/OPERATIONS.md)
- [`docs/RELEASE_READINESS.md`](docs/RELEASE_READINESS.md)
- [`docs/GEOSPATIAL.md`](docs/GEOSPATIAL.md)
- [`docs/ECONOMICS.md`](docs/ECONOMICS.md)
- [`docs/SPACE.md`](docs/SPACE.md)
- [`docs/ontology/README.md`](docs/ontology/README.md)
- [`docs/evidence/README.md`](docs/evidence/README.md)
- [`docs/temporal/README.md`](docs/temporal/README.md)
- [`docs/scenarios/README.md`](docs/scenarios/README.md)
- [`docs/propagation/README.md`](docs/propagation/README.md)

The domain documentation under `docs/` mirrors the semantic and execution layers and records explicit research baselines, algorithm contracts, limitations, and interoperability decisions.

## Security, contribution, support

- [`SECURITY.md`](SECURITY.md) — vulnerability reporting and security boundaries
- [`CONTRIBUTING.md`](CONTRIBUTING.md) — development and semantic-contract contribution rules
- [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md) — community standards
- [`SUPPORT.md`](SUPPORT.md) — reproducibility and support requirements

## Citation and license

Citation metadata is provided in [`CITATION.cff`](CITATION.cff).

QEDTY is licensed under the Apache License 2.0. See [`LICENSE`](LICENSE).

## Packaging note

The semantic product version is defined by `src/qedty/core/version.py` as `0.1a0`. The file `src/qedty/_version.py` is generated by `setuptools-scm`; it should be regenerated by the package tooling rather than treated as an independent semantic version source.

## Final engineering position

The repository currently provides a substantial Python semantic/reference and application foundation plus a deterministic Rust native core, contract surfaces, conformance vectors, tests, source adapters, storage, orchestration, API/output/CLI layers, and governance/documentation controls.

The next polyglot layers are architectural targets, not claims about code that is already present. The contract surface is the stable center: **future implementations must conform to QEDTY semantics rather than become competing semantic authorities.**
