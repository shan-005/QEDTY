# SERAPH-PCI-X Ontology Contract Coverage

| Semantic concept | Python reference | JSON Schema | RDF/OWL | JSON-LD | SHACL | Arrow | Protobuf | Golden vector |
|---|---|---|---|---|---|---|---|---|
| Entity | `entities.Entity` | yes | `seraph:Entity` | yes | yes | yes | yes | yes |
| Entity resolution | `entities.EntityResolution` | yes | `seraph:EntityResolution` | yes | yes | yes | yes | yes |
| Relationship | `relations.Relationship` | yes | `seraph:Relationship` | yes | yes | yes | yes | yes |
| Event | `events.WorldEvent` | yes | `seraph:Event` | yes | yes | yes | yes | yes |
| Capability | `capabilities.Capability` | yes | `seraph:Capability` | yes | yes | yes | yes | yes |
| Service | `services.Service` | yes | `seraph:Service` | yes | yes | yes | yes | yes |
| Flow | `flows.Flow` | yes | `seraph:Flow` | yes | yes | yes | yes | yes |
| Assertion | `assertions.Assertion` | yes | `seraph:Assertion` | yes | yes | yes | yes | yes |
| External identifier | Core `ExternalIdentifier` | nested | `seraph:ExternalIdentifier` | yes | value-object boundary | embedded | yes | covered by entity/resolution |
| Time window | Core `TimeWindow` | nested | `seraph:TimeWindow` | yes | ordering boundary | embedded | yes | covered by event/flow |
| Quantity | Core `Quantity` | nested | `seraph:Quantity` | yes | dimensional boundary | decimal128 | yes | covered by capability/flow |
| Geodetic point | Core `GeodeticPoint` | nested | `seraph:GeodeticPoint` | yes | coordinate bounds | embedded | yes | entity/location boundary |
| World aggregate | `world.WorldModel` | top-level document | graph/container boundary | document boundary | integrity boundary | batch contract | `OntologyDocument` | integration coverage |

## Contract principles

- SERAPH identifiers are deterministic and do not depend on external source identifiers.
- External identifiers remain distinct from canonical SERAPH identities.
- Entity resolution is first-class and evidence-qualified; accepted mappings cannot conflict inside one namespace/value key.
- Temporal validity is separate from observation/assertion time.
- Evidence and provenance references remain attached to semantic records.
- Quantitative values reuse Core `Quantity` rather than duplicating unit/value semantics.
- `Decimal` quantity semantics remain exact at the Arrow/Protobuf boundary.
- Relationships are reified because temporal, reliability, latency, capacity and provenance metadata are semantically significant.
- Python remains the semantic reference; RDF/OWL/SHACL, Arrow and Protobuf are interoperability boundaries, not alternate hidden business logic.
- Later Rust/SQL implementations must be checked against these semantics using the golden-vector suite and differential tests.
