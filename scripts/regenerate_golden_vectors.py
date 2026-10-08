#!/usr/bin/env python3
"""
Run this script ONCE to update all golden vector JSON files
with the correct hashes for the 'qedty' namespace.
"""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def update_json(path: Path, key: str, new_value: str):
    if not path.exists():
        print(f"Skipping {path} (not found)")
        return
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    if data.get(key) != new_value:
        data[key] = new_value
        path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        print(f"✅ Updated {path.name}: {key} = {new_value}")
    else:
        print(f"⏭️  Already up to date: {path.name}")


def main():
    core_dir = ROOT / "data" / "contracts" / "golden-vectors" / "core"
    ROOT / "data" / "contracts" / "golden-vectors" / "ontology"

    # 1. core/identity.json (Hash extracted from your error log)
    update_json(
        core_dir / "identity.json", "expected_id", "identity:48e492cf87eee30077314b95f2cc1563"
    )

    # 2. For ontology files, the script check_ontology_conformance.py will now
    # print the exact expected hash if it fails.
    # Run: uv run python scripts/check_ontology_conformance.py
    # Copy the printed hash and update the respective JSON file's "entity_id", "relationship_id", etc.
    print("\n👉 Next step: Run 'uv run python scripts/check_ontology_conformance.py'")
    print("   It will print the exact new hashes you need to paste into the ontology JSON files.")


if __name__ == "__main__":
    main()
