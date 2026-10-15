from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, ValidationError

ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = ROOT / "contracts" / "qedty" / "economics" / "currency-v2.json"


def load_schema() -> dict[str, object]:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def valid_request() -> dict[str, object]:
    return {
        "schema_version": "2.0",
        "source": {
            "amount": "10.00",
            "currency_code": "AAA",
            "metadata_profile_version": "fixture-v1",
        },
        "target_currency_code": "BBB",
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
        "fx_snapshot": {
            "snapshot_id": "fx-fixture-1",
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
    }


def test_currency_v2_schema_is_valid() -> None:
    Draft202012Validator.check_schema(load_schema())


def test_currency_v2_direct_conversion_request_matches_schema() -> None:
    Draft202012Validator(load_schema()).validate(valid_request())


def test_currency_v2_contract_rejects_binary_float_amounts() -> None:
    request = valid_request()
    source = request["source"]
    assert isinstance(source, dict)
    source["amount"] = 10.0
    errors = list(Draft202012Validator(load_schema()).iter_errors(request))
    assert any(error.json_path == "$.source.amount" for error in errors)


def test_currency_v2_contract_rejects_unknown_fields() -> None:
    request = valid_request()
    request["implicit_live_fx_fetch"] = True
    with pytest.raises(ValidationError):
        Draft202012Validator(load_schema()).validate(request)
