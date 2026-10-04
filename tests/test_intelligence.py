"""Tests for Layer 2 intelligence engines and related UFIC contracts."""

from pathlib import Path
from typing import Any

import pytest

from seraph.guard.intelligence import (
    context as intelligence_context,
    reachability as intelligence_reachability,
)
from seraph.guard.intelligence.causal import CausalRanker
from seraph.guard.intelligence.conformal import ConformalPredictionEngine
from seraph.guard.intelligence.impact import ImpactAssessmentEngine
from seraph.guard.intelligence.learning import AdaptiveLearningEngine
from seraph.guard.scanners.base import (
    BlastRadius,
    Category,
    Finding,
    ScanContext,
    Severity,
)
from seraph.ufic.classifier import UFICClassifier
from seraph.ufic.semantics import SemanticEngine
from seraph.ufic.topology import TopologyEngine


def _finding(**kwargs: Any) -> Finding:
    base: dict[str, Any] = {
        "scanner": "test",
        "category": Category.PATTERN,
        "severity": Severity.HIGH,
        "confidence": 0.8,
        "file": "src/worker.py",
        "line": 1,
        "title": "Test finding",
        "description": "Test description",
        "rule_id": "TEST-001",
        "metadata": {},
    }
    base.update(kwargs)
    return Finding(**base)


def _calibration_findings(count: int = 30) -> list[Finding]:
    return [
        _finding(
            file=f"src/module_{index}.py",
            line=index + 1,
            severity=Severity.HIGH if index % 2 == 0 else Severity.MEDIUM,
            confidence=0.6,
        )
        for index in range(count)
    ]


@pytest.fixture
def dummy_repo(tmp_path: Path) -> Path:
    (tmp_path / "app.py").write_text("print('hello')\n", encoding="utf-8")
    return tmp_path


def test_conformal_uncalibrated_prediction_is_deterministic() -> None:
    engine = ConformalPredictionEngine()
    finding = _finding(severity=Severity.HIGH, confidence=0.96)

    first = engine.predict(finding)
    second = engine.predict(finding)

    assert first == second
    assert first.calibrated is False
    assert first.coverage_guarantee == 0.0
    assert finding.severity.value in first.prediction_set
    assert 0.0 <= first.nonconformity_score <= 1.0


def test_conformal_calibration_requires_minimum_samples() -> None:
    engine = ConformalPredictionEngine(min_calibration_size=10)
    findings = [_finding()]

    with pytest.raises(ValueError, match="Need at least 10 calibration findings"):
        engine.calibrate(findings)

    assert engine.is_calibrated is False


def test_conformal_calibrated_prediction_and_apply() -> None:
    findings = _calibration_findings(30)
    engine = ConformalPredictionEngine(alpha=0.1, min_calibration_size=30)
    engine.calibrate(findings)

    prediction = engine.predict(findings[0])

    assert prediction.calibrated is True
    assert prediction.coverage_guarantee == pytest.approx(0.9)
    assert prediction.prediction_set
    assert prediction.lower is not None
    assert prediction.upper is not None

    enriched = engine.apply(findings)

    for finding in enriched:
        assert finding.conformal_set is not None
        assert finding.conformal_lower is not None
        assert finding.conformal_upper is not None
        assert finding.conformal_confidence is not None


def test_causal_empty_findings() -> None:
    assert CausalRanker().rank([]) == []


def test_causal_rank_assigns_sequential_ranks() -> None:
    findings = [
        _finding(file="src/a.py", line=1, severity=Severity.CRITICAL),
        _finding(file="src/b.py", line=2, severity=Severity.HIGH),
        _finding(file="src/c.py", line=3, severity=Severity.MEDIUM),
    ]

    ranked = CausalRanker().rank(findings)

    assert [finding.causal_rank for finding in ranked] == [1, 2, 3]


def test_causal_fix_plan_returns_expected_contract() -> None:
    findings = [
        _finding(
            category=Category.SECRET,
            severity=Severity.HIGH,
            file="src/a.py",
            blast_radius=BlastRadius(
                blast_radius_score=50.0,
                reduction_if_fixed=50.0,
                is_assessed=True,
                provenance="INFERRED",
                evidence=[
                    {
                        "type": "test",
                        "basis": "unit-test",
                    }
                ],
            ),
        )
    ]

    plan = CausalRanker().get_fix_plan(findings, max_effort_minutes=30)

    assert plan["findings_addressed"] >= 1
    assert plan["findings_addressed"] == len(plan["steps"])
    assert plan["cumulative_reduction"] > 0.0
    assert plan["total_effort_minutes"] > 0
    assert 0.0 <= plan["estimated_remaining_risk"] <= 1.0


