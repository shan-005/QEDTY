# QEDTY Rust Core Expansion and Conformance — Completion Gates

Status: the Rust core expansion and conformance milestone is merged to main; required GitHub CI checks passed for the reviewed closeout commit.

- [x] Stable workspace tests, formatting, Clippy, and `git diff --check`.
- [x] Rust 1.78 workspace tests and benchmark compilation.
- [x] Shared Rust graph/spatial golden-vector tests and Python graph tests that
  consume the same expected fixture values.
- [x] Canonical-JSON numeric regression tests for reported idempotence cases.
- [x] Latest smoke fuzz campaigns for `canonical_json` and `deterministic_id`.
      Earlier saved crash artifacts did not reproduce during one-shot replay and
      are retained locally for audit.
- [x] Arrow IPC stream round-trip between Rust and PyArrow, checking nulls,
  UTC millisecond timestamps, values and schema metadata.
- [x] Initial six-workload Criterion baseline, provenance report and raw archive.
      No comparative speedup is claimed.
- [x] ADR-0003 accepted: native Python bindings are deferred until stable APIs,
  conformance evidence and a demonstrated need justify a separate packaging change.
- [x] Project manifest and inventory validation in the local staged candidate.
- [x] Reviewed commit merged; required GitHub Actions checks passed.

The tests are deterministic shared-vector checks, not exhaustive randomized
differential coverage of every Python and Rust graph/spatial behavior. Arrow
support currently uses IPC streams for the supported column types; it is not a
zero-copy Arrow C Data Interface.

These gates were satisfied for the reviewed closeout commit. Re-run the required checks for subsequent changes. Do not claim production certification or a Rust speedup from this work alone.
