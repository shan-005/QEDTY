"""tests/test_cli_matrix.py — exhaustive CLI command-matrix regression tests.

The matrix exercises every public CLI command/flag combination through Click's
in-process runner.  The fixture intentionally contains only a source file so
these tests do not depend on a live vulnerability database or package registry.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any


if TYPE_CHECKING:
    from pathlib import Path

import pytest

from seraph.guard.cli import seraph_guard_main
from seraph.guard.suppression.engine import FileCategory, SuppressionEngine


@pytest.fixture
def cli_runner() -> Any:
    from click.testing import CliRunner

    return CliRunner()


@pytest.fixture
def dummy_repo(tmp_path: Path) -> Path:
    """Create a deterministic minimal repository with no dependency manifests."""
    (tmp_path / "main.py").write_text("print('hello world')\n", encoding="utf-8")
    return tmp_path


def assert_cli_scan_result(result: Any) -> None:
    """Allow a policy-failure exit, but never allow an unhandled traceback."""
    assert result.exit_code in (0, 1), result.output
    assert "Traceback (most recent call last)" not in result.output


class TestSuppressionContextRegression:
    """Regression tests for production/non-production classification boundaries."""

    def test_root_level_test_filename_is_test(self) -> None:
        engine = SuppressionEngine(".")
        cases = (
            "test_ufic.py",
            "test_api.py",
            "test-api.js",
            "spec_api.ts",
            "project/tests/test_ufic.py",  # Fixed: removed /tmp/ to satisfy bandit S108
            "tests/test_ufic.py",
        )
        for path in cases:
            classification = engine.classify_file(path)
            assert classification.category is FileCategory.TEST, (
                f"{path!r} classified as {classification.category.value}: {classification.reason}"
            )

    def test_production_filename_is_not_test(self) -> None:
        engine = SuppressionEngine(".")
        classification = engine.classify_file("src/api.py")
        assert classification.category is FileCategory.PRODUCTION

    def test_github_workflow_is_production(self) -> None:
        engine = SuppressionEngine(".")
        classification = engine.classify_file(".github/workflows/ci.yml")
        assert classification.category is FileCategory.PRODUCTION
        assert "supply-chain" in classification.reason

    @pytest.mark.security
    def test_automatic_suppression_does_not_write_learning_state(self) -> None:
        class Recorder:
            def __init__(self) -> None:
                self.calls = 0

            def record_suppression(self, *args: Any, **kwargs: Any) -> None:
                self.calls += 1

        recorder = Recorder()
        engine = SuppressionEngine(".", learning_engine=recorder)
        finding = {
            "file": "tests/example.py",
            "rule_id": "test-rule",
            "severity": "medium",
            "category": "pattern",
        }
        classification = engine.classify_file(finding["file"])
        suppressed, _, reason = engine.apply_suppression(finding, classification)

        assert suppressed is True
        assert "test" in reason.lower()
        assert recorder.calls == 0


class TestCLIScan:
    """Test all variants of the scan command."""

    @pytest.mark.integration
    def test_scan_default(self, cli_runner: Any, dummy_repo: Path) -> None:
        result = cli_runner.invoke(seraph_guard_main, ["scan", "--path", str(dummy_repo)])
        assert_cli_scan_result(result)

    @pytest.mark.integration
    def test_scan_format_table(self, cli_runner: Any, dummy_repo: Path) -> None:
        result = cli_runner.invoke(
            seraph_guard_main, ["scan", "--path", str(dummy_repo), "--format", "table"]
        )
        assert_cli_scan_result(result)

    @pytest.mark.integration
    def test_scan_format_json(self, cli_runner: Any, dummy_repo: Path) -> None:
        result = cli_runner.invoke(
            seraph_guard_main, ["scan", "--path", str(dummy_repo), "--format", "json"]
        )
        assert_cli_scan_result(result)

    @pytest.mark.integration
    def test_scan_format_sarif(self, cli_runner: Any, dummy_repo: Path) -> None:
        result = cli_runner.invoke(
            seraph_guard_main, ["scan", "--path", str(dummy_repo), "--format", "sarif"]
        )
        assert_cli_scan_result(result)

    @pytest.mark.integration
    def test_scan_format_github(self, cli_runner: Any, dummy_repo: Path) -> None:
        result = cli_runner.invoke(
            seraph_guard_main, ["scan", "--path", str(dummy_repo), "--format", "github"]
        )
        assert_cli_scan_result(result)

    @pytest.mark.integration
    def test_scan_format_junit(self, cli_runner: Any, dummy_repo: Path) -> None:
        result = cli_runner.invoke(
            seraph_guard_main, ["scan", "--path", str(dummy_repo), "--format", "junit"]
        )
        assert_cli_scan_result(result)

    @pytest.mark.integration
    def test_scan_output_file(self, cli_runner: Any, dummy_repo: Path) -> None:
        out = dummy_repo / "out.json"
        result = cli_runner.invoke(
            seraph_guard_main,
            [
                "scan",
                "--path",
                str(dummy_repo),
                "--format",
                "json",
                "--output-file",
                str(out),
            ],
        )
        assert_cli_scan_result(result)

    @pytest.mark.integration
    @pytest.mark.security
    def test_scan_fail_on_critical(self, cli_runner: Any, dummy_repo: Path) -> None:
        result = cli_runner.invoke(
            seraph_guard_main, ["scan", "--path", str(dummy_repo), "--fail-on", "critical"]
        )
        assert_cli_scan_result(result)

    @pytest.mark.integration
    @pytest.mark.security
    def test_scan_fail_on_high(self, cli_runner: Any, dummy_repo: Path) -> None:
        result = cli_runner.invoke(
            seraph_guard_main, ["scan", "--path", str(dummy_repo), "--fail-on", "high"]
        )
        assert_cli_scan_result(result)

    @pytest.mark.integration
    @pytest.mark.security
    def test_scan_fail_on_medium(self, cli_runner: Any, dummy_repo: Path) -> None:
        result = cli_runner.invoke(
            seraph_guard_main, ["scan", "--path", str(dummy_repo), "--fail-on", "medium"]
        )
        assert_cli_scan_result(result)

    @pytest.mark.integration
    @pytest.mark.security
    def test_scan_fail_on_low(self, cli_runner: Any, dummy_repo: Path) -> None:
        result = cli_runner.invoke(
            seraph_guard_main, ["scan", "--path", str(dummy_repo), "--fail-on", "low"]
        )
        assert_cli_scan_result(result)

    @pytest.mark.integration
    @pytest.mark.security
    def test_scan_secret_only(self, cli_runner: Any, dummy_repo: Path) -> None:
        result = cli_runner.invoke(
            seraph_guard_main, ["scan", "--path", str(dummy_repo), "--secret-only"]
        )
        assert_cli_scan_result(result)

    @pytest.mark.integration
    def test_scan_sbom_only(self, cli_runner: Any, dummy_repo: Path) -> None:
        result = cli_runner.invoke(
            seraph_guard_main, ["scan", "--path", str(dummy_repo), "--sbom-only"]
        )
        assert_cli_scan_result(result)

    @pytest.mark.integration
    @pytest.mark.security
    def test_scan_only_secrets(self, cli_runner: Any, dummy_repo: Path) -> None:
        result = cli_runner.invoke(
            seraph_guard_main, ["scan", "--path", str(dummy_repo), "--only", "secrets"]
        )
        assert_cli_scan_result(result)

    @pytest.mark.integration
    def test_scan_only_sbom(self, cli_runner: Any, dummy_repo: Path) -> None:
        result = cli_runner.invoke(
            seraph_guard_main, ["scan", "--path", str(dummy_repo), "--only", "sbom"]
        )
        assert_cli_scan_result(result)

    @pytest.mark.integration
    @pytest.mark.security
    def test_scan_exclude_secrets(self, cli_runner: Any, dummy_repo: Path) -> None:
        result = cli_runner.invoke(
            seraph_guard_main, ["scan", "--path", str(dummy_repo), "--exclude", "secrets"]
        )
        assert_cli_scan_result(result)

    @pytest.mark.integration
    @pytest.mark.security
    def test_scan_no_suppress(self, cli_runner: Any, dummy_repo: Path) -> None:
        result = cli_runner.invoke(
            seraph_guard_main, ["scan", "--path", str(dummy_repo), "--no-suppress"]
        )
        assert_cli_scan_result(result)

    @pytest.mark.integration
    @pytest.mark.security
    def test_scan_show_suppressed(self, cli_runner: Any, dummy_repo: Path) -> None:
        result = cli_runner.invoke(
            seraph_guard_main, ["scan", "--path", str(dummy_repo), "--show-suppressed"]
        )
        assert_cli_scan_result(result)

    @pytest.mark.integration
    @pytest.mark.security
    def test_scan_include_suppressed(self, cli_runner: Any, dummy_repo: Path) -> None:
        result = cli_runner.invoke(
            seraph_guard_main, ["scan", "--path", str(dummy_repo), "--include-suppressed"]
        )
        assert_cli_scan_result(result)

    @pytest.mark.integration
    def test_scan_dedup(self, cli_runner: Any, dummy_repo: Path) -> None:
        result = cli_runner.invoke(
            seraph_guard_main, ["scan", "--path", str(dummy_repo), "--dedup"]
        )
        assert_cli_scan_result(result)

    @pytest.mark.integration
    def test_scan_explain(self, cli_runner: Any, dummy_repo: Path) -> None:
        result = cli_runner.invoke(
            seraph_guard_main, ["scan", "--path", str(dummy_repo), "--explain"]
        )
        assert_cli_scan_result(result)

    @pytest.mark.integration
    def test_scan_rank_by_impact(self, cli_runner: Any, dummy_repo: Path) -> None:
        result = cli_runner.invoke(
            seraph_guard_main, ["scan", "--path", str(dummy_repo), "--rank-by-impact"]
        )
        assert_cli_scan_result(result)

    @pytest.mark.integration
    @pytest.mark.security
    def test_scan_learn(self, cli_runner: Any, dummy_repo: Path) -> None:
        result = cli_runner.invoke(
            seraph_guard_main, ["scan", "--path", str(dummy_repo), "--learn"]
        )
        assert_cli_scan_result(result)

    @pytest.mark.integration
    @pytest.mark.security
    def test_scan_git_history(self, cli_runner: Any, dummy_repo: Path) -> None:
        result = cli_runner.invoke(
            seraph_guard_main, ["scan", "--path", str(dummy_repo), "--git-history"]
        )
        assert_cli_scan_result(result)

    @pytest.mark.integration
    def test_scan_timeout(self, cli_runner: Any, dummy_repo: Path) -> None:
        result = cli_runner.invoke(
            seraph_guard_main, ["scan", "--path", str(dummy_repo), "--timeout", "60"]
        )
        assert_cli_scan_result(result)

    @pytest.mark.integration
    def test_scan_verbose(self, cli_runner: Any, dummy_repo: Path) -> None:
        result = cli_runner.invoke(
            seraph_guard_main, ["scan", "--path", str(dummy_repo), "--verbose"]
        )
        assert_cli_scan_result(result)

    @pytest.mark.integration
    def test_scan_exit_code(self, cli_runner: Any, dummy_repo: Path) -> None:
        result = cli_runner.invoke(
            seraph_guard_main, ["scan", "--path", str(dummy_repo), "--exit-code"]
        )
        assert_cli_scan_result(result)

    @pytest.mark.integration
    def test_scan_ignore_pattern(self, cli_runner: Any, dummy_repo: Path) -> None:
        result = cli_runner.invoke(
            seraph_guard_main,
            ["scan", "--path", str(dummy_repo), "--ignore", "**/node_modules/**"],
        )
        assert_cli_scan_result(result)

    @pytest.mark.integration
    @pytest.mark.security
    def test_scan_severity_medium(self, cli_runner: Any, dummy_repo: Path) -> None:
        result = cli_runner.invoke(
            seraph_guard_main, ["scan", "--path", str(dummy_repo), "--severity", "medium"]
        )
        assert_cli_scan_result(result)

    @pytest.mark.integration
    @pytest.mark.security
    def test_scan_severity_high(self, cli_runner: Any, dummy_repo: Path) -> None:
        result = cli_runner.invoke(
            seraph_guard_main, ["scan", "--path", str(dummy_repo), "--severity", "high"]
        )
        assert_cli_scan_result(result)


class TestCLIFix:
    """Test fix command variants."""

    @pytest.mark.integration
    def test_fix_dry_run(self, cli_runner: Any, dummy_repo: Path) -> None:
        result = cli_runner.invoke(
            seraph_guard_main, ["fix", "--path", str(dummy_repo), "--dry-run"]
        )
        assert result.exit_code == 0, result.output

    @pytest.mark.integration
    def test_fix_all_dry_run(self, cli_runner: Any, dummy_repo: Path) -> None:
        result = cli_runner.invoke(
            seraph_guard_main, ["fix", "--path", str(dummy_repo), "--all", "--dry-run"]
        )
        assert result.exit_code == 0, result.output

    @pytest.mark.integration
    def test_fix_format_json(self, cli_runner: Any, dummy_repo: Path) -> None:
        result = cli_runner.invoke(
            seraph_guard_main,
            ["fix", "--path", str(dummy_repo), "--format", "json", "--dry-run"],
        )
        assert result.exit_code == 0, result.output


class TestCLIExplain:
    """Test explain command variants."""

    @pytest.mark.integration
    def test_explain_f001_no_scan(self, cli_runner: Any, tmp_path: Path) -> None:
        result = cli_runner.invoke(seraph_guard_main, ["explain", "F001", "--path", str(tmp_path)])
        assert result.exit_code in (0, 1), result.output
        assert any(
            phrase in result.output.lower()
            for phrase in (
                "not found",
                "run a scan first",
                "error",
                "no detailed explanation",
                "explanation",
            )
        )

    @pytest.mark.integration
    def test_explain_secret_leak_no_scan(self, cli_runner: Any, tmp_path: Path) -> None:
        result = cli_runner.invoke(
            seraph_guard_main,
            ["explain", "--finding", "secret_leak", "--path", str(tmp_path)],
        )
        assert result.exit_code in (0, 1), result.output
        assert any(
            phrase in result.output.lower()
            for phrase in (
                "not found",
                "run a scan first",
                "error",
                "no detailed explanation",
                "explanation",
            )
        )

    @pytest.mark.integration
    def test_explain_format_json_no_scan(self, cli_runner: Any, tmp_path: Path) -> None:
        result = cli_runner.invoke(
            seraph_guard_main,
            ["explain", "F001", "--format", "json", "--path", str(tmp_path)],
        )
        assert result.exit_code in (0, 1), result.output

    @pytest.mark.integration
    def test_explain_after_scan(self, cli_runner: Any, dummy_repo: Path) -> None:
        cli_runner.invoke(
            seraph_guard_main, ["scan", "--path", str(dummy_repo), "--format", "json"]
        )
        result = cli_runner.invoke(
            seraph_guard_main, ["explain", "F001", "--path", str(dummy_repo)]
        )
        assert result.exit_code == 0, result.output
        assert (
            "no detailed explanation" in result.output.lower()
            or "explanation" in result.output.lower()
        )


class TestCLIReport:
    """Test report command variants."""

    @pytest.mark.integration
    def test_report_html(self, cli_runner: Any, dummy_repo: Path) -> None:
        result = cli_runner.invoke(
            seraph_guard_main, ["report", "--path", str(dummy_repo), "--format", "html"]
        )
        assert result.exit_code in (0, 1), result.output

    @pytest.mark.integration
    def test_report_markdown(self, cli_runner: Any, dummy_repo: Path) -> None:
        result = cli_runner.invoke(
            seraph_guard_main, ["report", "--path", str(dummy_repo), "--format", "markdown"]
        )
        assert result.exit_code in (0, 1), result.output

    @pytest.mark.integration
    def test_report_executive(self, cli_runner: Any, dummy_repo: Path) -> None:
        result = cli_runner.invoke(
            seraph_guard_main,
            ["report", "--path", str(dummy_repo), "--format", "executive"],
        )
        assert result.exit_code in (0, 1), result.output

    @pytest.mark.integration
    def test_report_output(self, cli_runner: Any, dummy_repo: Path) -> None:
        out = dummy_repo / "out.html"
        result = cli_runner.invoke(
            seraph_guard_main,
            [
                "report",
                "--path",
                str(dummy_repo),
                "--format",
                "html",
                "--output",
                str(out),
            ],
        )
        assert result.exit_code in (0, 1), result.output


class TestCLISync:
    """Test sync command variants."""

    @pytest.mark.integration
    def test_sync_export(self, cli_runner: Any, dummy_repo: Path) -> None:
        result = cli_runner.invoke(
            seraph_guard_main, ["sync", "--path", str(dummy_repo), "--export"]
        )
        assert result.exit_code == 0, result.output

    @pytest.mark.integration
    def test_sync_file(self, cli_runner: Any, dummy_repo: Path) -> None:
        out = dummy_repo / "sync.json"
        result = cli_runner.invoke(
            seraph_guard_main,
            ["sync", "--path", str(dummy_repo), "--export", "--file", str(out)],
        )
        assert result.exit_code == 0, result.output


class TestCLILSP:
    """Test LSP command."""

    @pytest.mark.integration
    def test_lsp_help(self, cli_runner: Any) -> None:
        result = cli_runner.invoke(seraph_guard_main, ["lsp", "--help"])
        assert result.exit_code == 0, result.output

    @pytest.mark.integration
    def test_lsp_stdio(self, cli_runner: Any) -> None:
        result = cli_runner.invoke(seraph_guard_main, ["lsp", "--stdio"])
        assert result.exit_code in (0, 1), result.output
        assert "Traceback (most recent call last)" not in result.output


class TestCLIStatus:
    """Test status command."""

    @pytest.mark.integration
    def test_status(self, cli_runner: Any, dummy_repo: Path) -> None:
        result = cli_runner.invoke(seraph_guard_main, ["status", "--path", str(dummy_repo)])
        assert result.exit_code == 0, result.output


class TestCLIConfig:
    """Test config command."""

    @pytest.mark.integration
    def test_config(self, cli_runner: Any) -> None:
        result = cli_runner.invoke(seraph_guard_main, ["config"])
        assert result.exit_code == 0, result.output


class TestCLICache:
    """Test cache command variants."""

    @pytest.mark.integration
    def test_cache_info(self, cli_runner: Any) -> None:
        result = cli_runner.invoke(seraph_guard_main, ["cache", "--info"])
        assert result.exit_code == 0, result.output

    @pytest.mark.integration
    def test_cache_clear(self, cli_runner: Any) -> None:
        result = cli_runner.invoke(seraph_guard_main, ["cache", "--clear"])
        assert result.exit_code == 0, result.output


class TestCLIInit:
    """Test init command."""

    @pytest.mark.integration
    def test_init(self, cli_runner: Any, tmp_path: Path) -> None:
        result = cli_runner.invoke(seraph_guard_main, ["init", "--path", str(tmp_path)])
        assert result.exit_code == 0, result.output


class TestCLICI:
    """Test CI command variants."""

    @pytest.mark.integration
    def test_ci_default(self, cli_runner: Any, dummy_repo: Path) -> None:
        result = cli_runner.invoke(seraph_guard_main, ["ci", "--path", str(dummy_repo)])
        assert_cli_scan_result(result)

    @pytest.mark.integration
    def test_ci_format_json(self, cli_runner: Any, dummy_repo: Path) -> None:
        result = cli_runner.invoke(
            seraph_guard_main, ["ci", "--path", str(dummy_repo), "--format", "json"]
        )
        assert_cli_scan_result(result)

    @pytest.mark.integration
    def test_ci_format_sarif(self, cli_runner: Any, dummy_repo: Path) -> None:
        result = cli_runner.invoke(
            seraph_guard_main, ["ci", "--path", str(dummy_repo), "--format", "sarif"]
        )
        assert_cli_scan_result(result)

    @pytest.mark.integration
    def test_ci_fail_on_critical(self, cli_runner: Any, dummy_repo: Path) -> None:
        result = cli_runner.invoke(
            seraph_guard_main, ["ci", "--path", str(dummy_repo), "--fail-on", "critical"]
        )
        assert_cli_scan_result(result)

    @pytest.mark.integration
    def test_ci_timeout(self, cli_runner: Any, dummy_repo: Path) -> None:
        result = cli_runner.invoke(
            seraph_guard_main, ["ci", "--path", str(dummy_repo), "--timeout", "120"]
        )
        assert_cli_scan_result(result)

    @pytest.mark.integration
    def test_ci_output_file(self, cli_runner: Any, dummy_repo: Path) -> None:
        out = dummy_repo / "out.json"
        result = cli_runner.invoke(
            seraph_guard_main,
            [
                "ci",
                "--path",
                str(dummy_repo),
                "--format",
                "json",
                "--output-file",
                str(out),
            ],
        )
        assert_cli_scan_result(result)


class TestCLIGuardGroup:
    """Test seraph guard (subcommand group) variants."""

    @pytest.mark.integration
    def test_guard_scan(self, cli_runner: Any, dummy_repo: Path) -> None:
        from click.testing import CliRunner

        from seraph.guard.cli import seraph_main

        runner = CliRunner()
        result = runner.invoke(seraph_main, ["guard", "scan", "--path", str(dummy_repo)])
        assert_cli_scan_result(result)

    @pytest.mark.integration
    def test_guard_status(self, cli_runner: Any, dummy_repo: Path) -> None:
        from click.testing import CliRunner

        from seraph.guard.cli import seraph_main

        runner = CliRunner()
        result = runner.invoke(seraph_main, ["guard", "status", "--path", str(dummy_repo)])
        assert result.exit_code == 0, result.output


class TestCLIGlobal:
    """Test global CLI behavior."""

    @pytest.mark.integration
    def test_help(self, cli_runner: Any) -> None:
        result = cli_runner.invoke(seraph_guard_main, ["--help"])
        assert result.exit_code == 0, result.output
        assert "scan" in result.output
        assert "fix" in result.output
        assert "lsp" in result.output

    @pytest.mark.integration
    def test_version(self, cli_runner: Any) -> None:
        result = cli_runner.invoke(seraph_guard_main, ["--version"])
        assert result.exit_code == 0, result.output
        assert "seraph-guard" in result.output.lower() or "0." in result.output

    @pytest.mark.integration
    def test_all_commands_listed(self, cli_runner: Any) -> None:
        result = cli_runner.invoke(seraph_guard_main, ["--help"])
        assert result.exit_code == 0, result.output
        commands = [
            "cache",
            "ci",
            "config",
            "explain",
            "fix",
            "init",
            "lsp",
            "report",
            "scan",
            "status",
            "sync",
        ]
        for cmd in commands:
            assert cmd in result.output, f"Command '{cmd}' missing from --help"
