# SERAPH-PCI-X research baseline — 2026-10-06

This architecture was reviewed against current authoritative/public standards and package metadata before generation. The baseline is intentionally limited to sources relevant to the implemented boundaries; it is not a claim of exhaustive Internet coverage.

## Geospatial

OGC JSON-FG 1.0.0 extends GeoJSON with feature typing, richer CRS handling and temporal/spatial members; OGC API – Features provides modular Web API building blocks for feature access.

References:
- https://www.ogc.org/standards/json-fg/
- https://docs.ogc.org/is/21-045r1/21-045r1.html
- https://www.ogc.org/standards/ogcapi-features/

## Space / GNSS

CCSDS 502.0-B-3 is the current Orbit Data Messages Blue Book listed by CCSDS. IGS lists RINEX 4.02 and SSR v1.0 as current formats/standards for GNSS products.

References:
- https://ccsds.org/publications/bluebooks/
- https://www.igs.org/formats-and-standards/
- https://igs.org/news/rinex-4-02/

## Provenance

W3C PROV-O is the recommendation-level ontology for representing provenance and explicitly permits domain-specific specialization. SERAPH uses this as an interoperability concept while retaining native contracts.

Reference:
- https://www.w3.org/TR/prov-o/

## Economics

The UN 2025 SNA is the international statistical standard for national accounts, adopted by the UN Statistical Commission in 2025. OECD describes ICIO as infrastructure mapping production, consumption, investment and international trade flows across countries and economic activities; the current database page notes a mid-January 2026 revision of the 2025 edition.

References:
- https://unstats.un.org/unsd/nationalaccount/sna2025.asp
- https://www.oecd.org/en/data/datasets/inter-country-input-output-tables.html

## Resilience / continuity

NIST SP 800-160 Vol. 2 Rev. 1 is the current final revision of its cyber-resiliency engineering guidance. ISO 22301:2019 remains published, while ISO/CD 22301 edition 3 is under development as of 2026; the project does not claim conformance to either standard merely by using related concepts.

References:
- https://csrc.nist.gov/pubs/sp/800/160/v2/r1/final
- https://www.iso.org/standard/75106.html
- https://www.iso.org/standard/93606.html

## Software supply chain

SLSA 1.2 is an approved specification covering source/build tracks and attestation/provenance concepts.

Reference:
- https://slsa.dev/spec/v1.2/

## Current package baselines verified from PyPI

- pydantic 2.13.5
- numpy 2.5.3
- scipy 1.18.1
- pyproj 3.8.0
- FastAPI 0.142.2

Package versions should be re-verified at release time because upstream releases can change after this development snapshot.
