# Rust benchmark policy

No performance benchmark is checked in yet because the current core has only canonicalization, identity, and one ECEF conversion. A benchmark suite is added when a kernel and realistic workload exist.

Recommended first benchmark targets after correctness baselines:

- canonical JSON/hash across representative nested object sizes;
- deterministic identity for realistic part counts;
- ECEF conversion over representative batch sizes, with the baseline vector retained;
- graph traversal after deterministic graph primitives exist;
- temporal interval query after interval semantics and index choices exist.

Use Criterion in `--release`, preserve the input seed/data-size metadata, record CPU/toolchain/target/features, and compare same-machine runs. Do not put unstable microbenchmark numbers into product documentation. Establish an initial baseline before defining regression limits.
