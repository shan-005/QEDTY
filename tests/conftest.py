"""Shared fixtures for Seraph Guard v2.0 test suite."""

from pathlib import Path

import pytest

from seraph.guard.config import SeraphConfig
from seraph.guard.orchestration.discovery import RepoProfile
from seraph.guard.scanners.base import BlastRadius, Category, Finding, ScanContext, Severity


@pytest.fixture
def temp_dir(tmp_path: Path) -> Path:
    """Provides a clean temporary directory for each test."""
    return tmp_path


@pytest.fixture
def sample_finding() -> Finding:
    """A standard high-severity secret finding for testing."""
    return Finding(
        scanner="TestScanner",
        category=Category.SECRET,
        severity=Severity.HIGH,
        confidence=0.95,
        file="src/main.py",
        line=42,
        title="Hardcoded AWS Key",
        description="Found an AWS key",
        evidence="AKIA...",
        blast_radius=BlastRadius(
            blast_radius_score=80.0, reduction_if_fixed=70.0, is_assessed=True
        ),
        fix_available=True,
        fix_command="rotate key",
    )


@pytest.fixture
def sample_findings(sample_finding: Finding) -> list[Finding]:
    """A list of mixed-severity findings."""
    low_finding = Finding(
        scanner="TestScanner",
        category=Category.POLICY,
        severity=Severity.LOW,
        confidence=0.8,
        file="README.md",
        line=1,
        title="Missing License",
        description="No license",
        evidence="",
        fix_available=False,
    )
    critical_finding = Finding(
        scanner="TestScanner",
        category=Category.VULNERABILITY,
        severity=Severity.CRITICAL,
        confidence=0.99,
        file="src/db.py",
        line=10,
        title="SQL Injection",
        description="Raw SQL query",
        evidence="execute(f'SELECT * FROM {table}')",
        blast_radius=BlastRadius(
            blast_radius_score=95.0, reduction_if_fixed=90.0, is_assessed=True
        ),
    )
    return [sample_finding, low_finding, critical_finding]


@pytest.fixture
def scan_context(temp_dir: Path) -> ScanContext:
    """A basic ScanContext for scanner tests."""
    return ScanContext(
        path=str(temp_dir),
        is_git_repo=False,
        config=SeraphConfig(),
        profile=RepoProfile(root=str(temp_dir)),
    )


@pytest.fixture
def dummy_repo(temp_dir: Path) -> Path:
    """Creates a minimal dummy repository structure."""
    (temp_dir / "main.py").write_text("print('hello world')\n")
    (temp_dir / "requirements.txt").write_text("requests==2.31.0\n")
    (temp_dir / "package.json").write_text('{"name": "test", "version": "1.0.0"}\n')
    (temp_dir / "tests").mkdir()
    (temp_dir / "tests" / "test_main.py").write_text("def test_pass(): assert True\n")
    return temp_dir
