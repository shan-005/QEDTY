# Temporal contract coverage

| Semantic surface | Python reference | JSON Schema | Protobuf | Arrow | RDF/SHACL | Golden vector |
|---|---:|---:|---:|---:|---:|---:|
| Temporal extent | yes | yes | yes | yes | yes | contains/intersection |
| Allen 13 relations | yes | yes | yes | relation column | OWL-Time alignment | yes |
| Bitemporal coordinates | yes | yes | yes | yes | yes | yes |
| Temporal instant metadata | yes | yes | yes | timestamp column | yes | yes via snapshot |
| Calendar granularity | yes | yes | string field | granularity column | domain vocabulary | yes |
| Snapshot identity | yes | yes | yes | manifest boundary | provenance-compatible | yes |
| Temporal versions | yes | yes | yes | record columns | provenance-compatible | yes |
| OGC datetime parsing | yes | external API boundary | string form | n/a | n/a | parsing tests |

The contract layer is intentionally semantic rather than a claim that every external standard has been fully implemented. Rust and database backends must consume the same canonical semantics when those backends are added.
