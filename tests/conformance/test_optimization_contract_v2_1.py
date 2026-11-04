from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, ValidationError

ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = ROOT / "contracts/qedty/optimization/optimization-v2.1.json"
FIXTURE_PATH = ROOT / "data/contracts/differential/cases/portfolio_v2_1_fx_path.json"
RESILIENCE_FIXTURE_PATH = (
    ROOT / "data/contracts/differential/cases/portfolio_v2_1_resilience_gain.json"
)
POLICY = "fewest_hops_then_lexicographic_currency_path"


def load_schema() -> dict[str, object]:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def fragment(schema: dict[str, object], definition: str) -> dict[str, object]:
    return {
        "$schema": schema["$schema"],
        "$defs": schema["$defs"],
        "$ref": f"#/$defs/{definition}",
    }


def valid_leg() -> dict[str, object]:
    return {
        "source_currency": "AAA",
        "target_currency": "BBB",
        "rate_base_currency": "AAA",
        "rate_quote_currency": "BBB",
        "rate": "3",
        "rate_was_inverted": False,
        "spread_bps": 200,
        "fee_bps": 100,
        "applied_rate": "2.9403",
        "fx_source": "fixture-market-c",
        "fx_provenance_id": "fixture:AAA/BBB",
    }


def valid_conversion() -> dict[str, object]:
    money_source = {
        "amount": "1.00",
        "currency_code": "AAA",
        "metadata_profile_version": "portfolio-fx-v21",
    }
    money_target = {
        "amount": "11.64",
        "currency_code": "DDD",
        "metadata_profile_version": "portfolio-fx-v21",
    }
    second_leg = valid_leg()
    second_leg.update(
        {
            "source_currency": "BBB",
            "target_currency": "DDD",
            "rate_base_currency": "BBB",
            "rate_quote_currency": "DDD",
            "rate": "4",
            "spread_bps": 100,
            "fee_bps": 50,
            "applied_rate": "3.9601",
            "fx_source": "fixture-market-d",
            "fx_provenance_id": "fixture:BBB/DDD",
        }
    )
    return {
        "source": money_source,
        "target": money_target,
        "applied_rate": "11.64388203",
        "unrounded_target_amount": "11.64388203",
        "rounding_mode": "ROUND_HALF_EVEN",
        "metadata_profile_version": "portfolio-fx-v21",
        "fx_snapshot_id": "fx-portfolio-v21-cross-language",
        "rate_base_currency": "AAA",
        "rate_quote_currency": "BBB",
        "rate_was_inverted": False,
        "fx_source": "fixture-market-c",
        "fx_provenance_id": "fixture:AAA/BBB",
        "effective_at": "2026-01-02T00:00:00Z",
        "fx_snapshot_as_of": "2026-01-02T00:00:00Z",
        "calculation_precision": 34,
        "fx_path": [valid_leg(), second_leg],
        "fx_path_policy": POLICY,
    }


def test_portfolio_v21_schema_and_differential_fixture_are_valid() -> None:
    schema = load_schema()
    Draft202012Validator.check_schema(schema)
    document = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    request = document["cases"][0]["input"]
    Draft202012Validator(schema).validate(request)


def test_portfolio_v21_fx_path_conversion_audit_is_valid() -> None:
    schema = load_schema()
    conversion_schema = fragment(schema, "MoneyConversionV2")
    Draft202012Validator(conversion_schema).validate(valid_conversion())


def test_portfolio_v21_requires_path_for_cross_currency_conversion() -> None:
    schema = load_schema()
    conversion = valid_conversion()
    del conversion["fx_path"]
    del conversion["fx_path_policy"]

    with pytest.raises(ValidationError):
        Draft202012Validator(fragment(schema, "MoneyConversionV2")).validate(conversion)


def test_portfolio_v21_rejects_out_of_range_basis_points() -> None:
    schema = load_schema()
    rate_schema = fragment(schema, "FxRate")
    rate = {
        "base_currency": "AAA",
        "quote_currency": "BBB",
        "rate": "2",
        "observed_at": "2026-01-01T00:00:00Z",
        "source": "fixture",
        "provenance_id": "fixture:AAA/BBB",
        "spread_bps": 20000,
        "fee_bps": 0,
    }
    with pytest.raises(ValidationError):
        Draft202012Validator(rate_schema).validate(rate)

    rate["spread_bps"] = 0
    rate["fee_bps"] = 10000
    with pytest.raises(ValidationError):
        Draft202012Validator(rate_schema).validate(rate)


def test_portfolio_v21_request_and_result_are_version_pinned() -> None:
    schema = load_schema()
    definitions = schema["$defs"]
    assert (
        definitions["PortfolioOptimizationRequestV2"]["properties"]["schema_version"]["const"]
        == "2.1"
    )
    assert (
        definitions["PortfolioOptimizationResultV2"]["properties"]["schema_version"]["const"]
        == "2.1"
    )



def test_portfolio_v21_resilience_gain_is_versioned_and_schema_valid() -> None:
    schema = load_schema()
    kinds = schema["$defs"]["PortfolioObjectiveV2"]["properties"]["kind"]["enum"]
    assert "resilience_gain" in kinds
    document = json.loads(RESILIENCE_FIXTURE_PATH.read_text(encoding="utf-8"))
    request = document["cases"][0]["input"]
    assert request["schema_version"] == "2.1"
    assert request["objective"]["kind"] == "resilience_gain"
    Draft202012Validator(schema).validate(request)
