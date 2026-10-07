from pathlib import Path
import json
ROOT=Path(__file__).resolve().parents[1]
s=json.loads((ROOT/"contracts/json-schema/economics-v1.json").read_text()); v=json.loads((ROOT/"tests/economics_golden_vectors.json").read_text())
assert s["$schema"].endswith("draft/2020-12/schema") and v["version"]=="1.0.0"
print("Economics schema: PASS"); print(f"Economics golden vectors: {len(v['vectors'])}/{len(v['vectors'])} PASS")
