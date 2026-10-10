#!/usr/bin/env bash
set -Eeuo pipefail

REPO="${1:-$HOME/qedty}"
if [[ ! -d "$REPO/.git" ]]; then
  echo "STOP: not a Git repository: $REPO" >&2
  exit 2
fi
cd "$REPO"

echo "========== QEDTY RUST COMPLETION PREFLIGHT =========="
printf 'Repository: %s\n' "$REPO"
printf 'HEAD: '; git rev-parse HEAD
printf 'Branch: '; git branch --show-current
printf '\n-- Git status (no changes made) --\n'
git status --short
printf '\n-- Required current files --\n'
for path in \
  Cargo.toml Cargo.lock rust-toolchain.toml \
  crates/qedty-core/Cargo.toml crates/qedty-core/src/lib.rs \
  crates/qedty-core/src/columnar.rs crates/qedty-core/tests/rust_expansion.rs \
  rust/CONFORMANCE.md rust/RUST_PLAN.md rust/decisions/ADR-0003-python-binding-timing.md \
  .github/workflows/rust.yml scripts/check_manifest_inventory.py QEDTY-PROJECT-MANIFEST.json
do
  if [[ -f "$path" ]]; then printf 'OK      %s\n' "$path"; else printf 'MISSING %s\n' "$path"; fi
done

printf '\n-- Current Rust module files --\n'
for path in columnar compute contract_result geodesy geometry graph quantity spatial temporal temporal_relations; do
  if [[ -f "crates/qedty-core/src/$path.rs" ]]; then
    printf 'OK      crates/qedty-core/src/%s.rs\n' "$path"
  else
    printf 'MISSING crates/qedty-core/src/%s.rs\n' "$path"
  fi
done

printf '\n-- Relevant completion gaps (manual evidence still required) --\n'
printf '%s\n' \
  '1. Broad Python/Rust differential execution and invalid-input comparisons' \
  '2. Actual Arrow RecordBatch interoperability and Python round-trip' \
  '3. Criterion benchmark runs and measured baseline evidence' \
  '4. Property/fuzz strategy with actual recorded runs' \
  '5. Reviewed ADR-0003 binding decision' \
  '6. Manifest and exact-final-SHA CI verification'
echo "Preflight is inventory only; it does not claim these gates passed."
