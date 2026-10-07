# SERAPH-PCI-X Spatial Research & Implementation Baseline

Date: 2026-10-06

Status: proposed Python-reference implementation for the Spatial phase

## 1. Scope

This package upgrades the existing `src/seraph/spatial/` implementation into a domain-level spatial reference layer for SERAPH-PCI-X. The implementation is deliberately deterministic, contract-oriented, and suitable for later Rust differential implementation.

The Spatial layer owns:

- coordinate positions and geometry validation
- geographic extents and antimeridian semantics
- CRS identification and coordinate transformation
- ellipsoidal geodesy
- vector geometry predicates and constructive operations
- spatial indexing and deterministic nearest/range queries
- GeoJSON RFC 7946 interoperability
- OGC JSON-FG 1.0.0 interoperability
- explicit optional H3/S2 indexing adapters

The layer does **not** own temporal semantics, ontology semantics, evidence lineage, database persistence, or application orchestration. Those remain in their established/future layers.

## 2. Standards baseline

### OGC JSON-FG 1.0.0

JSON-FG extends GeoJSON with richer CRS references, temporal members, feature typing/schema declarations, measures, and additional geospatial interoperability constructs. `conformsTo` is part of the JSON-FG contract. JSON-FG timestamps are required to use UTC `Z`. CRS84/CRS84h are the default WGS 84 longitude/latitude references. The JSON-FG `coordRefSys` member applies to JSON-FG `place`/additional geometries rather than changing the meaning of the ordinary GeoJSON `geometry` member.

Reference: https://www.ogc.org/standards/json-fg/

Specification: https://docs.ogc.org/is/21-045r1/21-045r1.html

### OGC API - Features

The API boundary should remain compatible with the current OGC API - Features family. Spatial query semantics should be implemented below the HTTP layer so the same reference behavior can be exposed through Python, Rust, SQL and web clients.

Reference: https://www.ogc.org/standards/ogcapi-features/

### OGC Simple Feature Access

The geometry model follows the standard Point, LineString/Curve, Polygon/Surface, Multi* and GeometryCollection vocabulary. SERAPH keeps a strict vector subset in this phase and delegates complex curved/solid constructs to future extensions rather than inventing incompatible semantics.

Reference: https://www.ogc.org/standards/sfa/

### OGC API - Moving Features

The frozen SERAPH Temporal layer provides the authoritative time semantics. Moving-feature standards are treated as an interoperability target for future trajectories rather than duplicated temporal logic inside Spatial.

Reference: https://www.ogc.org/standards/moving-features/

### CRS / WKT

CRS identifiers are delegated to PROJ/pyproj rather than implemented with a local parser. WKT CRS 2.1 and PROJ/PROJJSON are interoperability forms.

Reference: https://www.ogc.org/standards/wkt-crs/

## 3. Geodesy research

### Ellipsoidal geodesics

The authoritative reference is ellipsoidal geodesic computation rather than a spherical haversine approximation. Charles F. F. Karney's geodesic algorithms provide robust direct and inverse solutions on an ellipsoid and support differential/integral geodesic quantities.

Paper: C. F. F. Karney, “Algorithms for geodesics,” Journal of Geodesy.

DOI: https://doi.org/10.1007/s00190-012-0578-z

SERAPH implementation: PROJ/pyproj `Geod`, using WGS 84 by default, with the frozen Core haversine helper retained only as a fallback for lightweight distance/direct operations when pyproj is unavailable.

PROJ: https://proj.org/

pyproj: https://pyproj4.github.io/pyproj/

## 4. CRS transformation design

Transformations use pyproj `Transformer` with:

- `always_xy=True` to make SERAPH's x/y and GeoJSON longitude/latitude order explicit
- optional area-of-interest hints
- `allow_ballpark=False` by default
- optional `only_best` and `force_over`
- optional coordinate epoch for time-dependent transformations

A geographic SERAPH `Point` is not reused for projected coordinates. Projected coordinates use `CoordinatePoint`. This avoids silently treating meters or other projected axes as degrees.

`ST_SetSRID`-style “label only” operations are intentionally distinct from actual coordinate transformations.

## 5. Geometry model

The reference implementation accepts the seven standard GeoJSON vector geometry types:

- Point
- MultiPoint
- LineString
- MultiLineString
- Polygon
- MultiPolygon
- GeometryCollection

Positions may be XY, XYZ/XYM, or XYZM. Spatial bounds use X/Y and, when present, Z; M is a non-spatial measure and is never included in spatial extents.

Rings are explicitly validated as closed and contain at least four positions.

Coordinate values are required to be finite. Geographic coordinates are constrained to valid longitude/latitude ranges.

## 6. Topology and GEOS

Shapely 2.x / GEOS are used as the optional constructive/predicate engine. This avoids reimplementing mature computational-geometry algorithms in Python. The exposed operations include intersects, covers, within, contains, equals, intersection, union, difference, validity repair, precision reduction, and normalized geometry.

Important semantic rule: predicates/constructive operations are CRS-local. SERAPH rejects operations between geometries carrying different CRS metadata. The caller must transform first.

For longitude/latitude geometries, GEOS operations remain planar computational-geometry operations. They are not presented as geodesic area or distance computations. Geodesic metric operations live in `geodesy.py`.

Shapely: https://shapely.readthedocs.io/

GEOS: https://libgeos.org/

## 7. Spatial indexing research

### R-tree family

R-trees are the foundational dynamic spatial-index structure for bounding-box search.

Paper: Antonin Guttman, “R-trees: A Dynamic Index Structure for Spatial Searching,” SIGMOD 1984, pp. 47-57.

