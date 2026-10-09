# Fuzzing plan

No `cargo-fuzz` target is required by the initial three-vector core because the current public surface is small and the JSON fixtures are repository-controlled. Add fuzz targets when there is a non-trivial parser, decoder, untrusted serialization boundary, or complex graph/scenario input surface.

Candidate targets (future):

- canonical JSON input normalization with arbitrary nested JSON values;
- deterministic-ID part arrays and malformed lengths;
- temporal interval parsers and boundary combinations;
- graph edge collections and duplicate/malformed identifiers;
- future Arrow/Protobuf adapter validation.

Keep fuzz regression fixtures under the relevant test target. Run short smoke fuzzing separately from required stable CI because cargo-fuzz generally uses nightly and libFuzzer/LLVM support. Any discovered input that triggers a bug becomes a deterministic regression test before fixing the implementation.
