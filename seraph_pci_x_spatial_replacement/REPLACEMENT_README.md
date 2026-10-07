# SERAPH-PCI-X Spatial replacement package

Target branch: `seraph-pci-x-canonical`

Target path for source replacement:

```text
src/seraph/spatial/
```

This package contains complete replacements for all nine existing Spatial modules, plus the Spatial test suite, golden vectors, and research baseline.

## Files

```text
src/seraph/spatial/
├── __init__.py
├── crs.py
├── geodesy.py
├── geojson.py
├── index.py
├── jsonfg.py
├── models.py
├── operations.py
└── query.py

tests/
├── test_spatial.py
└── spatial_golden_vectors.json

SPATIAL_RESEARCH_BASELINE.md
```

## Replacement

Copy the nine files under `src/seraph/spatial/` over the matching repository files. Copy the test files if you want the accompanying reference/conformance coverage.

Do not replace Core, Ontology, Evidence, or Temporal from this package.

## Validation

The isolated reference environment passed:

```text
26 passed
compileall: PASS
return-annotation AST audit: PASS
```

The package intentionally keeps Shapely, pyproj, H3, and S2 as runtime-optional integrations where practical. The repository's existing `geo` extra already supplies Shapely and pyproj for the normal full Spatial environment.

Ruff and mypy were not available in the isolated build container; run the repository's locked toolchain before freezing Spatial in the main tree.
