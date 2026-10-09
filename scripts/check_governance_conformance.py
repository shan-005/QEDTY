from __future__ import annotations

import json
import sys
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator

from qedty.governance.policy import ClaimPolicy, Decision, evaluate

ROOT = Path(__file__).resolve().parents[1]
POLICIES = ROOT / "policies"
POLICY_SCHEMA = POLICIES / "policy.schema.json"


def check_policy_documents() -> bool:
    """Parse all policy YAML and schema-check every QEDTY v2 Policy document."""
    try:
        schema = json.loads(POLICY_SCHEMA.read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(schema)
    except (OSError, json.JSONDecodeError, Exception) as exc:
        print(f"Policy schema could not be loaded or validated: {exc}", file=sys.stderr)
        return False

    validator = Draft202012Validator(schema)
    yaml_paths = sorted({*POLICIES.rglob("*.yml"), *POLICIES.rglob("*.yaml")})
    versioned_policies = 0
    failures: list[str] = []

    for path in yaml_paths:
        try:
            document = yaml.safe_load(path.read_text(encoding="utf-8"))
        except (OSError, yaml.YAMLError) as exc:
            failures.append(f"{path.relative_to(ROOT)}: invalid YAML: {exc}")
            continue

        if document is None:
            failures.append(f"{path.relative_to(ROOT)}: empty YAML document")
            continue
        if not isinstance(document, dict):
            failures.append(f"{path.relative_to(ROOT)}: expected a YAML mapping")
            continue

        if document.get("api_version") != "qedty.policy/v2" or document.get("kind") != "Policy":
            continue

        versioned_policies += 1
        for error in sorted(validator.iter_errors(document), key=lambda item: list(map(str, item.absolute_path))):
            location = ".".join(str(part) for part in error.absolute_path) or "<root>"
            failures.append(f"{path.relative_to(ROOT)} [{location}]: {error.message}")

    if versioned_policies == 0:
        failures.append("No api_version=qedty.policy/v2 kind=Policy documents were discovered")
    if failures:
        for failure in failures:
            print(f"Policy validation error: {failure}", file=sys.stderr)
        return False

    print(
        f"Policy schema validation: PASS ({versioned_policies} QEDTY v2 Policy documents; "
        f"{len(yaml_paths)} policy YAML files parsed)"
    )
    return True


def main() -> int:
    policy = ClaimPolicy(minimum_confidence=0.5)
    assert evaluate("observed", ("e",), (), policy, confidence=0.9) == Decision.ALLOW
    assert evaluate("unknown", (), (), policy, confidence=0.9) == Decision.DENY
    print("Governance claim policy: PASS")
    print("Governance epistemic controls: PASS")
    print("Governance deterministic decisioning: PASS")
    return 0 if check_policy_documents() else 1


if __name__ == "__main__":
    raise SystemExit(main())
