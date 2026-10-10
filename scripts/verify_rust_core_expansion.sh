#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

printf '\n== Rust formatting ==\n'
cargo fmt --all -- --check
printf '\n== Rust workspace tests ==\n'
cargo test --workspace --locked
printf '\n== Rust Clippy ==\n'
cargo clippy --workspace --all-targets --locked -- -D warnings
printf '\n== Shared Rust conformance ==\n'
cargo run --bin qedty-conformance --locked -p qedty-conformance
printf '\n== Expanded graph/spatial conformance ==\n'
cargo run --locked -p qedty-conformance --bin rust-expansion-conformance
printf '\n== Python core conformance ==\n'
uv run python scripts/check_core_conformance.py
uv run python scripts/check_graph_conformance.py
printf '\n== Full Python suite ==\n'
uv run pytest -q
printf '\nPASS: local Rust and Python verification commands completed.\n'
