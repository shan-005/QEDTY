from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator

from seraph.core.conformance import check_vector

ROOT = Path(__file__).resolve().parents[2]
VECTOR_DIR = ROOT / "data" / "contracts" / "golden-vectors" / "core"
VECTOR_SCHEMA = json.loads(
    (ROOT / "contracts" / "json-schema" / "golden-vector.schema.json").read_text(encoding="utf-8")
)


def test_every_golden_vector_matches_python_reference() -> None:
    for path in sorted(VECTOR_DIR.glob("*.json")):
        vector = json.loads(path.read_text(encoding="utf-8"))
        Draft202012Validator(VECTOR_SCHEMA).validate(vector)
        check_vector(vector)
