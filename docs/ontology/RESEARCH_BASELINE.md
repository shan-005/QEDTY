# QEDTY Ontology Research Baseline — 2026-10-06

## Scope

QEDTY uses a **reified, evidence-aware, temporally qualified world ontology**. Python is the semantic reference implementation. JSON Schema, RDF/OWL/JSON-LD, SHACL and Protobuf/Arrow contracts are boundary representations; they do not create independent business semantics.

The design follows ontology-engineering practice based on explicit scope, competency questions, reuse of established vocabularies, versioned terms, formal constraints, and iterative validation. METHONTOLOGY frames ontology construction as a structured engineering process with a defined sequence of activities and evolving prototypes; NeOn extends this toward reuse, collaboration and evolving ontology networks. OBO Foundry principles additionally emphasize open formal representation, persistent identifiers, versioning, explicit scope and textual definitions. 

## Research findings translated into implementation rules

### Ontology engineering

METHONTOLOGY supports a disciplined ontology-development lifecycle rather than ad-hoc class creation. NeOn emphasizes reuse/reengineering, collaborative development and evolution. QEDTY therefore keeps a stable local semantic core while explicitly mapping to external standards instead of copying entire external ontologies into product code.

References:
- https://aaai.org/papers/0005-ss97-06-005-methontology-from-ontological-art-towards-ontological-engineering/
- https://oeg.fi.upm.es/index.php/en/methodologies/59-neon-methodology/index.html
- https://obofoundry.org/principles/fp-000-summary.html

### Knowledge-graph construction

Ji et al. survey representation, acquisition, temporal knowledge and applications. Zhong et al. survey more than 300 KG-construction methods and organize practical construction into knowledge acquisition, refinement and evolution, including entity typing, coreference/entity resolution, relation extraction, fusion and temporal evolution. These findings support separating canonical entities from identity-resolution records and keeping provenance/evidence attached to semantic statements.

References:
- https://arxiv.org/abs/2002.00388
- https://doi.org/10.1145/3618295
- https://arxiv.org/abs/2302.05019

### Entity resolution and ontology matching

Ontology matching is a semantic interoperability problem, not a string-equality problem. LLMs4OM evaluates retrieval/matching over 20 ontology-matching datasets. Later work such as MILA shows the value of retrieval, structural search and selective LLM use while reducing expensive model calls. QEDTY therefore records resolution method, score, decision, resolver and evidence, but never promotes a model score directly into canonical truth.

References:
- https://arxiv.org/abs/2404.10317
- https://arxiv.org/abs/2501.11441
- https://arxiv.org/abs/2508.10703

### Temporal knowledge graphs

Temporal KG surveys emphasize that facts and relations can be valid only during intervals and that graph evolution must be represented explicitly. QEDTY therefore separates `valid_time` from observation/assertion timestamps and uses Core's half-open UTC intervals.

References:
- https://arxiv.org/abs/2403.04782
- https://doi.org/10.1016/j.knosys.2024.112454

### Provenance

PROV-O expresses the PROV Data Model in OWL 2 and provides classes, properties and restrictions for interoperable provenance. It also explicitly permits domain-specific specialization. QEDTY consequently keeps provenance references as first-class metadata on semantic records rather than treating provenance as a report-only concern.

Reference:
- https://www.w3.org/TR/prov-o/

### Observation and sensing

SSN 2023 is a W3C Recommendation and OGC Standard covering observations, actuation, sampling, systems and deployments; SOSA is its lightweight interoperability level. The ontology reserves detailed observation semantics for the evidence/source layer while preserving observed timestamps and evidence links on the canonical world records.

Reference:
- https://www.w3.org/TR/vocab-ssn-2023/

### Geospatial semantics

GeoSPARQL 1.1 provides a vocabulary and query extension for geospatial data represented in RDF, including qualitative spatial reasoning and quantitative spatial computation. QEDTY uses its local Core geodetic type as the stable computational primitive and maps spatial semantics at the interoperability/database boundary.

Reference:
- https://www.ogc.org/standards/geosparql/

### Controlled vocabularies

SKOS is a W3C Recommendation for sharing and linking taxonomies and other knowledge-organization systems. QEDTY keeps machine-critical tokens in typed enums while exposing deterministic IRI mappings so external controlled vocabularies can be aligned later.

Reference:
- https://www.w3.org/TR/skos-reference/

### Data catalogs

DCAT 3 is the current W3C Recommendation for RDF-based dataset and data-service descriptions, including resource versioning and dataset series. It is used as a boundary reference for future evidence/source catalogs rather than as the ontology's entity model.

Reference:
- https://www.w3.org/TR/vocab-dcat-3/

### OWL and graph validation

OWL 2 supplies the formal ontology semantics for classes, properties, individuals and data values. SHACL is a graph constraint language for validating RDF data graphs against shape graphs. QEDTY uses OWL as the conceptual semantics reference and SHACL as the external validation boundary; the package does not claim SHACL 1.2 draft conformance.

References:
- https://www.w3.org/TR/owl-overview/
- https://www.w3.org/TR/shacl/

## Standards status decisions

- **RDF 1.1:** stable baseline for current RDF mappings.
- **RDF 1.2:** monitored as a 2026 Candidate Recommendation; draft-only features are not required by this package.
- **OWL 2:** Recommendation and semantic reference.
- **SHACL:** 2017 Recommendation baseline; SHACL 1.2 Working Draft monitored.
- **PROV-O:** Recommendation and provenance mapping.
- **SSN 2023:** Recommendation / OGC Standard.
- **GeoSPARQL 1.1:** OGC Standard.
- **SKOS:** Recommendation.
- **DCAT 3:** Recommendation.

## Deliberate semantic decisions

1. **Identity is separate from observation.** An entity's canonical identifier is stable; observations, assertions and resolutions are records about that entity.
2. **External identifiers are not QEDTY identifiers.** They are names in other namespaces that may be resolved into canonical entities.
3. **Resolution is an assessed mapping.** An accepted mapping must be explicit and can be rejected when conflicting accepted mappings exist in one world model.
4. **Validity and observation are separate clocks.** A scheduled/future entity may be observed before its validity interval begins.
5. **Confidence is an assessment score.** No probability, calibration or posterior interpretation is implied merely by a value in `[0,1]`.
6. **Relationships are reified.** A relationship is a first-class node because it may carry time, strength, capacity, reliability, latency, evidence and provenance.
7. **Quantities use Core semantics.** The ontology reuses `Quantity` instead of inventing new value/unit pairs.
8. **WorldModel is an in-memory semantic aggregate.** Persistence, distributed transactions, graph indexes and analytical execution belong to later layers.
9. **Open-ended properties are quarantined.** Free-form properties exist for extension but do not redefine canonical meaning.
10. **Standards are mapped, not copied wholesale.** QEDTY reuses established semantics where compatible and preserves local contracts where product-specific behavior is required.

## Known non-claims

This package does **not** claim:

- completeness of the full OWL/SHACL ecosystem;
- formal ontology-reasoner completeness;
- that ontology matching is solved by LLMs;
- that confidence values are probabilities;
- complete RDF/JSON-LD parser/serializer conformance;
- Rust/Arrow/Protobuf/SQL equivalence beyond the tests actually executed;
- causality, propagation, continuity, economic impact or optimization correctness.

Those claims require later layers and separate certification evidence.
