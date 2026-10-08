#!/usr/bin/env python3
"""Generate the canonical QEDTY ontology JSON Schema from Pydantic models."""

from __future__ import annotations

import json
from pathlib import Path

from qedty.ontology import (
    ONTOLOGY_PROFILE,
    WORLD_MODEL_SCHEMA,
    Assertion,
    Capability,
    Entity,
    EntityResolution,
    Flow,
    Relationship,
    Service,
    WorldEvent,
)

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "contracts" / "json-schema" / "ontology.schema.json"

MODELS = (
    ("entities", Entity),
    ("relationships", Relationship),
    ("events", WorldEvent),
    ("capabilities", Capability),
    ("services", Service),
    ("flows", Flow),
    ("assertions", Assertion),
    ("resolutions", EntityResolution),
)


def main() -> int:
    definitions: dict[str, object] = {}
    collections: dict[str, object] = {}

    for field_name, model in MODELS:
        model_schema = model.model_json_schema(ref_template="#/$defs/{model}")
        definitions.update(model_schema.get("$defs", {}))
        definitions[model.__name__] = {
            key: value for key, value in model_schema.items() if key != "$defs"
        }
        collections[field_name] = {
            "type": "array",
            "items": {"$ref": f"#/$defs/{model.__name__}"},
        }

    document: dict[str, object] = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "https://qedty.local/schema/ontology@2.0.0",
        "title": "QEDTY Ontology Document",
        "description": "Canonical interchange schema for the QEDTY ontology reference models.",
        "type": "object",
        "additionalProperties": False,
        "required": [
            "schema",
            "ontology_profile",
            "version",
            "entities",
            "relationships",
            "events",
            "capabilities",
            "services",
            "flows",
            "assertions",
            "resolutions",
        ],
        "properties": {
            "schema": {"const": WORLD_MODEL_SCHEMA},
            "ontology_profile": {"const": ONTOLOGY_PROFILE},
            "version": {"type": "integer", "minimum": 1},
            **collections,
        },
        "$defs": definitions,
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"WROTE {OUTPUT}")
    print(f"DEFINITIONS {len(definitions)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
