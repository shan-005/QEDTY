# API/output/CLI research baseline

Outputs are separated by purpose: canonical JSON for automation, GeoJSON/JSON-FG for geospatial interchange, graph JSON for semantic export, tabular outputs for human inspection, and reports for persisted artifacts.

OpenAPI and JSON Schema are treated as external contract languages, while Protobuf is reserved for service boundaries in the wider architecture. The API does not expose a mutation surface by default; the initial public endpoints are health/readiness/metadata/world/graph/feature discovery.
