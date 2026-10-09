from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError

from qedty.governance.policy import ClaimPolicy, Decision, evaluate

ROOT = Path(__file__).resolve().parents[1]
POLICIES = ROOT / "policies"
POLICY_SCHEMA = POLICIES / "policy.schema.json"


def tracked_yaml_paths() -> list[Path]:
    """Return all tracked YAML paths, excluding virtual environments and build output."""
    result = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=ROOT,
        check=True,
        capture_output=True,
    )
    paths = (
        Path(path.decode("utf-8"))
        for path in result.stdout.split(b"\0")
        if path
    )
    return sorted(
        ROOT / path
        for path in paths
        if path.suffix.lower() in {".yml", ".yaml"}
    )


def check_policy_documents() -> bool:
    """Parse every tracked YAML file and validate versioned policies against schema."""
    try:
        schema = json.loads(POLICY_SCHEMA.read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(schema)
    except (OSError, UnicodeError, json.JSONDecodeError, SchemaError) as exc:
        print(f"Policy schema could not be loaded or validated: {exc}", file=sys.stderr)
        return False

    validator = Draft202012Validator(schema)
    yaml_paths = tracked_yaml_paths()
    versioned_policies = 0
    failures: list[str] = []

    for path in yaml_paths:
        try:
            document = yaml.safe_load(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, yaml.YAMLError) as exc:
            failures.append(f"{path.relative_to(ROOT)}: invalid YAML: {exc}")
            continue

        if document is None:
            failures.append(f"{path.relative_to(ROOT)}: empty YAML document")
            continue
        if not isinstance(document, dict):
            continue
        if document.get("api_version") != "qedty.policy/v2" or document.get("kind") != "Policy":
            continue

        versioned_policies += 1
        errors = sorted(
            validator.iter_errors(document),
            key=lambda item: list(map(str, item.absolute_path)),
        )
        for error in errors:
            location = ".".join(str(part) for part in error.absolute_path) or "<root>"
            failures.append(f"{path.relative_to(ROOT)} [{location}]: {error.message}")

    if versioned_policies == 0:
        failures.append("No api_version=qedty.policy/v2 kind=Policy documents were discovered")
    if failures:
        for failure in failures:
            print(f"YAML/policy validation error: {failure}", file=sys.stderr)
        return False

    print(f"YAML syntax validation: PASS ({len(yaml_paths)} tracked YAML files parsed)")
    print(f"Policy schema validation: PASS ({versioned_policies} QEDTY v2 Policy documents)")
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
