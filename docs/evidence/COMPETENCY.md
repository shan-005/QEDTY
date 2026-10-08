# Evidence competency questions

1. Can QEDTY prove which immutable byte representation was acquired?  Yes: SHA-256 content address plus acquisition receipt.
2. Can QEDTY distinguish retrieval time from the time represented by the evidence?  Yes: `retrieved_at`, `observed_at` and optional `valid_time` are separate fields.
3. Can an analyst pinpoint the contributing fragment inside a source?  Yes: text, JSON pointer, byte, line, row and URI-fragment selectors are supported.
4. Can QEDTY explain how a record was transformed?  Yes: normalization records plus PROV-style activities and parent relationships.
5. Can quality be inspected without confusing it with truth?  Yes: quality measurements are explicit and composite scoring is opt-in.
6. Can unknown licensing be represented without silently denying or granting rights?  Yes: permission states include `unknown` and the default policy is `NOASSERTION`.
7. Can the same evidence be used across ontology, graph, analytics and later native layers?  Yes: stable `EvidenceRef`, JSON Schema, Protobuf, Arrow and golden vectors are provided.
