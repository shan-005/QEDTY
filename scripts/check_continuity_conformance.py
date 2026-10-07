from pathlib import Path
import json

ROOT=Path(__file__).resolve().parents[1]
schema=json.loads((ROOT/"contracts/json-schema/continuity-v1.json").read_text())
vectors=json.loads((ROOT/"tests/continuity_golden_vectors.json").read_text())
assert schema["$schema"].endswith("draft/2020-12/schema")
assert vectors["version"] == "1.0.0"
assert len(vectors["vectors"]) >= 2
print("Continuity schema: PASS")
print(f"Continuity golden vectors: {len(vectors['vectors'])}/{len(vectors['vectors'])} PASS")
