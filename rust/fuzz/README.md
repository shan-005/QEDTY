# Fuzzing plan

The current Rust conformance executable covers four implemented API families—canonical JSON, deterministic identity, WGS-84 ECEF conversion, and RFC 3339 timestamp normalization—with eleven shared behavior cases: two canonicalization vectors, one identity vector, seven ECEF vectors, and one timestamp vector. The `contract_result.json` and `quantity.json` fixtures do not yet have matching Rust APIs and are not conformance passes.

No `cargo-fuzz` target is required by the current small public surface and repository-controlled vector inputs. Add fuzz targets when there is a non-trivial parser, decoder, untrusted serialization boundary, or complex graph/scenario input surface.

Candidate targets (future):

- canonical JSON input normalization with arbitrary nested JSON values;
- deterministic-ID part arrays and malformed lengths;
- temporal interval parsers and boundary combinations;
- graph edge collections and duplicate/malformed identifiers;
- future Arrow/Protobuf adapter validation.

Keep fuzz regression fixtures under the relevant test target. Run short smoke fuzzing separately from required stable CI because `cargo-fuzz` generally uses nightly and libFuzzer/LLVM support. Any discovered input that triggers a bug becomes a deterministic regression test before the implementation is fixed.
