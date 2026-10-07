# API / Output / CLI contract

HTTP API follows an OpenAPI 3.1.1 description. Geospatial feature routes use OGC API Features concepts; JSON-FG is an explicit output extension. The CLI is an automation-facing interface and supports deterministic JSON export without requiring the optional API stack.

Standards/platform anchors:
- OpenAPI 3.1.1 defines language-agnostic HTTP API descriptions: https://spec.openapis.org/oas/v3.1.1.html
- JSON Schema Draft 2020-12 is the external document validation baseline: https://json-schema.org/draft/2020-12
- OGC API Features uses OpenAPI and provides feature collections/queries: https://www.ogc.org/standards/ogcapi-features/
- OGC JSON-FG extends GeoJSON with CRS/temporal/type capabilities and remains GeoJSON-compatible: https://www.ogc.org/standards/json-fg/
- RFC 7946 defines GeoJSON; SERAPH uses it for interoperable feature exchange.
- OpenTelemetry context propagation is applicable to API request/run correlation: https://opentelemetry.io/docs/concepts/context-propagation/
