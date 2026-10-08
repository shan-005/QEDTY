#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

# Make the package runnable directly from the delivery tree.
ROOT = Path(__file__).resolve().parents[1]
src = ROOT / "src"
sys.path.insert(0, str(src))

from jsonschema import Draft202012Validator  # noqa: E402

from qedty.core.conformance import check_vector  # noqa: E402


def main() -> int:
    vector_dir = ROOT / "data" / "contracts" / "golden-vectors" / "core"
    schema = json.loads(
        (ROOT / "contracts" / "json-schema" / "golden-vector.schema.json").read_text(
            encoding="utf-8-sig"
        )
    )
    validator = Draft202012Validator(schema)
    files = sorted(vector_dir.glob("*.json"))
    if not files:
        print("ERROR: no golden vectors found", file=sys.stderr)
        return 2
    for path in files:
        vector = json.loads(path.read_text(encoding="utf-8-sig"))
        validator.validate(vector)
        check_vector(vector)
        print(f"PASS {path.relative_to(ROOT)}")
    print(f"PASS: {len(files)} golden vectors conform")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
