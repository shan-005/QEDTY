#!/usr/bin/env bash
set -u
cd "$(dirname "${BASH_SOURCE[0]}")/.."
export PYTHONPATH="${PWD}/src${PYTHONPATH:+:${PYTHONPATH}}"
python -m compileall -q src tests || exit $?
python -m pytest -q || exit $?
python -m seraph validate || exit $?
python -m seraph demo || exit $?
