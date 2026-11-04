# QEDTY ontology

The ontology package is the contract-first semantic reference implementation for
`src/qedty/ontology/`. Its package and contract versions are defined by the source and
machine-readable artifacts; this document describes responsibilities rather than acting as
a second version registry.

## Semantic ownership

The ontology owns the canonical meaning of:

- `Entity` and `EntityResolution`;
- `Relationship`;
- `WorldEvent`;
- `Capability`;
- `Service`;
- `Flow`;
- `Assertion`;
- `WorldModel` and `WorldSnapshot`.

Propagation, continuity, economic impact, counterfactual analysis, uncertainty,
optimization, and governance decisions are downstream concerns. The ontology represents
the facts and references those layers consume without duplicating their algorithms.

## Python reference implementation

The Python models reuse Core semantics for deterministic identity, UTC-normalized time
windows, geodetic points, dimensioned quantities, stable references, epistemic status, and
evidence/provenance references.

The `WorldModel` aggregate provides collision detection, referential integrity,
external-identifier indexes, accepted entity-resolution mappings, transactions, snapshots,
and content fingerprints. Consult the implementation and tests for the exact supported
invariants.

## Contract surfaces

The ontology has interoperability artifacts for JSON Schema 2020-12, RDF/OWL, JSON-LD,
SHACL, Protobuf, and Arrow. Golden vectors define selected deterministic reference behavior.

These surfaces are bounded mappings, not claims of complete conformance to every feature
of the referenced standards. Python remains the semantic authority. Rust and other
implementations must conform only within explicitly accepted operation-level contracts.

## Repository paths

- `src/qedty/ontology/` — Python semantic implementation.
- `contracts/json-schema/` — JSON Schema artifacts.
- `contracts/rdf/` — RDF and JSON-LD artifacts.
- `contracts/shacl/` — SHACL shapes.
- `contracts/arrow/` — Arrow-oriented contract artifacts.
- `proto/qedty/ontology/` — Protobuf source.
- `data/contracts/golden-vectors/ontology/` — deterministic fixtures.
- `tests/ontology/` — ontology tests.
- `scripts/` — schema generation and conformance checks.

## Validation

Run from the repository root:

```bash
uv run python scripts/generate_ontology_schema.py
uv run python scripts/check_ontology_conformance.py
uv run ruff check src tests
uv run pytest -q tests/ontology
```

Use the current repository scripts and CI workflows as the authority if command names or
test locations change.

## Related documents

- [Ontology competency questions](COMPETENCY_QUESTIONS.md)
- [Platform interoperability](PLATFORM_INTEROPERABILITY.md)
- [Ontology research baseline](RESEARCH_BASELINE.md)
- [Contract coverage](../../contracts/CONTRACT_COVERAGE.md)
- [Graph contracts](../graph/CONTRACTS.md)
