from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = ROOT / "contracts/qedty/economics/currency-v2.1.json"


def test_currency_v21_schema_and_multi_hop_request() -> None:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)

    request = {
        "schema_version": "2.1",
        "source": {
            "amount": "10.00",
            "currency_code": "AAA",
            "metadata_profile_version": "profile-1",
        },
        "target_currency_code": "CCC",
        "currency_profile": {
            "profile_version": "profile-1",
            "currencies": [
                {
                    "currency_code": code,
                    "minor_unit_scale": 2,
                    "rounding_mode": "ROUND_HALF_EVEN",
                }
                for code in ("AAA", "BBB", "CCC")
            ],
        },
        "fx_snapshot": {
            "snapshot_id": "snapshot-1",
            "as_of": "2026-01-02T00:00:00Z",
            "valid_from": "2026-01-01T00:00:00Z",
            "valid_to": "2026-01-03T00:00:00Z",
            "rates": [
                {
                    "base_currency": "AAA",
                    "quote_currency": "BBB",
                    "rate": "2",
                    "spread_bps": 25,
                    "fee_bps": 10,
                    "observed_at": "2026-01-01T00:00:00Z",
                    "source": "fixture",
                    "provenance_id": "fixture:AAA/BBB",
                },
                {
                    "base_currency": "BBB",
                    "quote_currency": "CCC",
                    "rate": "3",
                    "observed_at": "2026-01-01T00:00:00Z",
                    "source": "fixture",
                    "provenance_id": "fixture:BBB/CCC",
                },
            ],
        },
    }
    Draft202012Validator(schema).validate(request)
