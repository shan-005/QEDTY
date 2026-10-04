"""Tests for Layer 3 Output Formatters and Report Generation."""

import json

from pathlib import Path

from seraph.guard.output.github import GitHubAnnotationsOutput
from seraph.guard.output.json import JsonOutput
from seraph.guard.output.sarif import SarifOutput
from seraph.guard.report import ReportGenerator
from seraph.guard.scanners.base import BlastRadius, Category, Finding, Severity


def _finding_to_dict(f: Finding) -> dict:
    """Helper to adapt Finding objects to the new SARIFFormatter dict API."""
    return {
        "id": getattr(f, "id", "test-id"),
        "file": getattr(f, "file", "a.py"),
        "line": getattr(f, "line", 1),
        "severity": f.severity.value if hasattr(f.severity, "value") else str(f.severity),
        "title": getattr(f, "title", "T"),
        "description": getattr(f, "description", "T"),
        "scanner": getattr(f, "scanner", "T"),
        "category": f.category.value if hasattr(f.category, "value") else str(f.category),
    }


def test_json_output(sample_finding: Finding):
    out = JsonOutput()
    json_str = out.to_json([sample_finding])
    data = json.loads(json_str)
    assert data["summary"]["total_findings"] == 1
    assert data["findings"][0]["title"] == "Hardcoded AWS Key"


def test_github_annotations(sample_finding: Finding):
    out = GitHubAnnotationsOutput()
    annotations = out.render([sample_finding])
    assert "::error" in annotations
    assert "src/main.py" in annotations
    # High severity should fail build on 'high', but pass on 'critical'
    assert out.should_fail_build([sample_finding], "high") is True
    assert out.should_fail_build([sample_finding], "critical") is False


def test_sarif_output(sample_finding: Finding):
    out = SarifOutput()
    # FIX: Adapted to new SARIFFormatter API
    f_dict = _finding_to_dict(sample_finding)
    sarif_dict = out.format([f_dict], ".")
    assert sarif_dict["version"] == "2.1.0"
    assert len(sarif_dict["runs"][0]["results"]) == 1


def test_report_generator_markdown(sample_finding: Finding, tmp_path: Path):
    gen = ReportGenerator([sample_finding])
    out_file = tmp_path / "report.md"
    gen.generate_markdown(out_file)
    assert out_file.exists()
    content = out_file.read_text()
    assert "Hardcoded AWS Key" in content
    assert "Seraph Guard Security Report" in content


def test_report_generator_executive(tmp_path: Path):
    """Test executive summary generation with enough findings to trigger CRITICAL risk level."""
    # Create two critical findings to ensure a risk score of 80 (CRITICAL level -> "IMMEDIATE ACTION REQUIRED")
    finding1 = Finding(
        scanner="TestScanner",
        category=Category.SECRET,
        severity=Severity.CRITICAL,
        confidence=0.95,
        file="src/main.py",
        line=42,
        title="Critical Issue 1",
        description="Found a critical issue",
        evidence="AKIA...",
        blast_radius=BlastRadius(
            blast_radius_score=90.0, reduction_if_fixed=80.0, is_assessed=True
        ),
        fix_available=True,
        fix_command="fix it",
    )
    finding2 = Finding(
        scanner="TestScanner",
        category=Category.SECRET,
        severity=Severity.CRITICAL,
        confidence=0.95,
        file="src/db.py",
        line=10,
        title="Critical Issue 2",
        description="Found another critical issue",
        evidence="password=...",
        blast_radius=BlastRadius(
            blast_radius_score=90.0, reduction_if_fixed=80.0, is_assessed=True
        ),
        fix_available=True,
        fix_command="fix it",
    )

    gen = ReportGenerator([finding1, finding2])
    out_file = tmp_path / "exec.txt"
    gen.generate_executive_summary(out_file)
    assert out_file.exists()
    content = out_file.read_text()
    assert "EXECUTIVE SECURITY SUMMARY" in content
    assert "IMMEDIATE ACTION REQUIRED" in content


def test_report_risk_score_calculation():
    gen = ReportGenerator([])
    # 2 critical (40*2=80) + 1 high (25) = 105 -> capped at 100
    score = gen._calculate_risk_score({"critical": 2, "high": 1})
    assert score == 100
    assert gen._risk_level(score) == "CRITICAL"
