#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."

uv sync --locked --all-groups --all-extras
export PYTHONPATH="${PWD}/src${PYTHONPATH:+:${PYTHONPATH}}"

uv run python -m compileall -q src tests
uv run pytest -q --cov-fail-under=60
uv run ruff check src tests scripts
uv run ruff format --check src tests scripts
uv run mypy src
uv run qedty validate
uv run qedty demo
uv run qedty scenario demo
uv run qedty impact demo
uv run python scripts/check_manifest_inventory.py
uv run python scripts/check_manifest_names.py --check

for script in scripts/check_*_conformance.py; do
    echo "==> ${script}"
    uv run python "${script}"
done

cargo test --manifest-path crates/qedty-core/Cargo.toml
uv lock --check
