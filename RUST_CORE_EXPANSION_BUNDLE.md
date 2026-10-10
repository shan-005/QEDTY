# QEDTY Rust Core Expansion Bundle

This archive is a **repository-relative overlay** for the QEDTY checkout. It is
not a full repository archive: existing Rust, Python reference, contracts,
fixtures, Cargo files, lockfiles, policies, workflows and other project assets
must remain in place.

## Reviewed baseline

The overlay was prepared against `main` commit
`d68af5e31e0707256c0834c139f710eefc961e2f`. The local installer refuses to run
against another `HEAD` or if tracked files already have modifications.

## Safe application

1. Extract this ZIP directly into the repository root, preserving paths.
2. Run `python3 scripts/install_rust_core_expansion.py` from the root.
3. Review `git diff --check` and `git diff`.
4. Run `bash scripts/verify_rust_core_expansion.sh`.
5. Only after reviewing results, stage/commit/push through your own normal GitHub workflow.

The installer only edits local working-tree files. It creates no branch, commit,
pull request, push, or GitHub change. It updates `lib.rs`, wires the existing
quantity and contract-result fixtures into the primary Rust conformance CLI,
adds a separate extended conformance executable, wires it into the existing Rust
CI workflow and verification script, refreshes Rust documentation, and recalculates
`QEDTY-PROJECT-MANIFEST.json` for the overlay's new paths.

## Included implementation families

- Dimension-checked unit conversion for a declared, bounded SI/UCUM-like unit
  registry, with Celsius affine-unit safeguards.
- Contract-result normalization with deterministic evidence/provenance/assumption
  lists and UTC timestamp canonicalization.
- Allen interval relations, bitemporal membership, and sorted timeline queries.
- Checked inverse WGS-84 ECEF conversion.
- A deterministic grid-based point-radius index, using a spherical mean-Earth
  distance for filtering.
- Ordered directed-graph traversal, additive shortest path, maximum-product
  reliability path, components, PageRank, and maximum flow.
- Pure numeric kernels for weighted means, interval uncertainty, continuity
  scores, bounded propagation and 0/1 knapsack selection.
- An Arrow-neutral typed columnar batch seam with null preservation and row
  conversion to JSON.
- Shared-vector and graph-scenario conformance tests plus local verification
  commands for Rust and Python.

## Important scope limits

This is a substantial implementation overlay, **not evidence by itself that the
entire Rust roadmap is complete**. The quantity kernel uses `f64` while Python
uses `Decimal`, so only the exact fixtures and explicitly bounded arithmetic
have parity coverage; it does not claim arbitrary-precision Decimal equivalence.
The columnar module is intentionally **not** Arrow IPC, Arrow C Data Interface,
or PyArrow integration. The bundle does not add a PyO3/maturin extension or
change the Python build backend. It also does not claim that release-mode
Criterion baselines, memory profiling, cargo-fuzz campaigns, or full Python/Rust
differential/property coverage have run. Those are evidence and packaging gates,
not files that should be marked complete by documentation alone.

The container used to prepare this archive did not have `cargo`, `rustc`, or
`rustfmt`, so Rust compilation, Rust formatting checks, Clippy, and the test
suite have **not** been represented as passing here. Run the provided verifier
on your QEDTY development machine; any compiler or test failure must be fixed
before merging this overlay.


## Local compile fixes

The corrected bundle version adds three compile fixes found by the first actual
workspace build: import `format_value` into the quantity unit tests, import
`haversine_m` into spatial index tests, and clone the empty knapsack state when
initializing the dynamic-programming vector so it remains available as fallback.
These are source-level fixes; they are not represented as a successful compiler run
until the recipient runs `cargo test --workspace --locked`.
