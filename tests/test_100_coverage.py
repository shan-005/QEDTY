"""Catch-all tests to ensure maximum coverage of edge cases and v2.0 components."""

import json

from pathlib import Path

import pytest

from seraph.guard.config import CacheConfig, SeraphConfig
from seraph.guard.deduplication import DeduplicationEngine
from seraph.guard.intelligence.causal import CausalRanker
from seraph.guard.intelligence.conformal import ConformalPredictionEngine
from seraph.guard.orchestration.cache import ScanCache
from seraph.guard.output.github import GitHubAnnotationsOutput
from seraph.guard.output.json import JsonOutput
from seraph.guard.output.sarif import SARIFFormatter
from seraph.guard.scanners.base import BlastRadius, Category, Finding, Severity
from seraph.guard.suppression.engine import FileCategory, SuppressionEngine


def _finding_to_dict(f: Finding) -> dict:
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


def test_config_invalid_output_format():
    with pytest.raises(ValueError, match="Output format"):
        SeraphConfig.from_cli_args(output_format="invalid")


def test_config_invalid_fail_severity():
    with pytest.raises(ValueError, match="fail_on_severity"):
        SeraphConfig.from_cli_args(fail_on="invalid")


def test_config_from_cli_args(tmp_path: Path):
    cfg = SeraphConfig.from_cli_args(path=str(tmp_path), output_format="json", fail_on="medium")
    assert str(cfg.scan_path) == str(tmp_path)
    cfg_dict = cfg.model_dump()
    assert "json" in str(cfg_dict)
    assert "medium" in str(cfg_dict)


def test_causal_empty_findings():
    ranker = CausalRanker()
    assert ranker.rank([]) == []


def test_causal_fix_plan_budget_exceeded():
    ranker = CausalRanker()
    findings = [
        Finding(
            scanner="T",
            category=Category.SECRET,
            severity=Severity.HIGH,
            confidence=0.9,
            file="a.py",
            line=1,
            title="T",
            description="T",
            blast_radius=BlastRadius(reduction_if_fixed=50, is_assessed=True),
        ),
    ]
    plan = ranker.get_fix_plan(findings, max_effort_minutes=0)
    assert plan["findings_addressed"] == 0
    assert plan["steps"] == []
    assert plan["total_effort_minutes"] == 0


def test_conformal_calibrate_not_enough_samples():
    engine = ConformalPredictionEngine(min_calibration_size=10)
    findings = [
        Finding(
            scanner="T",
            category=Category.SECRET,
            severity=Severity.HIGH,
            confidence=0.9,
            file="a.py",
            line=1,
            title="T",
            description="T",
        )
    ]

    with pytest.raises(ValueError, match="Need at least 10 calibration findings"):
        engine.calibrate(findings)

    assert engine.is_calibrated is False


def test_github_render_summary_empty():
    gh = GitHubAnnotationsOutput()
    summary = gh.render_summary([])
    assert "No security findings detected" in summary or summary == ""


def test_github_fail_build_suppressed():
    gh = GitHubAnnotationsOutput()
    findings = [
        Finding(
            scanner="T",
            category=Category.SECRET,
            severity=Severity.HIGH,
            confidence=0.9,
            file="a.py",
            line=1,
            title="T",
            description="T",
            is_suppressed=True,
        )
    ]
    assert not gh.should_fail_build(findings, fail_on="high")


def test_json_write(tmp_path: Path):
    out = tmp_path / "out.json"
    j = JsonOutput()
    findings = [
        Finding(
            scanner="T",
            category=Category.SECRET,
            severity=Severity.HIGH,
            confidence=0.9,
            file="a.py",
            line=1,
            title="T",
            description="T",
        )
    ]
    j.write(findings, out)
    assert out.exists()
    data = json.loads(out.read_text())
    assert data["summary"]["total_findings"] == 1


def test_sarif_to_json():
    s = SARIFFormatter()
    findings = [
        Finding(
            scanner="T",
            category=Category.SECRET,
            severity=Severity.HIGH,
            confidence=0.9,
            file="a.py",
            line=1,
            title="T",
            description="T",
        )
    ]
    out = json.dumps(s.format([_finding_to_dict(f) for f in findings], "."))
    assert "sarif" in out or "runs" in out


def test_suppression_engine_classification():
    engine = SuppressionEngine()
    cls = engine.classify_file("tests/test_main.py")
    assert cls.category == FileCategory.TEST

    cls_prod = engine.classify_file("src/main.py")
    assert cls_prod.category == FileCategory.PRODUCTION


def test_suppression_engine_severity_exception():
    engine = SuppressionEngine()
    finding = {
        "severity": "critical",
        "rule_id": "test",
        "title": "test",
        "file": "tests/test.py",
        "blast_radius": {},
    }
    cls = engine.classify_file("tests/test.py")
    suppressed, _, _ = engine.apply_suppression(finding, cls)
    assert not suppressed  # Critical findings should never be suppressed


def test_deduplication_engine():
    engine = DeduplicationEngine()
    findings = [
        {"rule_id": "R1", "file": "a.py", "line": 10, "severity": "high"},
        {"rule_id": "R1", "file": "a.py", "line": 10, "severity": "medium"},
        {"rule_id": "R2", "file": "b.py", "line": 20, "severity": "low"},
    ]
    deduped = engine.deduplicate(findings)
    assert len(deduped) == 2
    r1 = next(f for f in deduped if f["rule_id"] == "R1")
    assert r1["severity"] == "high"
    assert r1["location_count"] == 1


def test_scan_cache(tmp_path: Path):
    cfg = CacheConfig(directory=tmp_path / "cache", enabled=True, ttl_seconds=3600)
    cache = ScanCache(cfg)
    test_file = tmp_path / "test.py"
    test_file.write_text("print('hello')")

    cache.update(test_file)
    assert not cache.is_changed(test_file)

    test_file.write_text("print('world')")
    assert cache.is_changed(test_file)

    cache.clear()
    assert cache.size == 0
