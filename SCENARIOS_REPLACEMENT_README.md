# SERAPH-PCI-X Scenarios replacement

Target: `src/seraph/scenarios/`

Contract: `seraph-scenarios@1.0.0`

## Existing files replaced

- `__init__.py`
- `diff.py`
- `engine.py`
- `interventions.py`
- `models.py`
- `shocks.py`
- `state.py`

## Additional contract/test artifacts

- `schema.py`
- `arrow.py`
- `tests/test_scenarios.py`
- `tests/scenarios_golden_vectors.json`
- `scripts/check_scenarios_conformance.py`
- `contracts/json-schema/scenario-v1.json`
- `contracts/arrow/schema.json`
- `proto/seraph/scenarios/v1/scenarios.proto`
- `contracts/rdf/scenario.ttl`
- `contracts/shacl/scenario.shacl.ttl`
- `docs/scenarios/RESEARCH_BASELINE.md`
- `docs/scenarios/CONTRACT_COVERAGE.md`
- `data/contracts/golden-vectors/scenarios/*.json`

## Compatibility notes

The legacy `Scenario.parameters` and `Scenario.capacities` surfaces are retained. Parameters are applied as capacity multipliers; capacities are absolute overrides. `intervention_map()` remains compatible with the existing counterfactual engine. `Shock.normalized()` remains available.

## Validation performed in the isolated reference harness

- Python Scenarios tests: 17/17 PASS
- Golden vectors: 8/8 PASS
- Conformance runner: PASS
- Python compileall: PASS

The repository's own locked Ruff/mypy versions must still be run after installation because the isolated harness does not contain the complete repository environment.
