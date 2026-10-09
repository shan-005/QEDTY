#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

command -v cargo >/dev/null 2>&1 || {
  echo "ERROR: cargo not found. Install the repository's rustup toolchain first." >&2
  exit 127
}

cargo fmt --all -- --check
cargo test --workspace --locked
cargo clippy --workspace --all-targets --locked -- -D warnings
cargo run --locked -p qedty-conformance

# Preserve the repository's original native test entry point as a compatibility gate.
cargo test --locked --manifest-path "$ROOT/crates/qedty-core/Cargo.toml"

# Keep the current Python semantic/reference gates in the verification loop.
if command -v uv >/dev/null 2>&1; then
  uv run python scripts/check_core_conformance.py
  uv run pytest -q
else
  echo "NOTE: uv not found; skipped Python checks. Run them with the project's uv environment." >&2
fi
