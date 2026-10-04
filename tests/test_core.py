"""Core data model and configuration tests for Seraph Guard v2.0."""

import json

from pathlib import Path

from seraph.guard.config import SeraphConfig
from seraph.guard.config_loader import ConfigLoader
from seraph.guard.intelligence.causal import CausalRanker
from seraph.guard.intelligence.conformal import ConformalPredictionEngine
from seraph.guard.intelligence.learning import AdaptiveLearningEngine
from seraph.guard.output.github import GitHubAnnotationsOutput
from seraph.guard.output.json import JsonOutput
from seraph.guard.output.sarif import SARIFFormatter
from seraph.guard.report import ReportGenerator
from seraph.guard.scanners.base import Finding, Severity


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


def test_severity_weights():
    assert Severity.CRITICAL.weight == 100
    assert Severity.HIGH.weight == 75
    assert Severity.MEDIUM.weight == 50
    assert Severity.LOW.weight == 25
    assert Severity.INFO.weight == 10


def test_finding_properties(sample_finding: Finding):
    assert sample_finding.location == "src/main.py:42"
    assert len(sample_finding.id) == 12
    assert sample_finding.is_production_code
    assert not sample_finding.is_in_test


def test_seraph_config_defaults():
    config = SeraphConfig()
    assert config.fail.fail_on_severity == "high"
    assert config.scanners.timeout_seconds == 300


def test_config_loader_yaml(tmp_path: Path):
    cfg_file = tmp_path / ".seraph-guard.yaml"
    cfg_file.write_text("severity: critical\nformat: json\n")
    loaded = ConfigLoader.load(str(tmp_path), str(cfg_file))
    assert loaded.get("severity") == "critical"
    assert loaded.get("format") == "json"


def test_conformal_apply(sample_findings):
    engine = ConformalPredictionEngine()
    enriched = engine.apply(sample_findings)
    for f in enriched:
        assert f.conformal_confidence is not None


def test_causal_ranker(sample_findings):
    ranker = CausalRanker()
    ranked = ranker.rank(sample_findings)
    assert ranked[0].causal_rank == 1


def test_learning_engine(tmp_path: Path):
    engine = AdaptiveLearningEngine(cache_dir=tmp_path / "learn")
    assert engine.get_team_summary()["total_findings_seen"] == 0


def test_json_output(sample_finding: Finding):
    out = JsonOutput()
    data = json.loads(out.to_json([sample_finding]))
    assert data["summary"]["total_findings"] == 1


def test_github_annotations(sample_finding: Finding):
    out = GitHubAnnotationsOutput()
    assert "::error" in out.render([sample_finding])
    assert out.should_fail_build([sample_finding], "high") is True


def test_sarif_output(sample_finding: Finding):
    out = SARIFFormatter()
    f_dict = _finding_to_dict(sample_finding)
    sarif_dict = out.format([f_dict], ".")
    assert sarif_dict["version"] == "2.1.0"


def test_report_generator(sample_finding: Finding, tmp_path: Path):
    gen = ReportGenerator([sample_finding])
    out_file = tmp_path / "report.md"
    gen.generate_markdown(out_file)
    assert out_file.exists()
