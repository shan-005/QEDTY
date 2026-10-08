"""Language-neutral Propagation contract metadata."""

from __future__ import annotations

from typing import Any

from .models import PropagationEvent, PropagationResult, PropagationSummary
from .rules import PropagationRule

NAME = "qedty-propagation"
VERSION = "1.0.0"
KEY = f"{NAME}@{VERSION}"
CONTRACT_PROFILE = "QEDTY propagation contract v1"


def json_schema() -> dict[str, Any]:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": KEY,
        "title": "QEDTY Propagation Contract",
        "type": "object",
        "properties": {
            "propagation_event": PropagationEvent.model_json_schema(),
            "propagation_summary": PropagationSummary.model_json_schema(),
            "propagation_result": PropagationResult.model_json_schema(),
            "rule": {
                "type": "object",
                "additionalProperties": True,
            },
        },
        "required": ["propagation_event", "propagation_summary", "propagation_result", "rule"],
        "$defs": {
            "PropagationRuleDigest": {"type": "string", "minLength": 1},
        },
    }


def contract_metadata() -> dict[str, Any]:
    return {
        "name": NAME,
        "version": VERSION,
        "key": KEY,
        "profile": CONTRACT_PROFILE,
        "rule_digest_example": PropagationRule().digest,
    }
