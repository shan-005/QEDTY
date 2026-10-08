#!/usr/bin/env bash
set -u
cd "$(dirname "${BASH_SOURCE[0]}")/.."
export PATH="$HOME/.local/bin:$PATH"
uv lock || exit $?
uv sync --all-groups --all-extras || exit $?
uv run qedty validate || exit $?
uv run pytest -q || exit $?
