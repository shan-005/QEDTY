# Rust quality and release gates

## Required on every change

- `cargo fmt --all -- --check`
- `cargo test --workspace --locked`
- `cargo clippy --workspace --all-targets --locked -- -D warnings`
- `cargo run --locked -p qedty-conformance`
- Python core conformance and existing Python unit suite in the repository's established CI.
- No unrelated changes to Python dependencies or `pyproject.toml` in a Rust-only PR.

## Domain-specific before merge

- Unit tests for nominal cases, boundaries, invalid input, and typed errors.
- Golden-vector tests for each implemented behavior.
- Property tests for mathematical/invariant guarantees where suitable.
- Python differential tests for any kernel whose semantics exist in Python.
- Fuzzing for complex/untrusted input boundaries when applicable.
- Release-mode benchmark and memory/allocation notes for performance-oriented changes.
- `cargo tree -d` review when dependency versions duplicate unexpectedly.
- Security/advisory and license checks once dependency-policy configuration is adopted.

## Performance acceptance

- Benchmark with `--release` and a controlled workload.
- Record compiler/toolchain, target triple, CPU, feature flags, data size, warm-up, sampling configuration, and commit SHA.
- Compare on the same machine or equivalent runner; don't compare debug and release builds.
- Use statistical analysis (Criterion) and profile results; a single fastest sample is not evidence.
- Keep baseline outputs as artifacts, but avoid treating cross-machine raw timings as directly comparable.
- Do not require a numeric speedup before a baseline exists. First establish correctness and trustworthy measurements.

## Safety / determinism gates

- No unreviewed `unsafe` blocks.
- No silent fallback to zeros/default values for invalid input.
- No panic path reachable from expected user-supplied data.
- No unordered result emission where stable output affects identities, hashes, test vectors or API clients.
- No silent changes to tolerance, units, epistemic state, temporal inclusivity, or identity profile.
- Dependency license/MSRV/advisory changes documented in PR.