DOI: https://doi.org/10.1145/971697.602266

The reference implementation therefore provides deterministic bounding-box and grid indexes and an optional GEOS STRtree adapter. The Python implementation does not attempt to replace mature R-tree/STRtree implementations with a home-grown database index.

### Grid index

`PointGridIndex` is a deterministic lightweight lon/lat acceleration structure for local/single-node workloads. It never becomes the numerical authority: final nearest/radius ranking uses exact WGS 84 geodesic distance.

### STRtree

`STRtreeIndex` uses Shapely/GEOS STRtree where available. All indexed geometries must use one CRS, and query geometries must match it.

### H3

H3 is suitable as a global hierarchical spatial key for aggregation, partitioning, joins and multi-resolution analysis. The reference implementation keeps H3 optional and exposes explicit polygon containment policy (`center`, `full`, `overlap`, `bbox_overlap`) rather than silently choosing semantics.

Upstream implementation: https://github.com/uber/h3

Python binding documentation: https://uber.github.io/h3-py/

### S2

S2 is useful for spherical hierarchical indexing and point/cell joins. It is exposed as an optional adapter only; SERAPH does not make S2 the canonical geometry model.

Reference: https://s2geometry.io/

## 8. Global data interchange research

### GeoArrow 0.2

GeoArrow standardizes geospatial representations in Apache Arrow-compatible memory structures and extension metadata. Version 0.2 defines geometry layouts and metadata including CRS and supports a common geometry vocabulary. The ecosystem includes Rust (`geoarrow-rs`), Python, JavaScript/WASM and C/C++ components.

Specification: https://geoarrow.org/

Metadata: https://geoarrow.org/extension-types.html

The architecture implication is important: Spatial contracts must be representable as Arrow-compatible XY/XYZ/XYM/XYZM data without changing semantic meaning.

### GeoParquet

GeoParquet provides file-level geospatial metadata for Parquet. SERAPH should use GeoParquet for large analytical datasets and Arrow/GeoArrow for in-memory/interprocess paths rather than serializing large spatial datasets through JSON.

Specification: https://geoparquet.org/

## 9. Database platform research

### PostgreSQL + PostGIS

PostGIS remains the authoritative operational spatial database target because it provides geometry/geography types, spatial functions, GiST/R-tree style indexes, KNN operators and CRS transformations through PROJ.

Reference: https://postgis.net/docs/

The Python layer deliberately does not imitate the entire PostGIS SQL engine. It establishes semantics that SQL adapters can map to.

### DuckDB spatial

DuckDB Spatial is a complementary analytical engine. It is appropriate for columnar/Parquet workflows, local analytics and large read-heavy spatial analysis.

Reference: https://duckdb.org/docs/stable/core_extensions/spatial/overview

## 10. Research-derived design invariants

1. **Coordinate order is explicit.** Domain objects expose latitude/longitude names; wire geometry follows x/y ordering.
2. **CRS is metadata with semantics.** Transformation is distinct from relabeling.
3. **Planar and geodesic operations are not conflated.** GEOS predicates are planar; `Geod` provides ellipsoidal distance/area/perimeter.
4. **Antimeridian behavior is explicit.** Bounding boxes may be wrapped (`west > east`) and are split when indexing.
5. **Precision is intentional.** Rounding is explicit rather than implicit.
6. **Topology is delegated to mature libraries.** No improvised polygon-intersection algorithms are introduced.
7. **Indexes accelerate; exact operations decide.** Candidate selection must not become a correctness oracle.
8. **Optional global indexes remain optional.** H3/S2 are adapters, not canonical geometry semantics.
9. **Time belongs to the frozen Temporal layer.** Spatial may carry coordinate epochs where the CRS transformation requires one, but it does not create new temporal semantics.
10. **Every result must be reproducible.** Deterministic ordering and stable serialization are preferred everywhere.
11. **The Python implementation is a specification-by-execution.** The future Rust implementation must be able to consume the same vectors and satisfy the same invariants.

## 11. Explicit non-goals for this phase

- full raster processing stack
- terrain/DEM/remote-sensing processing
- curved/solid OGC geometry semantics
- spatial SQL engine reimplementation in Python
- a mandatory H3/S2 dependency
- a mandatory PyArrow/GeoArrow dependency in the base package
- global-scale distributed indexing inside the Python reference layer
- a claim of centimeter-level surveying accuracy for arbitrary source data
- a claim that planar geometry operations on EPSG:4326 are geodesically correct

## 12. Planned Rust mapping

The Python semantics map cleanly to future crates:

- `seraph-spatial` — geometry, bbox, predicates, transforms
- `seraph-geodesy` or geodesy module — direct/inverse/area/line calculations
- `seraph-temporal` — already conceptually frozen; Spatial consumes its types rather than replacing them
- `seraph-arrow` — GeoArrow/Arrow data interchange
- `seraph-formats` — GeoJSON/JSON-FG/WKB/WKT adapters

The conformance contract is: same canonical input, same semantic result, explicit numerical tolerance where floating-point implementation differences exist.

## 13. Validation performed on this replacement

- 25 Spatial tests passed in the local reference environment.
- Python bytecode compilation passed for all Spatial modules.
- AST audit found no missing function return annotations.
- Shapely 2.1.2 was available in the local smoke environment.
- The local smoke environment had pyproj 3.7.2; the repository lockfile/CI baseline targets pyproj 3.8.0.

Ruff and mypy were not installed in the isolated build container, so they could not be independently executed there. The repository's canonical CI remains the authoritative toolchain validation environment.
