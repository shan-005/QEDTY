#!/usr/bin/env bash
set -euo pipefail

REPO=${1:-.}
ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)

cd "$REPO"
[[ -d src/seraph ]] || { echo 'ERROR: not a Seraph repository: src/seraph missing' >&2; exit 2; }

mkdir -p src/seraph/core contracts/json-schema contracts/arrow proto/seraph/core/v1 crates/seraph-core/src crates/seraph-core/tests tests/conformance data/contracts/golden-vectors/core scripts
cp -a "$ROOT/src/seraph/core/." src/seraph/core/
cp -a "$ROOT/contracts/json-schema/." contracts/json-schema/
cp -a "$ROOT/contracts/arrow/." contracts/arrow/
cp -a "$ROOT/proto/seraph/core/v1/." proto/seraph/core/v1/
cp -a "$ROOT/crates/seraph-core/." crates/seraph-core/
cp -a "$ROOT/tests/conformance/." tests/conformance/
cp -a "$ROOT/data/contracts/golden-vectors/core/." data/contracts/golden-vectors/core/
cp -a "$ROOT/scripts/check_core_conformance.py" scripts/

printf '%s\n' 'SERAPH-PCI-X Core final contract layer installed.'
printf '%s\n' 'Run the repository test/lint/typecheck suite before committing.'
