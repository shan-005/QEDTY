# QEDTY Ontology Protobuf Boundary

The canonical Protobuf source is:

`proto/qedty/ontology/v1/ontology.proto`

This directory documents the contract boundary without duplicating the `.proto` source. Generated language bindings are build artifacts and are not committed here.

Design rules:

- machine identifiers remain strings and are governed by Python/Core identity semantics;
- timestamps use `google.protobuf.Timestamp`;
- exact decimal quantities cross the boundary as decimal-preserving strings plus a unit token;
- open-ended property bags use `google.protobuf.Struct`/`Value` only at explicitly dynamic fields;
- the Protobuf model transports the ontology but does not redefine ontology meaning.
