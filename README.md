# QEDTY

**QEDTY — evidence-backed planetary continuity intelligence**

QEDTY is a contract-driven platform for representing, querying, propagating, evaluating, and governing evidence-backed models of planetary systems and their continuity under disruption.

The project is designed as a serious, polyglot systems platform rather than a collection of independent analytics scripts. Its semantic model, evidence model, temporal and spatial semantics, graph structure, scenario semantics, propagation rules, uncertainty treatment, economic modeling, intelligence, optimization, governance, provenance, and outputs are governed by explicit contracts and conformance vectors.

> **Current release line:** `0.1a0`  
> **License:** Apache-2.0  
> **Status:** active alpha / engineering development

## What QEDTY is for

QEDTY is intended to answer questions of the form:

- What exists, where is it, and over what valid time interval?
- What evidence supports a claim, observation, relationship, or model input?
- What dependencies connect one capability or service to another?
- What happens when capacity, availability, or another system attribute changes?
- How does an intervention propagate through a dependency graph?
- What is the continuity effect of an intervention or counterfactual?
- What uncertainty attaches to the result, and where does it enter the computation?
- What economic flows, costs, or exposures accompany the modeled outcome?
- Which claims are observed, derived, inferred, modeled, counterfactual, or unknown?
- What provenance and governance constraints must accompany the result?

QEDTY therefore treats a model result as an evidence-bearing, provenance-preserving object rather than as an unexplained scalar.

## Design principles

### Contract first

Stable semantics are expressed through versioned contracts, JSON Schema, Arrow representations, RDF/SHACL where appropriate, Protobuf service definitions, and golden vectors.

The contracts are not documentation-only artifacts. They are part of the interoperability and conformance surface.

### One semantic model, multiple execution layers

QEDTY deliberately separates semantic authority from execution technology:

| Layer | Primary responsibility |
|---|---|
| Python | semantic/reference implementation, application layer, intelligence, orchestration |
| Rust | deterministic high-performance native computation |
| C++ / CUDA | selective specialized native/GPU acceleration where justified |
| Go | operational, edge, agent, and service workloads |
| TypeScript / React | web console, visualization, and operator interfaces |
| SQL | authoritative relational/spatiotemporal querying |
| Arrow / Parquet | high-throughput data interchange and analytical data plane |
| Protobuf / gRPC | typed cross-language service boundary |
| WIT / WASM | portable execution/component boundary |

These layers are implementations of a shared contract surface, not competing copies of the domain model.

### Evidence and provenance by construction

QEDTY is built around the distinction between observation, derivation, inference, modeling, and counterfactual reasoning. Provenance is intended to survive movement across storage, language, service, and analytical boundaries.

### Determinism where semantics require it

Canonicalization, identity, quantities, time, geometry, graph semantics, scenario transformations, and other contract-critical behavior are defined so independent implementations can be compared against the same expected results.

### Mature standards over reinvention

QEDTY integrates established standards and mature ecosystems at their natural boundaries: geospatial systems, relational/spatiotemporal databases, Arrow/Parquet, Protobuf/gRPC, provenance vocabularies, CCSDS/OGC-aligned interfaces, and standard software supply-chain controls.

## Architecture

The repository is organized into three major strata:

1. **Semantic and contract surface** — `src/qedty`, `contracts`, `data/contracts/golden-vectors`, `proto`
2. **Execution and systems surface** — `crates`, storage/query infrastructure, and future native/edge/runtime components
3. **Verification and governance surface** — `tests`, `scripts`, `policies`, `.github`, and engineering documentation

The current Python implementation contains the established domain layers:

- core
- ontology
- evidence
- temporal
- spatial
- graph
- scenarios
- propagation
- continuity
- economics
- counterfactual
- uncertainty
- intelligence
- optimization
- governance
- sources
- storage
- orchestration
- API / output / CLI

The project roadmap extends the same contract surface into additional native, service, analytical, edge, web, and WASM execution environments without duplicating semantic authority.

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for the repository-level architecture and [`docs/ALGORITHM_CONTRACT.md`](docs/ALGORITHM_CONTRACT.md) for algorithmic contract principles.

## Verification status

The latest local verification reported:

