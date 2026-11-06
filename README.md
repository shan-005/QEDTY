# QEDTY

**Evidence-backed planetary continuity intelligence: model how disruptions move through connected systems, while keeping evidence, assumptions and uncertainty inspectable.**

QEDTY is a contract-driven platform for representing, querying, propagating, evaluating and governing evidence-backed models of interconnected planetary systems and their continuity under disruption.

[![License](https://img.shields.io/badge/license-Apache--2.0-blue)](LICENSE)
![Status](https://img.shields.io/badge/status-alpha-orange)
![Version](https://img.shields.io/badge/version-0.1a0-lightgrey)
[![QEDTY CI](https://github.com/shan-005/QEDTY/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/shan-005/QEDTY/actions/workflows/ci.yml)

> **Status: active alpha (`0.1a0`).** Python is the semantic/reference implementation, Rust provides a deterministic native core, and Protobuf, JSON Schema, RDF/SHACL and Arrow are the contract and interoperability surfaces. APIs and contracts may change. See [Alpha boundaries](#alpha-boundaries-and-non-claims).

```
Satellite ──► GNSS service ──► Telecom network ──► Payment system ──► Digital service
          0.95            0.90               0.80                0.85
        a disruption enters here and propagates downstream, with every step traceable to its evidence
```

---

## Contents

- [Why QEDTY](#why-qedty)
- [See it work](#see-it-work)
- [Who it's for](#who-its-for)
- [Quick start](#quick-start)
- [What works today](#what-works-today)
- [In progress and known gaps](#in-progress-and-known-gaps)
- [Architecture](#architecture)
- [Contract-first design](#contract-first-design)
- [Epistemic and provenance model](#epistemic-and-provenance-model)
- [Capabilities](#capabilities)
- [Data and standards boundaries](#data-and-standards-boundaries)
- [Verification](#verification)
- [Repository map](#repository-map)
- [Contract and version discipline](#contract-and-version-discipline)
- [Development](#development)
- [Alpha boundaries and non-claims](#alpha-boundaries-and-non-claims)
- [Roadmap](#roadmap)
- [FAQ](#faq)
- [Engineering evidence](#engineering-evidence)
- [Project feedback](#project-feedback)
- [Cite and license](#cite-and-license)
- [Manifest notes](#manifest-notes)

---

---

## Why QEDTY

Most analysis tools return a number. QEDTY returns a number **together with its sources, assumptions and uncertainty**.

- **Evidence-linked.** Records carry provenance and SHA-256 content-addressed identities.
- **Honest about certainty.** Statements are labeled `observed`, `derived`, `inferred`, `modeled`, `counterfactual` or `unknown`. A model output is never relabeled as an observation.
- **Deterministic and verifiable.** A Rust native core is checked against the Python reference using shared golden vectors.
- **Contract-first.** JSON Schema, Protobuf, RDF/SHACL, JSON-LD and Arrow contracts define behavior across implementations.
- **Time- and space-aware.** Validity intervals, bitemporal coordinates and WGS-84 geodesy are built in.

QEDTY is designed to answer questions such as:

- What entities, capabilities, services, relationships and flows exist, and where?
- During which validity intervals do they apply?
- What evidence and provenance support a record or claim?
- Which dependencies connect capabilities and services?
- How does an explicit shock or intervention propagate through a dependency graph?
- What is the modeled continuity effect of an intervention or counterfactual?
- What uncertainty attaches to a result, and where does it enter the computation?
- What economic exposure accompanies a scenario?

Important results are treated as **evidence-bearing, provenance-preserving objects**, not unexplained scalar values.

## See it work

```bash
uv sync
uv run qedty validate
uv run qedty demo
```

The built-in demo models a **disruption to satellite navigation and timing and how it cascades through a dependency chain**:

```
Satellite ──► GNSS service ──► Telecom network ──► Payment system ──► Digital service
 (observed)     (derived)          (derived)           (derived)          (derived)
          0.95            0.90               0.80                0.85      ← dependency strengths
```

The five nodes correspond to these entities in the demo model:

| Node name | Entity type | Role in the scenario | Epistemic status |
|---|---|---|---|
| `Sat` | `SATELLITE` | Origin of the simulated GNSS disruption | `observed` |
| `Pnt` | `GNSS_SERVICE` | Navigation and timing service downstream of the satellite | `derived` |
| `Telecom` | `TELECOM_NETWORK` | Network relying on the GNSS service | `derived` |
| `Payments` | `PAYMENT_SYSTEM` | Payment service relying on telecom connectivity | `derived` |
| `Digital` | `SERVICE` | Final service whose continuity is evaluated | `derived` |

Each consecutive pair is joined by a directed `SUPPORTS` relationship. The four relationship strengths are 0.95, 0.90, 0.80 and 0.85. The node definitions and graph are in [`src/qedty/cli/scenario.py`](src/qedty/cli/scenario.py).

A simulated GNSS degradation (severity 0.6) propagates down the chain. QEDTY then compares the final service's capacity **with and without** a $1M "backup timing" intervention.

`qedty validate` confirms the contract surface is consistent:

```json
{
  "api_contract": "1.0.0",
  "epistemic_states": ["observed", "derived", "inferred", "modeled", "counterfactual", "unknown"],
  "output_formats": ["json", "geojson", "json-fg", "csv", "markdown"],
  "product_version": "0.1a0",
  "status": "ok",
  "world_graph_schema": "qedty-world-graph@1.0.0"
}
```

`qedty demo` runs the modeled scenario:

```json
{
  "baseline_capacity": 0.65116,
  "continuity_gain": 0.17442,
  "counterfactual_capacity": 0.82558,
  "intervention_cost_usd": 1000000.0,
  "nodes": 5,
  "path_hops": 4,
  "product": "QEDTY",
  "relationships": 4,
  "status": "modeled_demo"
}
```

| Result | Value | Meaning |
|---|---|---|
| `baseline_capacity` | 65.1% | Digital service capacity after the disruption, no intervention |
| `counterfactual_capacity` | 82.6% | Capacity if backup timing protects the final service |
| `continuity_gain` | +17.4 pp | Modeled benefit of the intervention |
| `intervention_cost_usd` | $1,000,000 | Assumed cost |

**The question it answers:** if satellite timing degrades by 60%, how much of a downstream digital service survives, and what does a $1M backup buy?

**Worked check:** the severity and the four dependency strengths multiply to 0.6 × 0.95 × 0.90 × 0.80 × 0.85 = 0.34884, a modeled loss of 34.9%, so baseline capacity is 1 − 0.34884 = 0.65116. The intervention halves that loss, giving 0.17442 and a counterfactual capacity of 0.82558.

**Reading the labels:** the output is marked `modeled_demo`, so it is a **modeled** result, never an observation. This is a deterministic, synthetic demonstration of the engine, not a forecast of any real system and not a measurement of real connected infrastructure.

## Who it's for

- **Researchers** modeling infrastructure dependencies and resilience.
- **Developers** who need reproducible, provenance-tracked graph and geospatial computation.
- **Analysts** who must show where a result came from and how sure it is.

## Quick start

**Requirements:** Python `>=3.12,<3.14`, [`uv`](https://docs.astral.sh/uv/) compatible with the repository's `tool.uv.required-version`, and a Rust toolchain (for the native core).

```bash
git clone https://github.com/shan-005/QEDTY.git
cd QEDTY
uv sync
uv run qedty validate   # check the contract surface
uv run qedty demo       # run the modeled demo
```

Inspect the CLI:

```bash
uv run qedty --help
uv run qedty --version
```

Run the full verification gate and the Rust core tests:

```bash
./scripts/verify.sh
cargo test --manifest-path crates/qedty-core/Cargo.toml
```

## What works today

| Technology | Status | What is present now |
|---|---|---|
| **Python** | Implemented | Semantic/reference and application layers, tests, conformance tooling, scripts |
| **Rust** | Implemented | `crates/qedty-core/` deterministic native core, golden-vector tests, workspace, and `rust/` conformance tooling |
| **Protobuf** | Implemented as contract source | Typed `.proto` definitions under `proto/qedty/` |
| **JSON Schema** | Implemented as contracts | Semantic and interface schemas under `contracts/` and packaged schemas |
| **RDF / Turtle / JSON-LD / SHACL** | Implemented as interoperability boundaries | Artifacts under `contracts/` |
| **Apache Arrow** | Implemented as data-plane contract | Arrow-oriented contract artifacts; optional Python Arrow/Parquet support |
| **SQL / SQLite** | Reference capability in Python | SQLite reference backend and database adapters; no standalone `.sql` files |
| **Go** | Not in this repository | Future operational/edge/service target |
| **C / C++ / CUDA** | Not in this repository | Future selective native/GPU acceleration |
| **TypeScript / React** | Not in this repository | Future web console target |
| **WIT / WASM** | Not in this repository | Future portable component boundary |

Future languages must **conform to the existing contracts** rather than silently redefine domain meaning. Roadmap targets are not current implementations; implementation status is determined by the source tree and the bounded conformance evidence.

## In progress and known gaps

QEDTY has accepted several **bounded, explicitly versioned** Python–Rust contracts. That acceptance must not be confused with full-domain parity.

| Workstream | Current disposition | Boundary |
|---|---|---|
| Currency-neutral money and portfolio v2.0/v2.1 | **Accepted bounded scope** | Named currency-conversion and portfolio contracts, including the tested FX-path and resilience-gain behavior. This is not full parity for every optimizer domain or live FX ingestion. |
| Full time-aware propagation | **Not complete** | Bounded impairment aggregation is tested; time-respecting graph propagation with delays, temporal edge validity and full arrival semantics is not accepted as cross-language parity. |
| Full uncertainty semantics | **Not complete** | The scalar weighted-mean kernel is covered; distribution models, sampling, calibration and uncertainty propagation are not established as fully equivalent. |
| Broader spatial and CRS semantics | **Not complete** | Selected WGS-84, distance and spatial-query operations are covered; arbitrary CRS transforms and the full spatial domain are not. |

The operation-level evidence and exclusions are recorded in the [cross-language conformance matrix](docs/engineering/CROSS_LANGUAGE_CONFORMANCE_MATRIX.csv). Expand a domain only with a named contract, boundary/error fixtures, independent expected values, differential tests and passing hosted CI.

## Architecture

QEDTY is structured around one shared semantic and contract surface.

```
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

### Python layers (implemented)

`core` · `ontology` · `evidence` · `temporal` · `spatial` · `graph` · `scenarios` · `propagation` · `continuity` · `economics` · `counterfactual` · `uncertainty` · `intelligence` · `optimization` · `governance` · `sources` · `storage` · `orchestration` · API / output / CLI

### Rust native core (implemented)

`crates/qedty-core/` provides:

- deterministic identity and canonicalization;
- checked geometry helpers;
- quantity and contract-result primitives;
- timestamp, interval and Allen-relation primitives;
- a bounded spatial point-grid index;
- in-memory directed-graph algorithms;
- small numeric and columnar adapter kernels.

Shared fixtures and the conformance CLI validate selected behaviors. The Rust graph and spatial APIs are **narrower** than the Python world-graph and geospatial layers, and the columnar module is **not** Arrow IPC or the Arrow C Data Interface. Rust is **not** a duplicate of the whole Python domain model, and no domain should be described as fully ported without a scope-specific conformance matrix.

### Future execution targets (not in this repository)

```
Go                 -> operational / edge / agent services
C++ / CUDA         -> selective specialized native/GPU acceleration
TypeScript / React -> web console / visualization / operator UI
SQL / PostgreSQL   -> production relational + spatiotemporal persistence
WIT / WASM         -> portable component/execution boundary
```

These targets are roadmap architecture. Each must conform to the same contracts, identifiers, temporal and spatial semantics, epistemic states, evidence and provenance rules, and golden vectors.

## Contract-first design

Contracts are executable interoperability surfaces, not documentation-only descriptions.

- **JSON Schema (Draft 2020-12)** for machine-readable document validation
- **Protobuf** for typed service and control boundaries
- **Apache Arrow** for columnar data interchange
- **RDF / OWL / JSON-LD** for semantic-web interoperability
- **SHACL** for bounded RDF graph validation
- **Golden vectors** (`data/contracts/golden-vectors/`) as normative expected-value fixtures
- **SHA-256 content-addressed identities** for evidence and provenance integrity

Contract directories under `contracts/` are accompanied by tests and conformance tooling.

## Epistemic and provenance model

QEDTY distinguishes these states, which are **not interchangeable**:

```
observed → derived → inferred → modeled → counterfactual → unknown
```

A model output is not relabeled as an observation merely because software produced it.

Evidence and provenance are separate concerns:

- **Integrity:** the captured representation matches its digest.
- **Provenance:** how and why the representation entered the pipeline.
- **Quality:** explicit measurements and methods.
- **Rights:** licensing and permission state.
- **Interpretation:** happens downstream of evidence acquisition.

## Capabilities

**Core and ontology.** Stable identity, deterministic hashing, quantities, time windows, geodetic primitives, epistemic states, entity resolution, relationships, events, capabilities, services, flows, assertions, world-model aggregation, snapshots, contract versioning.

**Evidence and provenance.** Content-addressed evidence, acquisition metadata, selectors, normalization lineage, provenance graphs, quality measurements, rights metadata, evidence registries.

**Temporal and spatial.** UTC-normalized intervals, half-open validity semantics, Allen relations, bitemporal coordinates, temporal snapshots and indexing, WGS-84 geodesy, GeoJSON / JSON-FG boundaries, coordinate reference handling, spatial query and operation primitives.

**Graph and propagation.** Typed directed property graphs, temporal graph queries, deterministic traversal and path algorithms, connectivity measures, max-flow / min-cut, and bounded time-respecting propagation of explicit shocks.

**Scenarios, continuity, counterfactuals, uncertainty.** Deterministic scenario patches and branches, intervention modeling, continuity / recovery / substitution logic, explicit modeled counterfactual comparison, uncertainty distributions, sampling, calibration and sensitivity helpers, provenance-preserving results.

**Economics, intelligence, optimization, governance.** Economic accounts, flows, trade and scenario impact modeling; deterministic anomaly, forecast, fusion and explanation primitives; intervention portfolio selection and robustness criteria; governance and assurance controls for evidence, provenance and epistemic constraints.

**Sources, storage, orchestration, interfaces.** Source adapters for Earth/geospatial, economy, infrastructure, repository-security observations, and space (CCSDS, RINEX, GNSS, space-weather) inputs; local SQLite and evidence/provenance storage; deterministic orchestration; optional FastAPI routes; deterministic JSON, table, GeoJSON, JSON-FG and report outputs; a Python CLI.

## Data and standards boundaries

QEDTY uses established standards where they solve a natural interoperability problem:

- OGC GeoJSON, JSON-FG and API Features for geospatial exchange
- CCSDS / IGS / RINEX-oriented boundaries for space-source ingestion
- W3C PROV, DCAT, DQV, Web Annotation, OWL, SHACL, SSN/SOSA and SKOS at semantic and provenance boundaries
- Apache Arrow and Parquet for columnar data movement and analytics
- Protobuf for typed service boundaries
- OpenAPI 3.1.1 for HTTP API description
- SQL/PGQ and PostgreSQL/PostGIS as future, adapter-level targets (not current semantic authorities)

Mapping to a standard is **not** a claim of complete conformance to every feature of that standard. QEDTY documents its bounded profiles explicitly.

## Verification

The [QEDTY CI workflow](.github/workflows/ci.yml) is the primary Python, native Rust and packaging gate. Its badge reports the current `main` branch result:

[![QEDTY CI](https://github.com/shan-005/QEDTY/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/shan-005/QEDTY/actions/workflows/ci.yml)

Other repository workflows are available directly: [Rust](.github/workflows/rust.yml), [Python–Rust Differential](.github/workflows/python-rust-differential.yml), [Platform Smoke](.github/workflows/qedty.yml), [Dependency Review](.github/workflows/dependency-review.yml), and [Release](.github/workflows/release.yml).

The primary CI gate covers:

- **Python 3.12 and 3.13:** tests and coverage, Ruff lint and format, mypy, dependency audit, Bandit, CLI validation, manifest and naming checks, demo commands and executable conformance scripts.
- **Rust workspace:** formatting, locked workspace tests, Clippy with warnings denied, golden-vector conformance, expanded graph/spatial conformance and the native-crate compatibility test.
- **Packaging:** locked dependency resolution, distribution build and metadata validation.

The Rust conformance implementations are visible in [the core golden-vector runner](rust/crates/qedty-conformance/src/main.rs), [the Python–Rust differential runner](rust/crates/qedty-conformance/src/bin/qedty-differential.rs) and [the Rust core crate](crates/qedty-core/). Operation-level scope and exclusions are recorded in the [cross-language conformance matrix](docs/engineering/CROSS_LANGUAGE_CONFORMANCE_MATRIX.csv).

These checks establish **only the behavior covered by their fixtures**. They are not exhaustive Python–Rust differential coverage or a complete Rust port. Coverage is an engineering signal, not proof of semantic completeness or production readiness. For the latest result on a commit, use the linked Actions workflow rather than a static test count.

## Repository map

| Path | Purpose |
|---|---|
| [`src/qedty/`](src/qedty/) | Python semantic/reference and application implementation |
| [`crates/qedty-core/`](crates/qedty-core/) | Rust deterministic native core |
| [`rust/crates/qedty-conformance/`](rust/crates/qedty-conformance/) | Rust golden-vector and differential conformance tooling |
| [`contracts/`](contracts/) | Machine-readable semantic and interface contracts |
| [`data/contracts/golden-vectors/`](data/contracts/golden-vectors/) | Cross-implementation expected-value fixtures |
| [`data/contracts/differential/cases/`](data/contracts/differential/cases/) | Fixed cross-language differential cases |
| [`proto/qedty/`](proto/qedty/) | Protobuf service and domain definitions |
| [`tests/`](tests/) | Unit, integration, contract and conformance tests |
| [`scripts/`](scripts/) | Verification, conformance and vector tooling |
| [`docs/engineering/CROSS_LANGUAGE_CONFORMANCE_MATRIX.csv`](docs/engineering/CROSS_LANGUAGE_CONFORMANCE_MATRIX.csv) | Bounded Python–Rust operation matrix and explicit scope limits |
| [`policies/`](policies/) | Repository and domain control policies |
| [`.github/workflows/`](.github/workflows/) | CI, release, dependency and platform workflows |
| `pyproject.toml`, `uv.lock`, `Cargo.lock` | Package configuration and locked dependency resolution |

## Contract and version discipline

A semantic change should normally update all affected surfaces together:

1. canonical contract/schema
2. golden vectors
3. Python reference implementation
4. conformance and integration tests
5. interoperability representations, where affected
6. documentation and migration notes
7. release verification

Do not silently change the meaning of existing IDs, epistemic states, temporal intervals, spatial reference behavior, quantities, propagation rules or output fields.

## Development

Before submitting changes, run at minimum:

```bash
uv run pytest -q --cov-fail-under=60
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

## Alpha boundaries and non-claims

QEDTY is a serious engineering and research platform, but this alpha is **not a certification**. It does **not** claim, merely from the existence of modules or mappings:

- production-critical operational certification;
- authoritative forecasts of the physical world;
- causal identification from graph propagation alone;
- complete ontology, RDF, SHACL, PROV, SPDX, OGC, CCSDS or database conformance;
- universal entity-resolution accuracy;
- calibrated probabilities from arbitrary confidence scores;
- global optimality when a deterministic greedy optimization fallback is used;
- performance at planetary scale before representative large-scale benchmarks are run;
- complete Go, C++/CUDA, TypeScript/React, SQL-service or WASM implementations.

Interpret model outputs together with their evidence, assumptions, uncertainty, provenance, contract version and model version.

## Roadmap

Engineering work is organized by maintainers into sequential milestones. These describe the delivery process only; they are **not** product features, architecture layers, release names or public API concepts. The bounded currency/portfolio v2.0/v2.1 scope has been accepted; broader optimizer-domain parity remains outside that acceptance.

- **Completed:** Rust Core Conformance and Kernel Expansion.
- **Completed:** Systematic Python–Rust Differential Testing.
- **Current:** Cross-Language Conformance Expansion, focused on extending explicit contracts without overstating the accepted bounded slices.
- **Planned direction (not commitments):** richer data ingestion and quality gates; deeper temporal, geospatial and graph analytics; uncertainty and evidence modeling; domain applications; performance and observability; operational services; APIs and a web console; security and governance; end-to-end validation; production readiness.

Python remains the semantic and reference authority. Rust must conform to approved Python behavior and the language-neutral contracts, and must not become a second semantic authority. Supported status is defined by source, tests, CI evidence and the current manifest, not by a roadmap heading.

## FAQ

**Is QEDTY a forecasting tool?**
No. It models how explicit shocks propagate through a dependency graph and labels results as modeled, not observed. It does not claim authoritative forecasts of the physical world.

**Does the demo use real data?**
No. `qedty demo` is a deterministic, synthetic scenario that illustrates the approach. It does not measure real infrastructure.

**Can I use it in production?**
Not yet. This is an alpha without operational certification, and contracts may change.

**Where does the data come from?**
Through the Python source-adapter layer under [`src/qedty/sources/`](src/qedty/sources/). Respect each provider's license, access policy and terms.

**Why both Python and Rust?**
Python defines the meaning and is the reference. Rust provides a deterministic native core that must agree with Python on shared golden vectors.

**When will Go, TypeScript/React or WASM arrive?**
They are future targets with no source in this repository yet. See the [Roadmap](#roadmap).

## Engineering evidence

The root README is the public project guide. The [cross-language conformance matrix](docs/engineering/CROSS_LANGUAGE_CONFORMANCE_MATRIX.csv) is the machine-readable record of bounded operation coverage, evidence levels and scope exclusions. Implementation details are maintained alongside the source, contracts, tests and workflow definitions.

## Project feedback

Use [GitHub Issues](https://github.com/shan-005/QEDTY/issues) for reproducible bug reports and scoped technical proposals. Include the command, environment and minimal reproduction where possible. Do not post credentials, private data or sensitive vulnerability details in a public issue.

## Cite and license

Citation metadata is in [`CITATION.cff`](CITATION.cff). QEDTY is licensed under the [Apache License 2.0](LICENSE).

## Manifest notes

- [`QEDTY-PROJECT-MANIFEST.json`](QEDTY-PROJECT-MANIFEST.json) records the tracked path inventory, extension counts and root-directory counts. CI compares it with `git ls-files`; a stale entry fails the gate. Do not copy inventory counts into this README because they change.
- [`scripts/update_manifest_inventory.py`](scripts/update_manifest_inventory.py) regenerates the inventory for the explicitly maintained conformance bundle paths. Its path list must refer only to files that exist in the repository.
- [`FILE_INDEX.json`](FILE_INDEX.json) indexes the original Rust research/scaffold archive. Its byte lengths and SHA-256 values describe that archive's payload, **not** the live contents of every path.
- The semantic product version is defined in [`src/qedty/core/version.py`](src/qedty/core/version.py) (`0.1a0`). `src/qedty/_version.py` is generated by `setuptools-scm` and is not an independent version source.
