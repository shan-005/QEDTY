# SERAPH-PCI-X Graph replacement

This package replaces the entire current `src/seraph/graph/` implementation while keeping Core, Ontology, Evidence, Temporal and Spatial outside the package.

## Included

```text
src/seraph/graph/
  __init__.py
  algorithms.py
  arrow.py
  builder.py
  model.py
  persistence.py
  query.py
  schema.py
  spatial.py
  store.py
  temporal.py

tests/
  test_graph.py
  test_graph_conformance.py
  graph_golden_vectors.json

scripts/
  check_graph_conformance.py

contracts/json-schema/graph-v1.json
contracts/arrow/graph-v1.json
proto/seraph/graph/v1/graph.proto
docs/graph/CONTRACTS.md
docs/graph/RESEARCH_BASELINE.md
```

## Replacement policy

Replace `src/seraph/graph/` completely. Add the Graph tests, golden vectors and conformance script. Add the contract artifacts under the existing contract/proto/docs trees without replacing unrelated frozen-layer files.

The Graph layer does not mutate or redefine Core, Ontology, Evidence, Temporal or Spatial semantics.

## Validation in the target repository

```bash
uv run ruff check src tests
uv run ruff format --check src tests
uv run pytest -q
uv run mypy src

uv run pytest -q tests/test_graph.py tests/test_graph_conformance.py -vv
uv run python scripts/check_graph_conformance.py

test -s tests/graph_golden_vectors.json && echo "Graph golden vectors: PASS"

protoc \
  --proto_path=proto \
  --descriptor_set_out=/tmp/seraph-graph.pb \
  proto/seraph/graph/v1/graph.proto

test -s /tmp/seraph-graph.pb && echo "Graph Protobuf descriptor: PASS"

git restore -- src/seraph/_version.py
git --no-pager diff --check
git status --short
```

The package was checked in an isolated compatibility harness with 22 Graph tests and 12 conformance checks. The authoritative validation remains the project's own Python 3.12 / uv / Ruff / mypy environment after replacement.
