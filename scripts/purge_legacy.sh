#!/usr/bin/env bash
set -u
cd "$(dirname "${BASH_SOURCE[0]}")/.."
rm -rf src/qedty/guard src/qedty/sources/repository
find src tests -type f \( -name '*.pyc' -o -name '*.pyo' \) -delete 2>/dev/null || true
