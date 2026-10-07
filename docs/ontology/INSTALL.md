# Installing SERAPH-PCI-X Ontology v2.0.0

From the repository root:

```bash
unzip -o /path/to/seraph_pci_x_ontology_v2_final.zip

uv run python scripts/generate_ontology_schema.py
uv run python scripts/check_ontology_conformance.py
uv run ruff check src tests
uv run ruff format --check src tests
uv run pytest -q tests/ontology
uv run mypy src
uv run seraph validate
```

Then compiler-validate the ontology Protobuf source:

```bash
protoc \
  --proto_path=proto \
  --descriptor_set_out=/tmp/seraph-ontology.pb \
  proto/seraph/ontology/v1/ontology.proto

test -s /tmp/seraph-ontology.pb && echo "Ontology Protobuf descriptor: PASS"
```

## Package boundary

This archive overlays only:

```text
src/seraph/ontology/
contracts/
proto/seraph/ontology/
data/contracts/golden-vectors/ontology/
tests/ontology/
scripts/check_ontology_conformance.py
scripts/generate_ontology_schema.py
docs/ontology/
```

It does not replace `README.md`, `pyproject.toml`, `uv.lock`, Core files, unrelated application modules, generated `.egg-info`, Rust `target/`, Python caches, or other build artifacts.

## Dependency note

The ontology reference models require the existing SERAPH Core package. The conformance script and schema tests use `jsonschema`, which is already part of the repository test dependency set from the Core contract work. No RDF engine is required by the base ontology tests; the RDF/Turtle artifacts are static interoperability contracts. A standards-runtime validation pass can be added later through an adapter such as Apache Jena or RDF4J without making that runtime a production dependency of the Python semantic layer.

## Native implementation boundary

No Rust ontology crate is included in this phase. Core Rust exists as the first native precedent. The ontology Rust model/compute implementation should be added only after this semantic contract is accepted, using the same golden-vector and differential-testing pattern rather than redefining ontology meaning.
