from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator, ValidationError

ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = ROOT / "contracts" / "qedty" / "optimization" / "optimization-v2.json"


def load_schema() -> dict[str, object]:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def valid_request() -> dict[str, object]:
    return {
        "schema_version": "2.0",
        "budget": {
            "amount": "100.00",
            "currency_code": "BBB",
            "metadata_profile_version": "fixture-v1",
        },
        "currency_profile": {
            "profile_version": "fixture-v1",
            "currencies": [
                {
                    "currency_code": "AAA",
                    "minor_unit_scale": 2,
                    "rounding_mode": "ROUND_HALF_EVEN",
                },
                {
                    "currency_code": "BBB",
                    "minor_unit_scale": 2,
                    "rounding_mode": "ROUND_HALF_UP",
                },
            ],
        },
        "candidates": [
            {
                "intervention_id": "bridge-1",
                "cost": {
                    "amount": "40.00",
                    "currency_code": "AAA",
                    "metadata_profile_version": "fixture-v1",
                },
                "continuity_gain": "12.5",
                "risk_score": "0.2",
                "scenario_scores": ["10.0", "-1.5"],
                "rationale": "fixed reference fixture",
            }
        ],
        "objective": {
            "kind": "weighted_score",
            "gain_weight": "1",
            "cost_weight": "1",
            "risk_weight": "1",
            "cvar_alpha": "0.9",
        },
        "fx_snapshot": {
            "snapshot_id": "fixture-fx",
            "as_of": "2026-01-02T00:00:00Z",
            "valid_from": "2026-01-01T00:00:00Z",
            "valid_to": "2026-01-03T00:00:00Z",
            "rates": [
                {
                    "base_currency": "AAA",
                    "quote_currency": "BBB",
                    "rate": "2",
                    "observed_at": "2026-01-01T00:00:00Z",
                    "source": "independent-fixture",
                    "provenance_id": "fixture:AAA/BBB",
                }
            ],
        },
        "fixed_overhead": {
            "amount": "1.00",
            "currency_code": "BBB",
            "metadata_profile_version": "fixture-v1",
        },
        "scenario_ids": ["optimistic", "stress"],
    }


def test_portfolio_v2_schema_and_request_are_valid() -> None:
    schema = load_schema()
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(valid_request())


def test_portfolio_v2_contract_rejects_implicit_float_money() -> None:
    request = valid_request()
    budget = request["budget"]
    assert isinstance(budget, dict)
    budget["amount"] = 100.0
    errors = list(Draft202012Validator(load_schema()).iter_errors(request))
    assert any(error.json_path == "$.budget.amount" for error in errors)


def test_portfolio_v2_contract_rejects_unversioned_fx_rate_or_unknown_request_fields() -> None:
    request = valid_request()
    snapshot = request["fx_snapshot"]
    assert isinstance(snapshot, dict)
    rates = snapshot["rates"]
    assert isinstance(rates, list)
    rate = rates[0]
    assert isinstance(rate, dict)
    rate["rate"] = "0"
    errors = list(Draft202012Validator(load_schema()).iter_errors(request))
    assert any(error.json_path == "$.fx_snapshot.rates[0].rate" for error in errors)

    request = valid_request()
    request["allow_live_fx_fetch"] = True
    try:
        Draft202012Validator(load_schema()).validate(request)
    except ValidationError:
        pass
    else:
        raise AssertionError("unknown request fields must be rejected")


def test_portfolio_v2_result_schema_accepts_solver_status_and_conversion_provenance() -> None:
    schema = load_schema()
    result_schema = {
        "$schema": schema["$schema"],
        "$defs": schema["$defs"],
        "$ref": "#/$defs/PortfolioOptimizationResultV2",
    }
    money = {
        "amount": "40.00",
        "currency_code": "BBB",
        "metadata_profile_version": "fixture-v1",
    }
    conversion = {
        "source": {
            "amount": "20.00",
            "currency_code": "AAA",
            "metadata_profile_version": "fixture-v1",
        },
        "target": money,
        "applied_rate": "2",
        "unrounded_target_amount": "40.00",
        "rounding_mode": "ROUND_HALF_UP",
        "metadata_profile_version": "fixture-v1",
        "fx_snapshot_id": "fixture-fx",
        "rate_base_currency": "AAA",
        "rate_quote_currency": "BBB",
        "rate_was_inverted": False,
        "fx_source": "independent-fixture",
        "fx_provenance_id": "fixture:AAA/BBB",
        "effective_at": "2026-01-02T00:00:00Z",
        "fx_snapshot_as_of": "2026-01-02T00:00:00Z",
        "calculation_precision": 34,
    }
    result = {
        "schema_version": "2.0",
        "status": "optimal",
        "solver_mode": "exact_branch_and_bound",
        "objective_kind": "weighted_score",
        "reporting_currency_code": "BBB",
        "budget": {
            "amount": "100.00",
            "currency_code": "BBB",
            "metadata_profile_version": "fixture-v1",
        },
        "fixed_overhead": {
            "amount": "1.00",
            "currency_code": "BBB",
            "metadata_profile_version": "fixture-v1",
        },
        "spent": money,
        "total_committed": {
            "amount": "41.00",
            "currency_code": "BBB",
            "metadata_profile_version": "fixture-v1",
        },
        "selected_intervention_ids": ["bridge-1"],
        "recommendations": [
            {
                "intervention_id": "bridge-1",
                "source_cost": conversion["source"],
                "reporting_cost": money,
                "continuity_gain": "12.5",
                "risk_score": "0.2",
                "scenario_scores": ["10", "-1.5"],
                "robust_score": "-1.5",
                "efficiency": "312500",
                "utility": "12.45996",
                "selected": True,
                "rationale": "fixed reference fixture",
                "conversion": conversion,
            }
        ],
        "objective_value": "12.45996",
        "portfolio_robust_floor": "-1.5",
        "portfolio_cvar": "-1.5",
        "dominance_score": "1",
        "scenario_ids": ["optimistic", "stress"],
        "solver_nodes": 8,
        "fx_snapshot_id": "fixture-fx",
        "digest": "a" * 64,
    }
    Draft202012Validator(result_schema).validate(result)
