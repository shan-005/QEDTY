# Rust fuzzing

The cargo-fuzz package is isolated under `rust/fuzz/` so its nightly-only
instrumentation does not change the stable workspace's MSRV.

Available targets:

- `canonical_json`: parses arbitrary JSON input and checks parse/canonicalize
  round-trip idempotence.
- `deterministic_id`: exercises deterministic identity inputs.

Run short smoke campaigns with nightly Rust, cargo-fuzz, and a Clang toolchain:

`CC=clang CXX=clang++ cargo +nightly fuzz run --fuzz-dir rust/fuzz canonical_json -- -max_total_time=30 -timeout=2 -max_len=4096`

Use the same command with `deterministic_id` for the second target. Redirect
full output to a log for review and retain diagnostic artifacts for failures.

The latest recorded smoke campaigns completed successfully. An earlier
canonical-JSON idempotence assertion was not reproduced by one-shot replay of
the saved crash inputs. Numeric regression cases now have deterministic Rust
tests. Preserve the exploratory crash artifacts for audit; do not commit
generated crash artifacts or the entire automatically generated corpus.
Only curated regression seeds belong in version control.
