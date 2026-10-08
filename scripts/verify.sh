#!/usr/bin/env bash
set -u
cd "$(dirname "${BASH_SOURCE[0]}")/.."
export PYTHONPATH="${PWD}/src${PYTHONPATH:+:${PYTHONPATH}}"
python -m compileall -q src tests || exit $?
python -m pytest -q || exit $?
python -m qedty validate || exit $?
python -m qedty demo || exit $?
