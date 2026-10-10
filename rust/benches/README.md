# Rust benchmark policy

Criterion benchmarks live under `crates/qedty-core/benches/` and are built
with the workspace's supported toolchains.

Run the suite with:

`cargo bench --locked -p qedty-core --bench core`

The initial Rust core expansion/conformance benchmark records six workloads:
canonical JSON, deterministic identity, WGS-84 ECEF conversion, quantity
conversion, graph shortest path, and columnar JSON-row conversion.

The provenance report and raw Criterion baseline archive are retained under
`rust/benches/results/`. Each report identifies the commit, working-tree
fingerprint, CPU, compiler, target and command used. Full local execution logs
remain outside the repository.

These results establish a reproducible initial baseline; they do not establish
a speedup. Performance comparisons must use a comparable workload on a
comparable machine and toolchain before regression thresholds are defined.
