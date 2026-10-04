"""Tests for Layer 1 Perception: The Multi-Agent Scanner Swarm."""

from pathlib import Path

import pytest

from seraph.guard.scanners.base import ScanContext, Severity
from seraph.guard.scanners.iac import IaCScanner
from seraph.guard.scanners.pattern import PatternScanner
from seraph.guard.scanners.policy import PolicyScanner
from seraph.guard.scanners.sbom import SBOMScanner
from seraph.guard.scanners.secret import AdvancedSecretScanner, EntropyEngine
from seraph.guard.scanners.taint import TaintScanner


@pytest.mark.security
def test_entropy_engine():
    """Verify Shannon + Character-Class diversity entropy calculation."""
    low_entropy = EntropyEngine.calculate("aaaa")
    high_entropy = EntropyEngine.calculate("aB3$xY9!zQ2@wE5&")
    assert low_entropy < 1.5
    assert high_entropy > 4.0


@pytest.mark.asyncio
@pytest.mark.security
async def test_secret_scanner_aws_key(tmp_path: Path):
    """Verify detection of AWS Access Key IDs with correct entropy."""
    f = tmp_path / "config.py"
    f.write_text("AWS_ACCESS_KEY_ID = 'AKIAIOSFODNN7EXAMPLE'\n")
    scanner = AdvancedSecretScanner()
    ctx = ScanContext(path=str(tmp_path))
    findings = await scanner.scan(ctx)
    assert any("AWS" in finding.title for finding in findings)


@pytest.mark.security
def test_sbom_parser_requirements(tmp_path: Path):
    """Verify SBOM manifest parsing for Python requirements.txt."""
    f = tmp_path / "requirements.txt"
    f.write_text("requests==2.31.0\nflask>=2.0.0\n")
    scanner = SBOMScanner()
    deps = scanner.parse_requirements_txt(f)
    assert len(deps) == 2
    assert deps[0]["name"] == "requests"
    assert deps[0]["version"] == "2.31.0"


@pytest.mark.asyncio
@pytest.mark.security
async def test_pattern_scanner_eval(tmp_path: Path):
    """Verify AST/Regex pattern detection for dangerous eval() calls."""
    f = tmp_path / "main.py"
    f.write_text("user_input = input()\nresult = eval(user_input)\n")
    scanner = PatternScanner()
    ctx = ScanContext(path=str(tmp_path))
    findings = await scanner.scan(ctx)
    assert any("eval" in finding.title.lower() for finding in findings)


@pytest.mark.asyncio
@pytest.mark.security
async def test_taint_scanner_basic(tmp_path: Path):
    """Verify interprocedural taint analysis doesn't crash on basic flows."""
    f = tmp_path / "vuln.py"
    f.write_text("def run():\n    data = input()\n    eval(data)\n")
    scanner = TaintScanner()
    ctx = ScanContext(path=str(tmp_path))
    findings = await scanner.scan(ctx)
    # Taint scanner maps sources to sinks; ensure it executes cleanly
    assert isinstance(findings, list)


@pytest.mark.security
def test_policy_scanner_file_exists(tmp_path: Path):
    """Verify policy engine checks for missing required files."""
    policy_dir = tmp_path / "policies"
    policy_dir.mkdir()
    policy_file = policy_dir / "test.yml"
    policy_file.write_text("""
rules:
  - id: require-security
    name: Require SECURITY.md
    type: file_exists
    paths: ["SECURITY.md"]
    severity: medium
    message: Missing SECURITY.md
""")
    scanner = PolicyScanner(policies_dir=policy_dir)
    scanner._load_rules()
    findings = scanner._check_file_exists(scanner.rules[0], tmp_path, Severity.MEDIUM)
    assert len(findings) == 1
    assert "Missing" in findings[0].title


@pytest.mark.asyncio
@pytest.mark.security
async def test_iac_scanner_privileged_container(tmp_path: Path):
    """Verify IaC scanner detects privileged Kubernetes pods."""
    f = tmp_path / "pod.yaml"
    f.write_text("""
apiVersion: v1
kind: Pod
spec:
  containers:
  - name: test
    securityContext:
      privileged: true
""")
    scanner = IaCScanner()
    ctx = ScanContext(path=str(tmp_path))
    findings = await scanner.scan(ctx)
    assert any("Privileged" in finding.title for finding in findings)
