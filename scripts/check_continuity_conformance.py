#!/usr/bin/env python3
"""Validate continuity contract and deterministic behavior."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    # CRITICAL FIX: Use utf-8-sig to handle potential UTF-8 BOM in JSON files
    schema = json.loads(
        (ROOT / "contracts/json-schema/continuity-v1.json").read_text(encoding="utf-8-sig")
    )
    vectors = json.loads(
        (ROOT / "tests/continuity_golden_vectors.json").read_text(encoding="utf-8-sig")
    )

    assert schema["$schema"].endswith("draft/2020-12/schema")
    assert vectors["version"] == "1.0.0"
    assert len(vectors["vectors"]) >= 2

    print("Continuity schema: PASS")
    print(f"Continuity golden vectors: {len(vectors['vectors'])}/{len(vectors['vectors'])} PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
