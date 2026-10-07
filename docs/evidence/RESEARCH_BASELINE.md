# SERAPH-PCI-X Evidence research baseline — 2026-10-06

## Design conclusions

Evidence in SERAPH is an immutable, content-addressed representation plus acquisition context, temporal context, source identity, quality measurements, rights metadata, fragment selectors, normalization lineage and provenance. It is deliberately not equivalent to a claim or a true statement.

## Standards

### W3C PROV
PROV-O maps the PROV data model into OWL 2 and provides Entity, Activity and Agent as the primary provenance classes. PROV also distinguishes usage, generation and derivation; SERAPH mirrors these distinctions rather than reducing provenance to a timestamp and source string.

Reference: https://www.w3.org/TR/prov-o/
Reference: https://www.w3.org/TR/prov-dm/

### W3C DQV
DQV models quality through dimensions, metrics and measurements. SERAPH therefore stores individual measurements with the metric and method and only computes a composite when weights are explicitly supplied.

Reference: https://www.w3.org/TR/vocab-dqv/

### W3C DCAT 3
DCAT 3 describes datasets and their distributions and is suitable for the catalog-facing side of evidence when one logical dataset has multiple available representations.

Reference: https://www.w3.org/TR/vocab-dcat-3/

### W3C Web Annotation
The Web Annotation Data Model supports selectors for identifying fragments of resources, including text position, text quote and other selector types. SERAPH adopts the same principle for evidentiary pinpointing without embedding source content unnecessarily.

Reference: https://www.w3.org/TR/annotation-model/

### Integrity / HTTP digests
RFC 9530 standardizes the HTTP Content-Digest field and permits multiple digest algorithms. SERAPH's immutable store uses SHA-256 for its canonical content address in V2 while acquisition metadata can retain transport/header context.

Reference: https://www.rfc-editor.org/rfc/rfc9530.html

### FAIR
The FAIR Guiding Principles require persistent identifiers, rich metadata, interoperability, and explicit provenance and licensing for reusable research objects. Evidence records implement these goals through stable identifiers, content digests, rights metadata, provenance hooks and machine-readable contracts.

Reference: https://www.nature.com/articles/sdata201618

## Research literature

Buneman, Khanna & Tan (ICDT 2001) distinguish “why” provenance (which source data influenced a result) from “where” provenance (where in the source the contributing data came from). SERAPH implements both directions: provenance chains capture derivation/usage while selectors capture the exact fragment or position in the representation.

Reference: https://doi.org/10.1007/3-540-44503-X_20

Simmhan, Plale & Gannon (2005) survey provenance in e-science and emphasize lineage, representation, storage, dissemination and reuse. SERAPH separates those concerns into immutable content, provenance activities, registry/indexing, and interoperable contracts.

Reference: https://doi.org/10.1145/1084805.1084812

“Big Data Provenance: Challenges, State of the Art and Opportunities” emphasizes the volume/variety/velocity challenges of capturing, querying, sharing and using provenance in data-intensive workflows. SERAPH therefore avoids embedding payloads in metadata and supports streaming content-addressed storage.

Reference: https://pmc.ncbi.nlm.nih.gov/articles/PMC5796788/

## Non-claims

- A cryptographic digest proves representation integrity, not semantic truth.
- A source URI does not prove source authority.
- A quality score is not a universal probability of correctness.
- Entity resolution is not evidence; a resolution decision is a separate ontology object.
- Current PROV interoperability is semantic alignment, not a claim of complete PROV-O implementation.
