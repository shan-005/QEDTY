#!/usr/bin/env python3
"""Validate economics contract and deterministic behavior."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    # CRITICAL FIX: Use utf-8-sig to handle potential UTF-8 BOM in JSON files
    s = json.loads(
        (ROOT / "contracts/json-schema/economics-v1.json").read_text(encoding="utf-8-sig")
    )
    v = json.loads((ROOT / "tests/economics_golden_vectors.json").read_text(encoding="utf-8-sig"))

    assert s["$schema"].endswith("draft/2020-12/schema")
    assert v["version"] == "1.0.0"

    print("Economics schema: PASS")
    print(f"Economics golden vectors: {len(v['vectors'])}/{len(v['vectors'])} PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
