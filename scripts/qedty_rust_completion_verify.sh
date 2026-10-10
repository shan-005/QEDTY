#!/usr/bin/env bash
set -Eeuo pipefail

REPO="${1:-$HOME/qedty}"
LOG_DIR="${QEDTY_RUST_LOG_DIR:-$HOME/qedty-rust-completion-logs}"
mkdir -p "$LOG_DIR"
if [[ ! -d "$REPO/.git" ]]; then
  echo "STOP: not a Git repository: $REPO" >&2
  exit 2
fi
cd "$REPO"

run() {
  local name="$1"; shift
  local log="$LOG_DIR/$name.log"
  echo
  echo "========== $name =========="
  echo "COMMAND: $*"
  if "$@" 2>&1 | tee "$log"; then
    echo "PASS: $name"
  else
    local rc=${PIPESTATUS[0]}
    echo "FAIL: $name (exit $rc; log: $log)" >&2
    return "$rc"
  fi
}

echo "Repository: $REPO"
echo "HEAD: $(git rev-parse HEAD)"
echo "Logs: $LOG_DIR"

run cargo_metadata cargo metadata --locked --format-version 1
run cargo_fmt cargo fmt --all -- --check
run cargo_test_locked cargo test --workspace --locked
run cargo_clippy cargo clippy --workspace --all-targets --locked -- -D warnings
run rust_conformance cargo run --locked -p qedty-conformance --bin qedty-conformance
run rust_expansion_conformance cargo run --locked -p qedty-conformance --bin rust-expansion-conformance
run rust_msrv cargo +1.78.0 test --workspace --locked
run manifest_inventory python3 scripts/check_manifest_inventory.py
run diff_check git diff --check

if command -v uv >/dev/null 2>&1; then
  run python_tests uv run --frozen pytest -q
else
  echo "SKIP: Python tests; uv not installed. Run the repository's documented Python test command."
fi

echo
echo "========== RESULT =========="
echo "All commands executed by this script passed."
echo "This result does NOT imply Arrow, benchmarks, fuzzing, or broad differential gates are complete unless their implementation and evidence are present."
echo "Review logs under: $LOG_DIR"
