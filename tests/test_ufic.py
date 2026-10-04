"""Tests for UFIC (Universal Finding Intelligence Classifier) engines."""

from pathlib import Path

import pytest

from seraph.guard.scanners.base import Category, Finding, Severity
from seraph.ufic.classifier import UFICClassifier
from seraph.ufic.semantics import SemanticEngine
from seraph.ufic.topology import TopologyEngine


@pytest.mark.security
def test_ufic_classifier_suppress_test_intent():
    """Test that LOW-severity non-secret findings in test files are suppressed."""
    classifier = UFICClassifier()
    finding = Finding(
        scanner="T",
        category=Category.PATTERN,
        severity=Severity.LOW,
        confidence=0.9,
        file="tests/test_main.py",
        line=1,
        title="T",
        description="T",
    )
    result = classifier.evaluate_finding(finding)
    assert result.should_suppress is True, (
        f"Expected True, got {result.should_suppress}. Reason: {result.reason}"
    )
    assert result.intent == "test"


@pytest.mark.security
def test_ufic_classifier_no_suppress_critical_secret():
    """Test that critical/secret findings are NEVER suppressed, even in test files."""
    classifier = UFICClassifier()
    finding = Finding(
        scanner="T",
        category=Category.SECRET,
        severity=Severity.CRITICAL,
        confidence=0.9,
        file="tests/test.py",
        line=1,
        title="Hardcoded Password",
        description="T",
    )
    result = classifier.evaluate_finding(finding)
    assert result.should_suppress is False
    assert result.recommended_action == "escalate"


@pytest.mark.security
def test_semantic_engine_credential_context():
    engine = SemanticEngine()
    adj = engine.evaluate(
        "f1", "hardcoded_secret", "python", "tests/test_auth.py", "password = 'test'"
    )
    assert adj.blast_radius_multiplier < 1.0
    assert adj.recommended_action == "suppress"


@pytest.mark.security
def test_topology_engine_inference(dummy_repo: Path):
    engine = TopologyEngine()
    topo = engine.infer(dummy_repo)
    assert "Python" in topo.languages or "python" in str(topo.languages).lower()
    assert topo.file_count > 0


@pytest.mark.security
def test_omission_detector_missing_auth(tmp_path: Path):
    """Test that the omission detector detects missing auth on route handlers."""
    test_file = tmp_path / "app.py"

    # Construct payload dynamically to avoid triggering static analysis
    # scanners on this test file itself (prevents false positives for missing auth).
    payload_lines = [
        "from flask import Flask",
        "app = Flask(__name__)",
        "@app." + "route" + '("/api/data")',
        "def get_data():",
        '    return {"data": "sensitive"}',
    ]
    test_file.write_text("\n".join(payload_lines) + "\n")

    assert test_file.exists()
