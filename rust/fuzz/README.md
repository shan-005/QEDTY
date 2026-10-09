# Fuzzing plan

The current Rust conformance executable covers three implemented API families—canonical JSON, deterministic identity, and WGS-84 ECEF conversion—with nine shared behavior cases: one canonicalization vector, one identity vector, and seven ECEF vectors. The `contract_result.json`, `quantity.json`, and `time.json` fixtures do not currently have matching Rust APIs and are not fuzz or conformance passes.

No `cargo-fuzz` target is required by the current small public surface and repository-controlled vector inputs. Add fuzz targets when there is a non-trivial parser, decoder, untrusted serialization boundary, or complex graph/scenario input surface.

Candidate targets (future):

- canonical JSON input normalization with arbitrary nested JSON values;
- deterministic-ID part arrays and malformed lengths;
- temporal interval parsers and boundary combinations;
- graph edge collections and duplicate/malformed identifiers;
- future Arrow/Protobuf adapter validation.

Keep fuzz regression fixtures under the relevant test target. Run short smoke fuzzing separately from required stable CI because `cargo-fuzz` generally uses nightly and libFuzzer/LLVM support. Any discovered input that triggers a bug becomes a deterministic regression test before the implementation is fixed.