def test_causal_fix_plan_budget_exceeded() -> None:
    findings = [
        _finding(
            category=Category.SECRET,
            blast_radius=BlastRadius(
                reduction_if_fixed=50.0,
                is_assessed=True,
                provenance="INFERRED",
                evidence=[
                    {
                        "type": "test",
                        "basis": "unit-test",
                    }
                ],
            ),
        )
    ]

    plan = CausalRanker().get_fix_plan(findings, max_effort_minutes=0)

    assert plan["findings_addressed"] == 0
    assert plan["steps"] == []
    assert plan["cumulative_reduction"] == 0.0
    assert plan["total_effort_minutes"] == 0


def test_impact_assessment_finds_local_propagation(tmp_path: Path) -> None:
    (tmp_path / "worker.py").write_text(
        "import store\nstore.save(x)\n",
        encoding="utf-8",
    )
    (tmp_path / "store.py").write_text(
        "def save(value):\n    return value\n",
        encoding="utf-8",
    )

    finding = _finding(
        file="worker.py",
        metadata={"cwe": "CWE-78"},
    )
    context = ScanContext(path=str(tmp_path))

    ImpactAssessmentEngine().assess_findings([finding], context)

    assert finding.blast_radius is not None
    assert finding.blast_radius.is_assessed is True
    assert finding.blast_radius.provenance == "INFERRED"
    assert finding.blast_radius.evidence
    assert finding.metadata["causal_score"]["has_real_data"] is True


def test_learning_engine_initialization(tmp_path: Path) -> None:
    engine = AdaptiveLearningEngine(tmp_path / "learn")

    assert engine.cache_file == tmp_path / "learn" / "cache.json"
    assert isinstance(engine.get_team_summary(), dict)


def test_learning_record_and_suppress(tmp_path: Path) -> None:
    engine = AdaptiveLearningEngine(tmp_path / "learn")
    files = [
        "src/core/module_a.py",
        "src/core/module_b.py",
        "src/core/module_c.py",
        "src/core/module_d.py",
        "src/core/module_e.py",
    ]

    for file in files:
        finding = _finding(
            scanner="PatternScanner",
            category=Category.PATTERN,
            severity=Severity.LOW,
            confidence=0.9,
            file=file,
            title="TestPattern",
            description="Test finding",
            metadata={
                "pattern": r"\beval\s*\(",
                "cwe": "CWE-95",
            },
        )
        engine.record_suppression(finding)

    query = _finding(
        scanner="PatternScanner",
        category=Category.PATTERN,
        severity=Severity.LOW,
        confidence=0.9,
        file="src/core/module_a.py",
        title="TestPattern",
        description="Test finding",
        metadata={
            "pattern": r"\beval\s*\(",
            "cwe": "CWE-95",
        },
    )

    outcome = engine.should_suppress(query)
    assert outcome[0] is True


def test_intelligence_context_and_reachability_are_importable() -> None:
    assert intelligence_context.__file__
    assert intelligence_reachability.__file__


@pytest.mark.security
def test_ufic_classifier_intent() -> None:
    classifier = UFICClassifier()

    assert classifier.get_file_intent("tests/test_main.py") == "test"
    assert classifier.get_file_intent("src/main.py") == "production"


@pytest.mark.security
def test_ufic_severity_exception() -> None:
    classifier = UFICClassifier()
    finding = _finding(
        category=Category.SECRET,
        severity=Severity.CRITICAL,
        file="tests/test.py",
        title="Hardcoded Password",
    )

    result = classifier.evaluate_finding(finding)

    assert not result.should_suppress
    assert result.recommended_action == "escalate"


@pytest.mark.security
def test_semantic_engine_credential_context() -> None:
    engine = SemanticEngine()
    adjustment = engine.evaluate(
        "f1",
        "hardcoded_secret",
        "python",
        "tests/test_auth.py",
        "password = 'test'",
    )

    assert adjustment.blast_radius_multiplier < 1.0
    assert adjustment.recommended_action == "suppress"


def test_topology_engine_inference(dummy_repo: Path) -> None:
    engine = TopologyEngine()
    topo = engine.infer(dummy_repo)

    assert "Python" in topo.languages or "python" in str(topo.languages).lower()
    assert topo.file_count > 0
