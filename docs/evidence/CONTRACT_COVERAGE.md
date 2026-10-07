# Evidence contract coverage

| Surface | Purpose | Status |
|---|---|---|
| Python/Pydantic | Semantic reference models | Implemented |
| SHA-256 CAS | Immutable byte identity | Implemented |
| JSON Schema 2020-12 | Machine validation | Implemented |
| Protobuf | Typed service/control contract | Implemented |
| Arrow schema | Bulk evidence metadata | Implemented |
| PROV-O / PROV-DM mapping | Lineage semantics | Implemented as boundary vocabulary |
| DQV mapping | Quality measurements | Implemented as boundary vocabulary |
| DCAT 3 mapping | Dataset/distribution metadata | Implemented as boundary vocabulary |
| Web Annotation selectors | Fine-grained evidence location | Implemented |
| SPDX expression field | Rights identification | Implemented; grammar validation delegated to release tooling |
| HTTP Digest compatibility | Acquisition metadata compatibility | SHA-256 implementation; transport header preservation |
| Golden vectors | Deterministic interoperability | Implemented: 8 vectors |

## Evidence semantics

1. Integrity: stored bytes match the declared SHA-256 digest.
2. Provenance: acquisition/transformation activities explain how representations entered the system.
3. Quality: explicit measurements describe fitness characteristics under an identified metric and method.
4. Rights: licensing is explicit and unknown rights remain unknown.
5. Resolution: an evidence item may refer to ontology entities, but entity resolution remains a separate decision object.
6. Interpretation: evidence does not itself become a claim or a truth assertion.

## Current non-claims

The Core does not claim full implementation of every construct in PROV-O, DCAT, DQV, Web Annotation, RDF, SHACL or SPDX. The boundary contracts use selected interoperable concepts and document those selections.
