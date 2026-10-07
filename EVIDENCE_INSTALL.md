# SERAPH-PCI-X Evidence 2.0.0 — install

This package is intended to be extracted at the repository root (`~/seraph`). It contains only Evidence-layer files and Evidence-specific contracts/tests/docs; it does not replace the repository root README, pyproject, lockfile, Core, or Ontology source.

```bash
cd ~/seraph
unzip -o /path/to/seraph_pci_x_evidence_v2_final.zip
```

Then run:

```bash
uv run ruff check src tests
uv run ruff format --check src tests
uv run pytest -q
uv run mypy src
uv run python scripts/check_evidence_conformance.py
```

The Evidence package uses the `jsonschema` test dependency already introduced by the Core contract suite. It adds no mandatory runtime dependency beyond the existing SERAPH Core/Pydantic foundation.
