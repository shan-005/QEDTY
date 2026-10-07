# SERAPH-PCI-X Ontology Platform Interoperability

## Purpose

The ontology is a semantic reference layer, not a commitment to a single graph database or RDF runtime. SERAPH defines meaning in Python first and exposes interoperable boundaries through JSON Schema, RDF/OWL, SHACL, JSON-LD, Protobuf and Arrow.

The implementation uses reified domain records where provenance, evidence, time, confidence, reliability, or other qualification would otherwise be lost by projecting a relationship directly to a binary predicate.

## Platform assessment

| Platform | Useful capability | SERAPH role | Constraint / non-claim |
|---|---|---|---|
| Apache Jena | RDF, SPARQL, OWL, SHACL, GeoSPARQL, Fuseki/TDB | Reference adapter target for standards-oriented RDF validation/querying | Jena is not the authoritative SERAPH semantic implementation |
| RDF4J | RDF storage, parsing, querying, inference and SPARQL | Alternative RDF adapter/runtime | RDF4J is an integration option, not a required runtime dependency |
| Amazon Neptune | Managed graph service with SPARQL support | Potential managed deployment target | No vendor-specific semantics are required by the ontology |
| Stardog | SPARQL plus OWL/rules reasoning | Potential reasoning/knowledge-graph deployment target | SERAPH does not claim reasoner completeness or vendor equivalence |
| Neo4j + neosemantics | Property graph with RDF/OWL/RDFS/SKOS interoperability and SHACL support | Potential property-graph bridge | The bridge is deployment-specific; SERAPH semantics remain contract-defined |
| OAEI | Ontology matching evaluation campaigns and reusable tracks | Benchmark reference for future entity/ontology matching evaluation | Passing an OAEI track would be evidence for a specific matching task, not a universal matching claim |

## Standards boundary

The ontology is aligned to these external semantic standards where they are technically relevant:

- **OWL 2** for formal ontology representation.
- **SHACL** for constraint validation over RDF graphs.
- **PROV-O** for provenance interoperability and specialization.
- **SSN/SOSA** for observation-oriented concepts used later by evidence and sensing domains.
- **GeoSPARQL 1.1** for spatial semantics and query interoperability.
- **SKOS** for controlled vocabularies and taxonomies.
- **DCAT 3** for future dataset/catalog metadata integration.

SERAPH does not equate “mapped to a standard” with “conformant to every feature of that standard”. The ontology profile is deliberately bounded and versioned.

## Entity resolution boundary

Entity resolution is modeled as a first-class, evidence-qualified activity:

```text
external identifier
        ↓
 candidate generation / matching
        ↓
 EntityResolution
        ├── method
        ├── score
        ├── decision
        ├── resolver
        ├── evidence
        └── provenance
        ↓
 canonical Entity
```

This prevents a source identifier from becoming the canonical identity merely because it happened to be unique inside one source.

Future matching evaluation should report task-specific precision/recall or ranking metrics, dataset coverage, ambiguity, abstention/review rates, and calibration. It must not collapse these into a single unsupported “entity resolution accuracy” claim.

## Temporal boundary

An entity's `valid_time` describes when a modeled entity is valid in the world. `observed_at` describes when SERAPH observed or learned the statement. These timestamps are intentionally separate.

The same separation applies to events, relationships, capabilities, services, flows, assertions and resolutions whenever their semantics require it.

This distinction is essential for historical reconstruction, planned assets, delayed reporting, and retrospective corrections.

## Spatial boundary

SERAPH uses Core WGS-84 geodetic value objects at this layer. High-volume spatial computation remains a responsibility of the spatial layer and its native backends. GeoSPARQL interoperability is represented without making the ontology dependent on a particular spatial database.

## Data interchange boundary

- JSON Schema: external document validation and generated contract surface.
- JSON-LD/RDF/OWL: semantic-web interchange and standards-oriented knowledge graphs.
- Protobuf: typed service/control messages.
- Arrow: high-throughput columnar record interchange.
- Parquet: persistent columnar analytical storage.

Large numerical quantities retain exact decimal semantics at the contract boundary; they are not silently converted to binary floating point.

## Future conformance work

The ontology phase establishes the semantic contract. Later phases should add:

1. Python property tests for normalization and identity invariants.
2. Rust model conformance against the same ontology vectors.
3. Protobuf encode/decode round trips.
4. Arrow schema and record-batch interoperability tests.
5. SQL round trips once PostgreSQL/PostGIS persistence is introduced.
6. Differential entity-resolution benchmarks with explicit abstention and ambiguity handling.
7. RDF/SHACL execution tests in at least one standards-oriented runtime when the RDF adapter is implemented.
