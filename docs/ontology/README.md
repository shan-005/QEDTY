# QEDTY Ontology v2.0.0

This package is the contract-first semantic reference implementation for `src/qedty/ontology/`.

## Semantic scope

The ontology owns the canonical meaning of:

- `Entity` and `EntityResolution`
- `Relationship`
- `WorldEvent`
- `Capability`
- `Service`
- `Flow`
- `Assertion`
- `WorldModel` / `WorldSnapshot`

Causal propagation, continuity, economic impact, counterfactuals, uncertainty modeling, optimization and governance decisions remain downstream concerns. The ontology can represent facts needed by those layers without implementing their algorithms prematurely.

## Included implementation

The Python reference models are strict, frozen Pydantic models and reuse QEDTY Core semantics for:

- deterministic identity
- UTC-normalized `TimeWindow`
- WGS-84 `GeodeticPoint`
- dimensioned `Quantity`
- stable reference types
- epistemic status
- provenance/evidence references

The `WorldModel` aggregate provides collision detection, referential integrity, external-identifier indexes, accepted entity-resolution mappings, atomic transactions, deterministic snapshots and content fingerprints.

## Contract surfaces

```text
Python reference
      │
      ├── JSON Schema 2020-12
      ├── RDF / OWL
      ├── JSON-LD context
      ├── SHACL constraints
      ├── Protobuf v1
      └── Arrow field contract
             │
        golden vectors
```

The RDF layer follows a reified-record pattern where metadata would otherwise be lost. Structured value objects (`ExternalIdentifier`, `TimeWindow`, `Quantity`, `GeodeticPoint`) are represented explicitly so the boundary remains lossless.

## Repository paths

```text
src/qedty/ontology/
contracts/json-schema/ontology.schema.json
contracts/rdf/context.jsonld
contracts/rdf/qedty-ontology.ttl
contracts/shacl/qedty-ontology.shacl.ttl
contracts/arrow/ontology.contract.json
contracts/protobuf/README.md
proto/qedty/ontology/v1/ontology.proto
data/contracts/golden-vectors/ontology/
tests/ontology/
scripts/generate_ontology_schema.py
scripts/check_ontology_conformance.py
docs/ontology/
```

The ontology layer does **not** include generated build artifacts, package metadata, Rust `target/`, test caches, or unrelated source modules.

## Validation

Run from the repository root:

```bash
uv run python scripts/generate_ontology_schema.py
uv run python scripts/check_ontology_conformance.py
uv run ruff check src tests
uv run ruff format --check src tests
uv run pytest -q
uv run mypy src
uv run qedty validate
```

The native Protobuf contract can be compiler-validated with:

```bash
protoc \
  --proto_path=proto \
  --descriptor_set_out=/tmp/qedty-ontology.pb \
  proto/qedty/ontology/v1/ontology.proto
```

A native Rust ontology implementation is intentionally **not** shipped in this phase. Rust will implement ontology semantics after the Python contract and vectors are stable; the Core Rust implementation is the precedent.

## Research baseline

The engineering approach draws on ontology-engineering methods (METHONTOLOGY and NeOn), OBO Foundry principles, knowledge-graph construction surveys, temporal knowledge-graph research, ontology-matching evaluations, and current standards for provenance, observations, geospatial semantics, vocabularies and graph validation. See `RESEARCH_BASELINE.md` and `PLATFORM_INTEROPERABILITY.md`.

## Semantic rule

Python is the reference implementation. Rust, Arrow, Protobuf, SQL and RDF runtimes must conform to the same identifiers, temporal semantics, value-object meanings, evidence/provenance attachment rules and ontology vocabulary rather than redefining them independently.
