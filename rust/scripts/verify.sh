#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

command -v cargo >/dev/null 2>&1 || {
  echo "ERROR: cargo not found. Install the pinned rustup toolchain first." >&2
  exit 127
}
command -v uv >/dev/null 2>&1 || {
  echo "ERROR: uv not found. Install the project-pinned uv and run this gate again." >&2
  exit 127
}

# Rust checks are fail-closed: missing tools never produce a successful partial run.
cargo fmt --all -- --check
cargo test --workspace --locked
cargo clippy --workspace --all-targets --locked -- -D warnings
cargo run --locked -p qedty-conformance
# Preserve the original crate entry point as an independent compatibility gate.
cargo test --locked --manifest-path "$ROOT/crates/qedty-core/Cargo.toml"

# Reconstruct the declared Python dependency environment from the lockfile.
uv sync --locked --all-groups --all-extras
uv run pytest -q
uv run ruff check src tests scripts
uv run ruff format --check src tests scripts
uv run mypy src
uv run qedty validate
uv run python scripts/check_manifest_inventory.py
uv run qedty demo
uv run qedty scenario demo
uv run qedty impact demo

# Every domain conformance script is required, not an optional smoke test.
shopt -s nullglob
conformance_scripts=(scripts/check_*_conformance.py)
if (("${#conformance_scripts[@]}" == 0)); then
  echo "ERROR: no conformance scripts were found." >&2
  exit 1
fi
for script in "${conformance_scripts[@]}"; do
  echo "==> ${script}"
  uv run python "${script}"
done

uv lock --check
echo "PASS: Rust, Python, lockfile, and conformance gates completed."