- Python test suite: **203 passed, 1 skipped**
- coverage: **66.08%**
- contract verification: **status `ok`**
- world graph schema: **`qedty-world-graph@1.0.0`**
- API contract: **`1.0.0`**
- modeled demonstration: successful
- verification entry point: [`scripts/verify.sh`](scripts/verify.sh)

The single skipped test is an intentional test for behavior when PyArrow is absent; PyArrow is installed in the active environment.

Coverage is reported for engineering visibility and is not presented as a proxy for semantic completeness or production readiness.

## Quick start

### Requirements

- Python `>=3.12,<3.15`
- `uv`
- a working Rust toolchain for the native core

### Environment

```bash
git clone <repository-url>
cd qedty

uv sync
source .venv/bin/activate
```

### Validate the installation

```bash
python -m qedty validate
python -m qedty demo
```

### Run the repository verification gate

```bash
chmod +x scripts/verify.sh
./scripts/verify.sh
```

The verification script performs Python compilation, the test suite, validation, and the modeled demonstration.

### Rust core

```bash
cargo test --manifest-path crates/qedty-core/Cargo.toml
```

The Rust crate is tested against the shared golden-vector surface where applicable.

## Repository map

| Path | Role |
|---|---|
| `src/qedty/` | Python semantic/reference/application implementation |
| `crates/qedty-core/` | Rust native core |
| `contracts/` | machine-readable semantic/interface contracts |
| `data/contracts/golden-vectors/` | cross-implementation expected-value vectors |
| `proto/qedty/` | Protobuf service/message definitions |
| `tests/` | unit, integration, contract, and conformance tests |
| `scripts/` | verification, conformance, and vector tooling |
| `docs/` | architecture, algorithms, research baselines, operations, and domain documentation |
| `policies/` | repository and domain policy controls |
| `.github/` | CI, release, security, and collaboration automation |

## Contract and version discipline

Contract versions are part of QEDTY's compatibility surface.

Changes that alter externally meaningful semantics should normally:

1. update the relevant contract;
2. update or add golden vectors;
3. update the reference implementation;
4. update conformance tests;
5. document compatibility and migration implications;
6. verify downstream interfaces before release.

Avoid silently changing the meaning of existing fields, identifiers, temporal semantics, spatial reference behavior, epistemic states, propagation rules, or output schemas.

## What QEDTY does not claim

QEDTY is an engineering platform for evidence-backed modeling and decision support. A model output is not automatically a fact about the physical world.

The system distinguishes evidence-backed observation from derivation, inference, model output, and counterfactual analysis. Results should therefore be interpreted with their evidence, assumptions, uncertainty, model version, and provenance.

The alpha release line should not be treated as a production-critical certification, operational guarantee, or authoritative forecast without independent domain validation and deployment-specific controls.

## Documentation

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

Domain-specific documentation is organized beneath `docs/` and mirrors the implementation/contract domains.

## Security

Security-sensitive reports must not be opened as public issues.

See [`SECURITY.md`](SECURITY.md) for the supported release line, disclosure process, security boundaries, and handling expectations.

## Contributing

QEDTY is contract-driven and verification-heavy. Contributions are expected to preserve semantic stability, provenance, deterministic behavior where specified, and cross-layer interoperability.

See [`CONTRIBUTING.md`](CONTRIBUTING.md) before submitting changes.

## Code of conduct

Participation in the project is governed by [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md).

## Support

See [`SUPPORT.md`](SUPPORT.md) for support channels, issue quality requirements, reproducibility expectations, and escalation guidance.

## Citation

The repository contains [`CITATION.cff`](CITATION.cff) for machine-readable citation metadata.

## License

QEDTY is distributed under the Apache License, Version 2.0. See [`LICENSE`](LICENSE).

---

### Engineering maturity statement

QEDTY has a substantial semantic, contract, evidence, temporal, spatial, graph, scenario, propagation, continuity, economic, counterfactual, uncertainty, intelligence, optimization, governance, source, storage, orchestration, and API/output/CLI foundation.

The project is nevertheless an **alpha engineering system**. Future native, distributed, analytical, edge, web, and accelerator layers must conform to the existing semantic and contract surface rather than silently replacing it.

