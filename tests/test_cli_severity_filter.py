import json

from pathlib import Path

from click.testing import CliRunner

from seraph.guard.cli import apply_severity_filter, seraph_main
from seraph.guard.scanners.base import Category, Finding, Severity


def _critical_secret() -> Finding:
    return Finding(
        scanner="AdvancedSecretScanner",
        category=Category.SECRET,
        severity=Severity.CRITICAL,
        confidence=0.95,
        file="app.py",
        line=1,
        title="Potential AWS Access Key ID detected",
        description="test",
    )


def test_severity_filter_falls_back_when_effective_severity_is_none():
    finding = _critical_secret()

    assert finding.effective_severity is None
    assert finding.computed_effective_severity == Severity.CRITICAL

    assert apply_severity_filter([finding], "medium") == [finding]
    assert apply_severity_filter([finding], "high") == [finding]
    assert apply_severity_filter([finding], "critical") == [finding]


def test_secret_only_default_cli_keeps_critical_finding(tmp_path: Path):
    fixture = tmp_path / "app.py"
    fixture.write_text(
        'AWS_ACCESS_KEY_ID = "AKIA2D4H6J8L0N1P3Q5R"\n',
        encoding="utf-8",
    )

    output = tmp_path / "result.json"
    result = CliRunner().invoke(
        seraph_main,
        [
            "guard",
            "scan",
            "--path",
            str(tmp_path),
            "--secret-only",
            "--format",
            "json",
            "--output-file",
            str(output),
        ],
    )

    # Default --fail-on high must fail because the fixture contains a critical secret.
    assert result.exit_code == 1, result.output

    data = json.loads(output.read_text(encoding="utf-8"))
    assert len(data["findings"]) == 1
    assert data["findings"][0]["rule_id"] == "AWS-001"
    assert data["findings"][0]["severity"] == "critical"
    assert data["findings"][0]["effective_severity"] == "critical"
