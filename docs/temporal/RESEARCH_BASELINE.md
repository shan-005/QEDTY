# Temporal research baseline — 2026-10-06

QEDTY temporal semantics are grounded in several established lines of research and standards.

## Core time representation

ISO 8601-1:2019 is the current published baseline for Gregorian date/time interchange. ISO 8601-2:2019 remains current after 2024 review and adds representations for uncertain/approximate times, extended intervals, recurring intervals, and date/time arithmetic. A second edition is under development, so QEDTY does not claim conformance to the draft revision merely by referencing it.

References:
- https://www.iso.org/standard/70907.html
- https://www.iso.org/standard/70908.html
- https://www.iso.org/standard/91030.html

## Ontological temporal semantics

W3C OWL-Time models instants, intervals, durations and temporal relations, including the Allen interval relations. QEDTY's AllenRelation classifier intentionally follows this semantic family while retaining a compact Python representation.

References:
- https://www.w3.org/TR/owl-time/
- https://www.w3.org/TR/vocab-owl-time-rel/

## Interval algebra

Allen's 1983 Communications of the ACM paper introduced the 13 mutually exclusive primitive relationships between intervals. QEDTY implements these relations deterministically for finite proper intervals.

Reference:
- J. F. Allen, "Maintaining Knowledge about Temporal Intervals," Communications of the ACM, 26(11), 832–843, 1983. DOI: 10.1145/182.358434

## Temporal databases

Temporal database research distinguishes valid/application time from transaction/system time. Jensen and Snodgrass describe both dimensions and their role in historical accountability; the TSQL2 work consolidated temporal query concepts. Current PostgreSQL documentation provides native timestamp range/multirange types and exclusion constraints, making `[start,end)` an appropriate storage boundary even though application-level bitemporal semantics still belong in QEDTY.

References:
- C. S. Jensen and R. T. Snodgrass, "Temporal Data Management," IEEE TKDE, 11(1), 1999.
- https://link.springer.com/book/10.1007/978-1-4615-2289-8
- https://www.postgresql.org/docs/current/rangetypes.html
- https://www.postgresql.org/docs/current/ddl-temporal-tables.html

## Temporal knowledge graphs

Recent temporal-KG surveys emphasize that facts can change over time and that temporal representation must support evolving entities/relations and temporal reasoning. QEDTY therefore keeps temporal state orthogonal to graph topology; temporal graph learning is a downstream modeling concern, not the authoritative temporal contract.

References:
- Li Cai et al., "A Survey on Temporal Knowledge Graph: Representation Learning and Applications," arXiv:2403.04782, 2024.
- Y. Zhang et al., "A survey on temporal knowledge graph embedding: Models and applications," Knowledge-Based Systems, 304, 112454, 2024.

## Spatio-temporal data systems

OGC API - Features and OGC API - Moving Features provide explicit time-query semantics and support bounded, half-bounded and unbounded temporal intervals. These concepts inform the external interchange boundary while QEDTY retains its own typed reference model.

References:
- https://www.ogc.org/standards/ogcapi-features/
- https://www.ogc.org/standards/ogc-api-moving-features/

## Design consequence

QEDTY uses:

`UTC-normalized instant + explicit time-scale metadata + half-open finite interval + optional unbounded ends + orthogonal valid/transaction time + provenance-aware snapshots`.

This is deliberately stronger than a single `start/end` helper, while avoiding an incorrect claim that the Python layer itself implements every calendar, leap-second, or database standard.
