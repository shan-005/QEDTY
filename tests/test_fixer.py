"""Tests for Layer 3 Action: Automated Remediation & Fixer Engine."""

from pathlib import Path

import pytest

from seraph.guard.fixer import BackupManager, Fixer
from seraph.guard.scanners.base import Category, Finding, Severity


def test_backup_manager_creates_safe_copy(tmp_path: Path):
    """Verify fixer backs up files before mutation."""
    f = tmp_path / "test.py"
    f.write_text("print('hello')")

    bm = BackupManager(tmp_path)
    backup_path = bm.backup(f)

    assert backup_path.exists()
    assert backup_path.read_text() == "print('hello')"


def test_fixer_upgrades_dependency(tmp_path: Path):
    """Verify fixer bumps vulnerable dependencies in requirements.txt."""
    req = tmp_path / "requirements.txt"
    req.write_text("requests==2.25.0\nflask==1.0.0\n")

    finding = Finding(
        scanner="sbom",
        category=Category.VULNERABILITY,
        severity=Severity.HIGH,
        confidence=0.9,
        file="requirements.txt",
        line=1,
        title="Vuln in requests",
        description="Upgrade requests",
        fix_available=True,
        fix_command="Upgrade to 2.31.0",
    )
    finding.metadata = {"package": "requests", "fixed_version": "2.31.0"}

    fixer = Fixer(tmp_path)
    result = fixer.fix_one(finding, dry_run=False)

    assert result.success
    content = req.read_text()
    assert "requests>=2.31.0" in content


@pytest.mark.security
def test_fixer_redacts_env_secret(tmp_path: Path):
    """Verify fixer redacts leaked secrets in .env files."""
    env = tmp_path / ".env"
    env.write_text("DB_PASSWORD=supersecret123\nAPI_KEY=abc\n")

    finding = Finding(
        scanner="secret",
        category=Category.SECRET,
        severity=Severity.CRITICAL,
        confidence=0.99,
        file=".env",
        line=1,
        title="Hardcoded Password",
        description="Remove it",
        fix_available=True,
        fix_command="Redact",
    )
    # Populate all possible locations where the Fixer might look for the secret value
    finding.evidence = "supersecret123"
    finding.metadata = {"value": "supersecret123", "secret_value": "supersecret123"}
    object.__setattr__(finding, "_raw_secret", "supersecret123")

    fixer = Fixer(tmp_path)
    result = fixer.fix_one(finding, dry_run=False)

    assert result.success, f"Fix failed: {result.message}"
    content = env.read_text()
    assert "supersecret123" not in content
    assert "REDACTED_BY_SERAPH" in content
