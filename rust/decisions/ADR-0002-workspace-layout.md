# ADR-0002: Keep the existing core path and introduce one root Cargo workspace

- **Status:** Proposed for review in this bundle
- **Decision:** Keep production core source at `crates/qedty-core/`; add a root Cargo workspace containing that crate and the conformance CLI under `rust/crates/`.
- **Context:** The repository already tests `crates/qedty-core/Cargo.toml` from CI and has tests that reference fixtures by that path. Moving the core into `rust/crates/qedty-core` would require coordinated source, test, docs, CI, and lockfile changes while providing no immediate semantic or performance value.
- **Consequences:** root `Cargo.toml` and `Cargo.lock` are the workspace boundary; `crates/qedty-core/Cargo.lock` becomes redundant when the root lock is verified and can be removed in a separate cleanup. The new `rust/` area contains Rust tooling, docs, conformance and later bounded targets, rather than a second copy of core.
- **Review requirement:** run the full test and package jobs before merge. Reconsider only if a repository-wide native layout migration has a concrete payoff.
