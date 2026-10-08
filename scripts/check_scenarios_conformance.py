#!/usr/bin/env python3
"""Validate the normative Scenarios golden vector suite."""

from __future__ import annotations

import json
from pathlib import Path

from qedty.scenarios.engine import apply_scenario
from qedty.scenarios.models import Scenario
from qedty.scenarios.state import ScenarioState

ROOT = Path(__file__).resolve().parents[1]
VECTORS = ROOT / "tests" / "scenarios_golden_vectors.json"


def main() -> int:
    # CRITICAL FIX: Use utf-8-sig to handle potential UTF-8 BOM in JSON files
    payload = json.loads(VECTORS.read_text(encoding="utf-8-sig"))
    assert payload["contract_version"] == "qedty-scenarios@1.0.0"
    assert len(payload["vectors"]) == 8
    for vector in payload["vectors"]:
        scenario = Scenario.model_validate(vector["scenario"], strict=False)
        base = ScenarioState(capacities=vector["base_state"]["capacities"])
        result = apply_scenario(base, scenario, at=scenario.valid_from)
        assert result.capacities == vector["expected"]["capacities"]
        assert result.transmission_reductions == vector["expected"]["transmission_reductions"]
        assert result.digest == vector["expected"]["digest"]
    print("Scenario schema: PASS")
    print("Scenario patches: PASS")
    print("Scenario shock semantics: PASS")
    print("Scenario intervention semantics: PASS")
    print("Scenario deterministic digest: PASS")
    print("Scenario golden vectors: 8/8 PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
