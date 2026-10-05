"""Architectural Principle:
  cli.py is thin (argument parsing only).
  scheduler.py is the conductor.
  No scanner talks directly to another scanner.
  All communication goes through the Seraph Ontology.

In v2.0, the heavy orchestration logic has been moved into the
Scheduler's 3-Layer Ontological Pipeline.  The CLI now:
  1. Loads config
  2. Discovers repo (with rich console output)
  3. Builds scanners
  4. Calls Scheduler.run()  ← the conductor
  5. Renders output
"""

from __future__ import annotations

import ast
import asyncio
import json
import logging
import re
import sys
import tomllib

from collections import Counter
from pathlib import Path
from typing import Any, cast

import click

from rich.console import Console
from rich.logging import RichHandler
from rich.panel import Panel

from seraph import __version__
from seraph.config import CacheConfig, SeraphConfig
from seraph.config_loader import ConfigLoader
from seraph.intelligence.explanation.engine import ExplanationEngine
from seraph.intelligence.causal import CausalRanker
from seraph.orchestration.cache import ScanCache
from seraph.orchestration.discovery import RepoDiscovery
from seraph.orchestration.scheduler import Scheduler
from seraph.output.github import GitHubAnnotationsOutput
from seraph.output.json import JsonOutput
from seraph.output.junit import JUnitFormatter
from seraph.output.sarif import SARIFFormatter
from seraph.output.table import TableOutput
from seraph.output.report import ReportGenerator
from seraph.sources.repository.scanners.base import Finding, ScanContext, Severity
from seraph.sources.repository.scanners.container import ContainerScanner
from seraph.sources.repository.scanners.iac import IaCScanner
from seraph.sources.repository.scanners.pattern import PatternScanner
from seraph.sources.repository.scanners.policy import PolicyScanner
from seraph.sources.repository.scanners.sbom import SBOMScanner
from seraph.sources.repository.scanners.secret import SecretScanner
from seraph.sources.repository.scanners.taint import TaintScanner
from seraph.integrations.lsp.server import start_lsp
from seraph.intelligence.ufic.engine import UFICEngine


console = Console()
progress_console = Console(stderr=True)
MACHINE_OUTPUT_FORMATS: frozenset[str] = frozenset({"json", "sarif", "junit", "github"})
SCANNER_FAILURE_EXIT_CODE: int = 2
VALID_SCANNER_NAMES: frozenset[str] = frozenset(
    {"secrets", "sbom", "policy", "pattern", "iac", "ufic", "taint", "container"}
)
SCANNER_ALIASES: dict[str, str] = {
    # Scanner aliases, not credentials.
    "secret": "secrets",  # nosec B105
    "secrets": "secrets",  # nosec B105
    "sca": "sbom",
    "supply-chain": "sbom",
    "dependency": "sbom",
    "deps": "sbom",
    "sast": "pattern",
    "patterns": "pattern",
    "iac": "iac",
    "infrastructure": "iac",
    "flow": "taint",
    "dataflow": "taint",
    "data-flow": "taint",
    "container": "container",
    "containers": "container",
    "image": "container",
}


def _normalize_scanner_names(
    values: tuple[str, ...] | list[str] | None,
) -> tuple[list[str], list[str]]:
    """Normalize scanner aliases and return (canonical, unknown)."""
    canonical: list[str] = []
    unknown: list[str] = []
    for raw in values or []:
        name = str(raw).strip().lower()
        normalized = SCANNER_ALIASES.get(name, name)
        if normalized not in VALID_SCANNER_NAMES:
            unknown.append(raw)
            continue
        if normalized not in canonical:
            canonical.append(normalized)
    return canonical, unknown


def _get_scan_console(output_format: str, output_file: str | None) -> Console:
    """Return the console used for scan progress/status messages.

    Machine-readable output sent to stdout must remain parseable, so progress
    is redirected to stderr whenever structured output is emitted directly to
    stdout. When a structured result is written to a file, normal stdout
    remains appropriate for the human-facing progress UI.
    """
    if output_format in MACHINE_OUTPUT_FORMATS and not output_file:
        return progress_console
    return console


# ═══════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════


def _severity_to_str(sev: Any) -> str:
    if sev is None:
        return "info"
    if hasattr(sev, "value"):
        return str(sev.value).lower()
    return str(sev).lower()


def _severity_to_weight(sev: Any) -> int:
    order = {"info": 0, "low": 1, "medium": 2, "high": 3, "critical": 4}
    return order.get(_severity_to_str(sev), 0)


def _resolve_config_paths(config: SeraphConfig, scan_path: Path) -> None:
    """Resolve all relative paths in the config to be absolute relative to scan_path."""
    if hasattr(config, "learning") and hasattr(config.learning, "cache_dir"):
        p = config.learning.cache_dir
        if isinstance(p, Path) and not p.is_absolute():
            config.learning.cache_dir = scan_path / p
    if hasattr(config, "cache") and hasattr(config.cache, "directory"):
        p = config.cache.directory
        if isinstance(p, Path) and not p.is_absolute():
            config.cache.directory = scan_path / p
    for attr in ["policies_dir", "auto_policies_dir"]:
        if hasattr(config, attr):
            p = getattr(config, attr)
            if isinstance(p, Path) and not p.is_absolute():
                setattr(config, attr, scan_path / p)


def _load_gitleaks_toml(scan_path: Path) -> dict[str, Any]:
    """Load .gitleaks.toml and merge into Seraph-style config dict."""
    gitleaks_path = scan_path / ".gitleaks.toml"
    if not gitleaks_path.exists():
        return {}
    try:
        with gitleaks_path.open("rb") as f:
            data = tomllib.load(f)
    except Exception:
        return {}
    allowlist = data.get("allowlist", {})
    paths = allowlist.get("paths", [])
    regexes = allowlist.get("regexes", [])
    mapped: dict[str, Any] = {"ignore": [], "suppression": {"enabled": True}}
    for p in paths:
        mapped["ignore"].append(str(p).replace("\\", "/"))
    if regexes:
        mapped["_gitleaks_regex_allowlist"] = regexes
    return mapped


def _write_output(
    data: dict[str, Any], output_format: str, output_file: str | None, console: Console
) -> None:
    if output_format == "json":
        payload = json.dumps(data, indent=2, default=str)
        if output_file:
            Path(output_file).write_text(payload, encoding="utf-8")
            console.print(f"[green]JSON written to {output_file}[/green]")
        else:
            click.echo(payload)
    else:
        msg = data.get("message", "")
        if not msg and "detail" in data:
            msg = data["detail"]
        if msg:
            console.print(msg)
        else:
            lines: list[str] = []
            for k, v in data.items():
                if k == "results" and isinstance(v, list):
                    lines.append(f"{k}: {len(v)} items")
                else:
                    lines.append(f"{k}: {v}")
            console.print("\n".join(lines))
        if output_file:
            payload = json.dumps(data, indent=2, default=str)
            Path(output_file).write_text(payload, encoding="utf-8")
            console.print(f"[green]Output written to {output_file}[/green]")


def setup_logging(verbose: bool = False, log_console: Console | None = None) -> None:
    level = logging.DEBUG if verbose else logging.WARNING
    logging.basicConfig(
        level=level,
        format="%(message)s",
        datefmt="[%X]",
        handlers=[
            RichHandler(
                console=log_console or console,
                rich_tracebacks=True,
                show_path=False,
            )
        ],
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)


def build_scanners(
    config: SeraphConfig,
    only_scanners: list[str] | None = None,
    exclude_scanners: list[str] | None = None,
    git_history: bool = False,
    image: str | None = None,
) -> list[Any]:
    all_scanners: dict[str, Any] = {
        "secrets": SecretScanner(min_entropy=4.2, git_history=git_history),
        "sbom": SBOMScanner(
            timeout=config.scanners.timeout_seconds,
            chunk_size=config.sbom.chunk_size,
            max_dependencies=config.sbom.max_dependencies,
            quick_mode=config.sbom.quick_mode,
        ),
        "policy": PolicyScanner(policies_dir=config.policies_dir),
        "pattern": PatternScanner(learning_cache_path=config.learning.cache_dir / "cache.json"),
        "iac": IaCScanner(
            policies_dir=config.policies_dir,
            timeout=config.scanners.timeout_seconds,
        ),
        "ufic": UFICEngine(
            cache_dir=config.learning.cache_dir,
            enabled=getattr(config.intelligence, "ufic_enabled", True),
        ),
        "taint": TaintScanner(
            max_call_depth=getattr(config.intelligence, "causal_depth", 3),
            timeout=config.scanners.timeout_seconds,
        ),
    }
    normalized_only, _unknown_only = _normalize_scanner_names(only_scanners)
    normalized_exclude, _unknown_exclude = _normalize_scanner_names(exclude_scanners)
    scanners: list[Any] = []
    if normalized_only:
        scanners = []
        for name in normalized_only:
            if name == "container":
                if not image:
                    msg = "Container scanning requires --image <image>"
                    raise click.ClickException(msg)
                scanners.append(ContainerScanner(image=image))
            elif name in all_scanners:
                scanners.append(all_scanners[name])
    elif only_scanners:
        scanners = []
    else:
        excluded = set(normalized_exclude)
        scanners = [all_scanners[n] for n in all_scanners if n not in excluded]
    if image and not any(isinstance(scanner, ContainerScanner) for scanner in scanners):
        scanners.append(ContainerScanner(image=image))
    return scanners


def _run_pipeline(
    scheduler: Scheduler,
    context: ScanContext,
    scanners: list[Any],
    options: dict[str, Any] | None = None,
) -> Any:
    """Run the scheduler pipeline with correct event loop handling."""
    opts = options or {}
    try:
        loop = asyncio.get_running_loop()
        return asyncio.run_coroutine_threadsafe(
            scheduler.run(context, scanners, opts), loop
        ).result()
    except RuntimeError:
        return asyncio.run(scheduler.run(context, scanners, opts))


def apply_baseline(findings: list[Finding], baseline_path: str) -> list[Finding]:
    try:
        baseline_data = json.loads(Path(baseline_path).read_text(encoding="utf-8"))
        raw_baseline_findings = baseline_data.get("findings", [])
        baseline_ids: set[str] = set()

        if isinstance(raw_baseline_findings, list):
            for item in raw_baseline_findings:
                if isinstance(item, dict):
                    baseline_ids.add(str(item.get("id", "")))

        return [
            finding for finding in findings if str(getattr(finding, "id", "")) not in baseline_ids
        ]
    except Exception as e:
        logging.getLogger(__name__).debug("Failed to apply baseline: %s", e)
        return findings


def _get_pipeline_errors(pipeline_result: Any) -> list[str]:
    """Return scanner/pipeline failures that must make the CLI fail closed."""
    errors: list[str] = []

    layer1 = getattr(pipeline_result, "layer1", None)
    layer1_errors = getattr(layer1, "errors", []) if layer1 is not None else []
    for error in layer1_errors or []:
        value = str(error).strip()
        if value and value not in errors:
            errors.append(value)

    statuses = getattr(pipeline_result, "scanner_status", {}) or {}
    if isinstance(statuses, dict):
        for scanner_name, status in statuses.items():
            text = str(status)
            lowered = text.lower()
            if "✗ error" in lowered or lowered.startswith("✗ invalid") or "timeout" in lowered:
                message = f"{scanner_name}: {text}"
                if message not in errors:
                    errors.append(message)

    return errors


def _set_effective_severity(finding: Finding, new_sev: Severity) -> None:
    try:
        object.__setattr__(finding, "effective_severity", new_sev)
    except (AttributeError, TypeError, ValueError):
        try:
            finding.severity = new_sev
        except (AttributeError, TypeError, ValueError):
            object.__setattr__(finding, "severity", new_sev)


def _finding_effective_severity(finding: Finding) -> Severity:
    """Return the effective severity for a finding, falling back safely."""
    severity = getattr(finding, "effective_severity", None) or getattr(
        finding, "severity", Severity.INFO
    )
    if isinstance(severity, Severity):
        return severity
    try:
        return Severity(str(severity).lower())
    except ValueError:
        return Severity.INFO


def _finding_to_dict(finding: Finding) -> dict[str, Any]:
    """Serialize through Finding.to_dict() so machine output stays secret-safe.

    The CLI uses this dictionary for suppression and SARIF preparation. Raw
    secret/value fields are deliberately not represented.
    """
    effective_severity = _finding_effective_severity(finding)

    base_obj = getattr(finding, "to_dict", None)
    base: dict[str, Any] = {}
    if callable(base_obj):
        raw_base = base_obj()
        if isinstance(raw_base, dict):
            base = cast("dict[str, Any]", raw_base)

    category = getattr(finding, "category", base.get("category", ""))
    category_value = getattr(category, "value", category)
    metadata = base.get("metadata", getattr(finding, "metadata", {}))
    if not isinstance(metadata, dict):
        metadata = {}
    return {
        "id": base.get("id", getattr(finding, "id", "")),
        "file": base.get("file", getattr(finding, "file", "") or getattr(finding, "path", "")),
        "line": base.get("line", getattr(finding, "line", 0)),
        "column": base.get("column", getattr(finding, "column", 0)),
        "rule_id": base.get("rule_id", getattr(finding, "rule_id", getattr(finding, "id", ""))),
        "rule_name": base.get("rule_name", getattr(finding, "rule_name", "")),
        "severity": _severity_to_str(getattr(finding, "severity", Severity.INFO)),
        "effective_severity": _severity_to_str(effective_severity),
        "message": base.get("message", getattr(finding, "message", "")),
        "description": base.get("description", getattr(finding, "description", "")),
        "context": base.get("context", getattr(finding, "context", "")),
        "contains_sensitive_value": bool(
            getattr(finding, "secret_value", "")
            or getattr(finding, "value", "")
            or getattr(finding, "_raw_secret", "")
        ),
        "variable_name": base.get("variable_name", getattr(finding, "variable_name", "")),
        "tags": base.get("tags", getattr(finding, "tags", [])),
        "category": str(category_value),
        "scanner": base.get("scanner", getattr(finding, "scanner", "")),
        "confidence": base.get("confidence", getattr(finding, "confidence", 0.0)),
        "conformal_lower": base.get("conformal_lower", getattr(finding, "conformal_lower", None)),
        "conformal_upper": base.get("conformal_upper", getattr(finding, "conformal_upper", None)),
        "blast_radius": base.get("blast_radius", getattr(finding, "blast_radius", None)),
        "causal_rank": base.get("causal_rank", getattr(finding, "causal_rank", None)),
        "fix_available": base.get("fix_available", getattr(finding, "fix_available", False)),
        "fix_command": base.get("fix_command", getattr(finding, "fix_command", "")),
        "cve": base.get("cve", getattr(finding, "cve", "")),
        "commit": metadata.get("commit", ""),
        "cwe": base.get("cwe", getattr(finding, "cwe", None)),
        "cwe_aliases": base.get("cwe_aliases", getattr(finding, "cwe_aliases", [])),
        "file_context": base.get("file_context", getattr(finding, "file_context", "")),
        "metadata": metadata,
        "affected_files": base.get("affected_files", getattr(finding, "affected_files", [])),
    }


def apply_severity_filter(findings: list[Finding], severity_str: str) -> list[Finding]:
    if not severity_str or severity_str.lower() == "all":
        return findings

    allowed = [s.strip().lower() for s in severity_str.split(",")]
    min_level = min(_severity_to_weight(s) for s in allowed)

    return [
        finding
        for finding in findings
        if _severity_to_weight(_finding_effective_severity(finding)) >= min_level
    ]


# ═══════════════════════════════════════════════════════════════
# Output Renderers
# ═══════════════════════════════════════════════════════════════


def _render_scan_output(
    output_format: str,
    raw_findings: list[Finding],
    prod_findings: list[Finding],
    suppressed_findings: list[Finding],
    metadata: dict[str, Any],
    config: SeraphConfig,
    rank_by_impact: bool,
    output_file: str | None,
    scanner_status: dict[str, str],
    cli_config: dict[str, Any],
    include_suppressed: bool = False,
    show_suppressed: bool = False,
) -> None:
    console = _get_scan_console(output_format, output_file)
    console.print("\n[bold]Step 3/4:[/bold] Generating output...")
    machine_findings = prod_findings if not include_suppressed else raw_findings
    if output_format == "table":
        _render_table_output(
            raw_findings,
            prod_findings,
            suppressed_findings,
            rank_by_impact,
            config,
            scanner_status,
            show_suppressed=show_suppressed,
        )
    elif output_format == "json":
        _render_json_output(machine_findings, metadata, output_file)
    elif output_format == "sarif":
        _render_sarif_output_v2(machine_findings, metadata, output_file, cli_config)
    elif output_format == "junit":
        _render_junit_output(machine_findings, metadata, output_file)
    elif output_format == "github":
        gh_output = GitHubAnnotationsOutput()
        payload = gh_output.render(machine_findings)

        if output_file:
            Path(output_file).write_text(
                payload + ("\n" if payload else ""),
                encoding="utf-8",
            )
            console.print(f"[green]GitHub annotations written to {output_file}[/green]")
        elif payload:
            click.echo(payload)


def _render_table_output(
    raw_findings: list[Finding],
    prod_findings: list[Finding],
    suppressed_findings: list[Finding],
    rank_by_impact: bool,
    _config: SeraphConfig,
    scanner_status: dict[str, str],
    show_suppressed: bool = False,
) -> None:
    emoji_map = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🔵", "info": "⚪"}
    sev_counts: Counter[str] = Counter()
    for finding in raw_findings:
        sev_str = _severity_to_str(_finding_effective_severity(finding))
        sev_counts[sev_str] += 1
    dist_parts = [
        f"{emoji_map.get(s, '⚪')} {s}: {sev_counts[s]}"
        for s in ["critical", "high", "medium", "low", "info"]
        if sev_counts.get(s, 0) > 0
    ]
    dist_str = "  |  ".join(dist_parts) if dist_parts else "No findings"
    console.print(
        Panel(
            dist_str, title="Severity Distribution (All Files)", border_style="blue", expand=False
        )
    )
    prod_sev_counts: Counter[str] = Counter()
    for finding in prod_findings:
        sev_str = _severity_to_str(_finding_effective_severity(finding))
        prod_sev_counts[sev_str] += 1
    prod_dist_parts = [
        f"{emoji_map.get(s, '⚪')} {s}: {prod_sev_counts[s]}"
        for s in ["critical", "high", "medium", "low", "info"]
        if prod_sev_counts.get(s, 0) > 0
    ]
    prod_dist_str = "  |  ".join(prod_dist_parts) if prod_dist_parts else "No production findings"
    console.print(
        Panel(
            prod_dist_str,
            title="Severity Distribution (Production Code)",
            border_style="green",
            expand=False,
        )
    )
    console.print(
        f"\n[bold]Seraph Guard — Production Code Findings ({len(prod_findings)} issues)[/bold]"
    )
    if prod_findings:
        table_output = TableOutput(console)
        table_output.render(prod_findings, raw_findings, scanner_status)
    else:
        console.print(
            "  [green]✅ No production findings at or above the specified severity.[/green]"
        )
    gaps = sum(
        1
        for status in scanner_status.values()
        if "error" in str(status).lower() or "timeout" in str(status).lower()
    )
    info_parts: list[str] = []
    if len(suppressed_findings) > 0:
        info_parts.append(f"{len(suppressed_findings)} findings suppressed")
    if gaps > 0:
        info_parts.append(f"Scanner gaps: {gaps}")
    if info_parts:
        console.print(f"[dim]Info: {'  |  '.join(info_parts)}[/dim]")
    if show_suppressed and suppressed_findings:
        console.print(f"\n[bold]Suppressed Findings ({len(suppressed_findings)} items):[/bold]")
        for finding in suppressed_findings[:50]:
            sev_str = _severity_to_str(_finding_effective_severity(finding)).upper()
            file_path = getattr(finding, "file", "") or getattr(finding, "path", "")
            rule = getattr(finding, "rule_id", getattr(finding, "id", ""))
            console.print(f"  [dim]{sev_str} | {rule} | {file_path}[/dim]")
        if len(suppressed_findings) > 50:
            console.print(f"  [dim]... and {len(suppressed_findings) - 50} more[/dim]")

    if rank_by_impact and prod_findings:
        try:
            ranker = CausalRanker()
            plan = ranker.get_fix_plan(prod_findings, max_effort_minutes=30)
            if plan:
                table_output = TableOutput(console)
                table_output.render_fix_plan(plan)
                console.print("[dim]Math: multiplicative — total = 1 - product(1 - r_i)[/dim]")
        except Exception as e:
            console.print(f"[dim]Fix plan generation skipped (ranker error: {e})[/dim]")


def _render_json_output(
    findings: list[Finding], metadata: dict[str, Any], output_file: str | None
) -> None:
    json_output = JsonOutput()
    output = json_output.to_json(findings, metadata=metadata)
    if output_file:
        Path(output_file).write_text(output, encoding="utf-8")
        progress_console.print(f"[green]JSON written to {output_file}[/green]")
    else:
        click.echo(output)


def _render_sarif_output_v2(
    findings: list[Finding],
    metadata: dict[str, Any],
    output_file: str | None,
    _cli_config: dict[str, Any],
) -> None:
    formatter = SARIFFormatter(tool_name="Seraph Guard", tool_version=__version__)
    finding_dicts: list[dict[str, Any]] = []
    for f in findings:
        d = _finding_to_dict(f)
        d["blast_radius"] = getattr(f, "blast_radius", None)
        d["conformal_lower"] = getattr(f, "conformal_lower", None)
        d["conformal_upper"] = getattr(f, "conformal_upper", None)
        d["confidence"] = getattr(f, "confidence", getattr(f, "conformal_confidence", 0))
        d["affected_files"] = getattr(f, "affected_files", [])
        d["remediation"] = getattr(f, "remediation", "")
        d["id"] = getattr(f, "id", "")
        d["title"] = getattr(f, "title", "")
        d["category"] = getattr(f, "category", "")
        d["scanner"] = getattr(f, "scanner", "")
        d["fix_available"] = getattr(f, "fix_available", False)
        d["fix_command"] = getattr(f, "fix_command", "")
        d["cve"] = getattr(f, "cve", "")
        finding_dicts.append(d)
    if output_file:
        formatter.write(finding_dicts, metadata.get("scan_path", "."), output_file)
        progress_console.print(f"[green]SARIF written to {output_file}[/green]")
    else:
        click.echo(
            json.dumps(formatter.format(finding_dicts, metadata.get("scan_path", ".")), indent=2)
        )


def _render_junit_output(
    findings: list[Finding], metadata: dict[str, Any], output_file: str | None
) -> None:
    formatter = JUnitFormatter()
    finding_dicts = [_finding_to_dict(f) for f in findings]
    if output_file:
        formatter.write(finding_dicts, metadata.get("scan_path", "."), output_file)
        progress_console.print(f"[green]JUnit XML written to {output_file}[/green]")
    else:
        click.echo(formatter.format(finding_dicts, metadata.get("scan_path", ".")))


def _evaluate_build_result(
    prod_findings: list[Finding],
    suppressed_findings: list[Finding],
    suppression_stats: dict[str, int],
    fail_on: str,
    exit_code_flag: bool,
    _cli_config: dict[str, Any],
    output_console: Console | None = None,
    scanner_errors: list[str] | None = None,
) -> int:
    active_console = output_console or console
    active_console.print("\n[bold]Step 4/4:[/bold] Evaluating scan result...")
    for cat, count in suppression_stats.items():
        if count > 0:
            label = cat.replace("_suppressed", "").replace("_", " ").capitalize()
            active_console.print(f"  {label} findings: excluded ({count})")
    active_console.print(f"  Production findings evaluated: {len(prod_findings)}\n")

    # Scanner/runtime failures are execution failures, not clean scans.
    # A failed scanner must never be converted into a zero-finding success,
    # regardless of --exit-code or finding thresholds.
    if scanner_errors:
        active_console.print(
            f"[bold red]Scan FAILED: {len(scanner_errors)} scanner/runtime error(s). "
            "Results are not trustworthy.[/bold red]"
        )
        for error in scanner_errors:
            active_console.print(f"  [red]✗ {error}[/red]")
        active_console.print(
            f"  [dim]Returning exit code {SCANNER_FAILURE_EXIT_CODE} (fail closed).[/dim]"
        )
        return SCANNER_FAILURE_EXIT_CODE

    if exit_code_flag and prod_findings:
        active_console.print(
            f"[bold red]Scan FAILED: {len(prod_findings)} finding(s) in production code (--exit-code enabled).[/bold red]"
        )
        return 1

    threshold = _severity_to_weight(fail_on)
    failing_findings = [
        finding
        for finding in prod_findings
        if _severity_to_weight(_finding_effective_severity(finding)) >= threshold
    ]
    if failing_findings:
        active_console.print(
            f"[bold red]Scan FAILED: {len(failing_findings)} findings at or above '{fail_on}' severity in production code.[/bold red]"
        )
        return 1
    active_console.print(
        f"[bold green]Scan PASSED: No findings at or above '{fail_on}' severity in production code.[/bold green]"
    )
    non_prod_high = [
        finding
        for finding in suppressed_findings
        if _severity_to_weight(_finding_effective_severity(finding)) >= 3
    ]
    if non_prod_high:
        active_console.print(
            f"  [yellow]{len(non_prod_high)} high finding(s) in non-production code (build scripts, framework internals, tests)[/yellow]"
        )
        active_console.print("  [dim]Recommendation: Review in next sprint.[/dim]")
    return 0


# ═══════════════════════════════════════════════════════════════
# Commands (v2.0 — delegate orchestration to Scheduler)
# ═══════════════════════════════════════════════════════════════


def _cmd_scan(
    path: str,
    secret_only: bool,
    sbom_only: bool,
    output_format: str,
    fail_on: str,
    rank_by_impact: bool,
    learn: bool,
    verbose: bool,
    output_file: str | None,
    exclude: tuple[str, ...],
    only: tuple[str, ...],
    severity: str,
    timeout: int | None,
    baseline: str | None,
    exit_code: bool,
    config_path: str | None,
    ignore: tuple[str, ...],
    no_suppress: bool,
    dedup: bool,
    include_suppressed: bool,
    show_suppressed: bool,
    git_history: bool,
    image: str | None,
    explain: bool = False,
) -> int:
    """Run a security scan via the 3-Layer Ontological Pipeline."""
    scan_path = Path(path).resolve()
    scan_console = _get_scan_console(output_format, output_file)
    setup_logging(verbose, scan_console)
    console = scan_console

    console.print(f"\n[bold blue]Seraph Guard v{__version__}[/bold blue]")
    console.print(f"[dim]Scanning: {scan_path}[/dim]\n")

    selected_only, unknown_only = _normalize_scanner_names(list(only))
    selected_exclude, unknown_exclude = _normalize_scanner_names(list(exclude))
    if unknown_only or unknown_exclude:
        unknown = [*unknown_only, *unknown_exclude]
        console.print(
            "[bold red]Unknown scanner name(s): "
            + ", ".join(str(item) for item in unknown)
            + "[/bold red]"
        )
        console.print("[dim]Valid scanners: secrets, sbom, policy, pattern, iac, ufic, taint[/dim]")
        return SCANNER_FAILURE_EXIT_CODE

    cli_config = ConfigLoader.load(str(scan_path), config_path)
    gitleaks_config = _load_gitleaks_toml(scan_path)
    if gitleaks_config:
        cli_config["ignore"] = list(
            set(cli_config.get("ignore", []) + gitleaks_config.get("ignore", []))
        )
        console.print("[dim]  Merged .gitleaks.toml allowlist into ignore patterns[/dim]")

    if severity != "medium":
        cli_config["severity"] = severity
    if ignore:
        cli_config["ignore"] = list(ignore) + cli_config.get("ignore", [])
    if no_suppress:
        cli_config["suppression"] = cli_config.get("suppression", {})
        cli_config["suppression"]["enabled"] = False
    if not dedup:
        cli_config["deduplication"] = False

    config_obj = SeraphConfig.from_cli_args(
        path=str(scan_path),
        output_format=output_format,
        fail_on=fail_on,
        rank_by_impact=rank_by_impact,
        learn=learn,
        verbose=verbose,
    )
    _resolve_config_paths(config_obj, scan_path)
    if timeout:
        config_obj.scanners.timeout_seconds = timeout

    # Propagate SBOM config from YAML to the config object
    sbom_cfg = cli_config.get("sbom", {})
    if isinstance(sbom_cfg, dict):
        for key in (
            "include_dev_dependencies",
            "deduplicate_across_manifests",
            "chunk_size",
            "max_dependencies",
            "quick_mode",
        ):
            if key in sbom_cfg:
                setattr(config_obj.sbom, key, sbom_cfg[key])

    console.print("[bold]Step 1/4:[/bold] Discovering repository...")
    discovery = RepoDiscovery(scan_path)
    profile = discovery.discover()

    langs = ", ".join(profile.languages) if profile.languages else "none detected"
    console.print(f"  Languages: {langs}")
    prod_count = getattr(profile, "prod_file_count", profile.file_count)
    test_count = getattr(profile, "test_file_count", 0)
    console.print(
        f"  Files: {profile.file_count}  |  Production: {prod_count}  |  Test: {test_count}"
    )
    is_fw = getattr(profile, "is_framework", False)
    fw_name = getattr(profile, "framework_name", "")
    fw_str = f"  |  Framework detected: {fw_name}" if is_fw and fw_name else ""
    is_container = getattr(profile, "is_container_rootfs", False)
    container_str = "  |  Container rootfs detected" if is_container else ""
    console.print(f"  Git repo: {'yes' if profile.is_git_repo else 'no'}{fw_str}{container_str}")

    context = ScanContext(
        path=str(scan_path),
        is_git_repo=profile.is_git_repo,
        config=config_obj,
        profile=profile,
    )
    canonical_only = [*selected_only]
    if secret_only:
        canonical_only = ["secrets"]
    elif sbom_only:
        canonical_only = ["sbom"]
    scanners = build_scanners(
        config_obj, canonical_only or None, selected_exclude, git_history=git_history, image=image
    )

    pipeline_options = {
        "deduplication": cli_config.get("deduplication", True),
        "suppression": not no_suppress,
        "learn": learn,
        "rank_by_impact": rank_by_impact,
        "explain": explain,
    }

    scheduler = Scheduler(config_obj)
    pipeline_result = _run_pipeline(scheduler, context, scanners, pipeline_options)
    scanner_errors = _get_pipeline_errors(pipeline_result)

    findings = list(pipeline_result.layer2.findings)
    if baseline:
        before = len(findings)
        findings = apply_baseline(findings, baseline)
        if before - len(findings) > 0:
            console.print(f"  Baseline filtered: {before - len(findings)} known findings")

    findings = apply_severity_filter(findings, cli_config.get("severity", severity))

    # Build metadata early so we can cache the scan for the `explain` command.
    metadata = {
        "scan_path": str(scan_path),
        "duration_ms": pipeline_result.scan_duration_ms,
        "scanners": pipeline_result.scanners_executed,
        "version": __version__,
        "suppressed_count": pipeline_result.total_suppressed,
        "total_raw": pipeline_result.total_raw_findings,
        "scanner_errors": scanner_errors,
        "scan_metadata": getattr(context, "metadata", {}),
        "scan_status": "failed" if scanner_errors else "completed",
        "intelligence": {
            "dedup_applied": bool(pipeline_result.layer2.dedup_applied),
            "learning_applied": bool(pipeline_result.layer2.learning_applied),
            "conformal_applied": bool(pipeline_result.layer2.conformal_applied),
            "causal_applied": bool(pipeline_result.layer2.causal_applied),
            "explanation_requested": bool(explain),
            "explanations_attached": sum(
                1
                for finding in findings
                if isinstance(getattr(finding, "metadata", None), dict)
                and isinstance(finding.metadata.get("explanation"), dict)
            ),
        },
    }

    try:
        cache_dir = scan_path / ".seraph-cache"
        cache_dir.mkdir(parents=True, exist_ok=True)
        json_output = JsonOutput()
        payload = json_output.to_json(findings, metadata=metadata)
        (cache_dir / "last_scan.json").write_text(payload, encoding="utf-8")
    except Exception as e:
        logging.getLogger(__name__).debug("could not save last scan: %s", e)

    if not findings and not pipeline_result.layer1.findings:
        if scanner_errors:
            console.print(
                "\n[bold red]No trustworthy result: one or more scanners failed.[/bold red]"
            )
        else:
            console.print("\n[bold green]No findings. Repository is clean![/bold green]")
        metadata["findings"] = []
        _render_scan_output(
            output_format,
            pipeline_result.layer1.findings,
            [],
            pipeline_result.layer2.suppressed_findings,
            metadata,
            config_obj,
            rank_by_impact,
            output_file,
            pipeline_result.scanner_status,
            cli_config,
            include_suppressed=include_suppressed,
            show_suppressed=show_suppressed,
        )
        return _evaluate_build_result(
            [],
            pipeline_result.layer2.suppressed_findings,
            pipeline_result.layer2.suppression_stats,
            fail_on,
            exit_code,
            cli_config,
            output_console=scan_console,
            scanner_errors=scanner_errors,
        )

    _render_scan_output(
        output_format,
        pipeline_result.layer1.findings,
        findings,
        pipeline_result.layer2.suppressed_findings,
        metadata,
        config_obj,
        rank_by_impact,
        output_file,
        pipeline_result.scanner_status,
        cli_config,
        include_suppressed=include_suppressed,
        show_suppressed=show_suppressed,
    )

    if explain and findings:
        _render_scan_explanations(findings, output_format)

    return _evaluate_build_result(
        findings,
        pipeline_result.layer2.suppressed_findings,
        pipeline_result.layer2.suppression_stats,
        fail_on,
        exit_code,
        cli_config,
        output_console=scan_console,
        scanner_errors=scanner_errors,
    )


def _try_fix_sbom_finding(finding: Finding, scan_path: Path, dry_run: bool) -> dict[str, Any]:
    """Attempt to auto-fix an SBOM finding by upgrading the vulnerable dependency."""
    pkg_name = getattr(finding, "package_name", "") or getattr(finding, "rule_name", "")
    fixed_version = getattr(finding, "fixed_version", "") or getattr(finding, "remediation", "")
    file_path = getattr(finding, "file", "") or getattr(finding, "path", "")

    result: dict[str, Any] = {
        "finding_id": getattr(finding, "id", "?"),
        "success": False,
        "message": "No auto-fix available for this finding type",
        "changes": [],
    }

    if not pkg_name or not fixed_version:
        return result

    abs_file = scan_path / file_path if file_path else None
    if not abs_file or not abs_file.exists():
        return result

    if abs_file.name.lower() == "package.json":
        try:
            content = json.loads(abs_file.read_text(encoding="utf-8"))
            updated = False
            for section in ("dependencies", "devDependencies"):
                if section in content and pkg_name in content[section]:
                    old = content[section][pkg_name]
                    content[section][pkg_name] = fixed_version
                    result["changes"].append(f"{section}.{pkg_name}: {old} → {fixed_version}")
                    updated = True
            if updated:
                if not dry_run:
                    abs_file.write_text(json.dumps(content, indent=2) + "\n", encoding="utf-8")
                result["success"] = True
                result["message"] = f"Upgraded {pkg_name} to {fixed_version} in package.json"
            return result
        except Exception as e:
            result["message"] = f"package.json fix failed: {e}"
            return result

    if abs_file.name.lower() == "requirements.txt":
        try:
            lines = abs_file.read_text(encoding="utf-8").splitlines()
            new_lines: list[str] = []
            updated = False
            for line in lines:
                match = re.match(
                    rf"^({re.escape(pkg_name)})([<>=!~].*)$", line.strip(), re.IGNORECASE
                )
                if match:
                    old = line.strip()
                    new_line = f"{pkg_name}=={fixed_version}"
                    new_lines.append(new_line)
                    result["changes"].append(f"{old} → {new_line}")
                    updated = True
                else:
                    new_lines.append(line)
            if updated:
                if not dry_run:
                    abs_file.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
                result["success"] = True
                result["message"] = f"Pinned {pkg_name}=={fixed_version} in requirements.txt"
            return result
        except Exception as e:
            result["message"] = f"requirements.txt fix failed: {e}"
            return result

    if abs_file.name.lower() == "cargo.toml":
        try:
            with abs_file.open("rb") as f:
                data = tomllib.load(f)
            updated = False
            for section in ("dependencies", "dev-dependencies"):
                if section in data and pkg_name in data[section]:
                    dep = data[section][pkg_name]
                    if isinstance(dep, dict):
                        old = dep.get("version", "?")
                        dep["version"] = fixed_version
                    else:
                        old = dep
                        data[section][pkg_name] = {"version": fixed_version}
                    result["changes"].append(f"{section}.{pkg_name}: {old} → {fixed_version}")
                    updated = True
            if updated:
                if not dry_run:
                    text = abs_file.read_text(encoding="utf-8")
                    pattern = rf"({re.escape(pkg_name)}\s*=\s*){{[^}}]*}}"
                    repl = f'{{ version = "{fixed_version}" }}'
                    text = re.sub(pattern, repl, text)
                    abs_file.write_text(text, encoding="utf-8")
                result["success"] = True
                result["message"] = f"Upgraded {pkg_name} to {fixed_version} in Cargo.toml"
            return result
        except Exception as e:
            result["message"] = f"Cargo.toml fix failed: {e}"
            return result

    return result


def _cmd_fix(
    path: str,
    fix_all: bool,
    finding_id: str | None,
    dry_run: bool,
    output_format: str,
    output: str | None,
    verbose: bool,
    only: tuple[str, ...],
    exclude: tuple[str, ...],
    config_path: str | None = None,
) -> None:
    """Auto-fix issues where possible."""
    setup_logging(verbose)
    scan_path = Path(path).resolve()
    console.print("\n[bold blue]Seraph Guard Fix[/bold blue]")
    console.print(f"[dim]Path: {scan_path}[/dim]\n")
    if dry_run:
        console.print("[yellow]DRY RUN — no changes will be made[/yellow]\n")

    cli_config = ConfigLoader.load(str(scan_path), config_path)

    console.print("[bold]Step 1/2:[/bold] Running scan to identify fixable findings...")
    config = SeraphConfig(scan_path=scan_path)
    _resolve_config_paths(config, scan_path)

    if "timeout" in cli_config and hasattr(config.scanners, "timeout_seconds"):
        config.scanners.timeout_seconds = cli_config["timeout"]
    if "policies_dir" in cli_config and hasattr(config, "policies_dir"):
        p = Path(cli_config["policies_dir"])
        config.policies_dir = p if p.is_absolute() else scan_path / p
    if "auto_policies_dir" in cli_config and hasattr(config, "auto_policies_dir"):
        p = Path(cli_config["auto_policies_dir"])
        config.auto_policies_dir = p if p.is_absolute() else scan_path / p

    if hasattr(config, "policies_dir"):
        pd = Path(config.policies_dir)
        if not pd.exists():
            builtin = Path(__file__).parent.parent.parent.parent / "policies" / "builtin"
            if builtin.exists():
                config.policies_dir = builtin
                if hasattr(config, "auto_policies_dir"):
                    config.auto_policies_dir = builtin.parent / "auto-generated"

    # Propagate SBOM config from YAML to the config object
    sbom_cfg = cli_config.get("sbom", {})
    if isinstance(sbom_cfg, dict):
        for key in (
            "include_dev_dependencies",
            "deduplicate_across_manifests",
            "chunk_size",
            "max_dependencies",
            "quick_mode",
        ):
            if key in sbom_cfg:
                setattr(config.sbom, key, sbom_cfg[key])

    discovery = RepoDiscovery(scan_path)
    profile = discovery.discover()
    context = ScanContext(
        path=str(scan_path), is_git_repo=profile.is_git_repo, config=config, profile=profile
    )
    scanners = build_scanners(
        config, list(only) if only else None, list(exclude) if exclude else None
    )
    scheduler = Scheduler(config)
    pipeline_result = _run_pipeline(scheduler, context, scanners, {"suppression": False})
    findings = list(pipeline_result.layer2.findings)

    if not findings:
        console.print("[bold green]No findings to fix![/bold green]")
        if output:
            empty_data: dict[str, Any] = {
                "dry_run": dry_run,
                "finding_id": finding_id,
                "fixed": 0,
                "failed": 0,
                "success_rate": 0.0,
                "results": [],
            }
            Path(output).write_text(json.dumps(empty_data, indent=2, default=str), encoding="utf-8")
            console.print(f"[green]Empty fix report written to {output}[/green]")
        return

    fixable = [f for f in findings if getattr(f, "fix_available", False)]
    sbom_fixable = [
        f
        for f in findings
        if getattr(f, "scanner", "") == "sbom" and getattr(f, "fixed_version", "")
    ]

    console.print(f"  Total findings: {len(findings)}")
    console.print(f"  Auto-fixable (general): {len(fixable)}")
    console.print(f"  Auto-fixable (SBOM): {len(sbom_fixable)}\n")

    console.print("[bold]Step 2/2:[/bold] Applying fixes...")
    from seraph.sources.repository.fixer import Fixer

    fixer = Fixer(scan_path)

    from seraph.intelligence.learning import AdaptiveLearningEngine

    learning = AdaptiveLearningEngine(cache_dir=scan_path / ".seraph-learn")
    fixed_findings: list[Finding] = []
    fix_results: list[dict[str, Any]] = []

    if finding_id:
        target = next((f for f in findings if getattr(f, "id", "") == finding_id), None)
        if not target:
            target = next((f for f in findings if getattr(f, "rule_id", "") == finding_id), None)
        if not target:
            target = next(
                (f for f in findings if getattr(f, "id", "").startswith(finding_id)), None
            )

        if not target:
            console.print(f"[red]Finding not found: {finding_id}[/red]")
            console.print("[dim]Available finding IDs (first 10):[/dim]")
            for f in findings[:10]:
                fid = getattr(f, "id", "?")
                rule = getattr(f, "rule_id", "?")
                console.print(f"  [dim]{fid}  ({rule})[/dim]")
            return

        if getattr(target, "scanner", "") == "sbom":
            res = _try_fix_sbom_finding(target, scan_path, dry_run)
            fix_results.append(res)
            if res["success"]:
                console.print(f"  [green]✅ {res['message']}[/green]")
                fixed_findings.append(target)
            else:
                console.print(f"  [yellow]⚠️ {res['message']}[/yellow]")
        else:
            fix_res = fixer.fix_one(target, dry_run)
            # Safely extract boolean status from FixResult object
            fix_success = bool(getattr(fix_res, "success", True))
            if fix_success or not dry_run:
                fixed_findings.append(target)
    elif fix_all:
        for f in sbom_fixable:
            res = _try_fix_sbom_finding(f, scan_path, dry_run)
            fix_results.append(res)
            if res["success"]:
                fixed_findings.append(f)
        fixer.fix_all(findings, dry_run)
        if not dry_run:
            for f in fixable:
                if f not in fixed_findings:
                    fixed_findings.append(f)
    else:
        console.print("[yellow]Specify --all or --finding <id>[/yellow]")
        console.print("[dim]Example: seraph-guard fix --all --dry-run[/dim]")
        return

    if not dry_run and fixed_findings:
        for f in fixed_findings:
            try:
                learning.record_fix(f)
            except Exception as e:
                logging.getLogger(__name__).debug("Failed to record fix: %s", e)
        console.print(
            f"[dim]  Recorded {len(fixed_findings)} fixes in adaptive learning engine.[/dim]"
        )

    summary = fixer.get_summary()
    raw_results = summary.get("results", [])
    parsed_results: list[dict[str, Any]] = []
    for r in raw_results:
        if isinstance(r, dict):
            parsed_results.append(cast("dict[str, Any]", r))
        elif isinstance(r, str):
            try:
                parsed = ast.literal_eval(r)
            except (ValueError, SyntaxError):
                parsed_results.append({"raw": r, "parse_error": True})
            else:
                if isinstance(parsed, dict):
                    parsed_results.append(cast("dict[str, Any]", parsed))
                else:
                    parsed_results.append({"raw": r, "parse_error": True})
        else:
            parsed_results.append({"raw": str(r)})
    parsed_results.extend(fix_results)

    fix_output_data: dict[str, Any] = {
        "dry_run": dry_run,
        "finding_id": finding_id,
        "fixed": sum(1 for r in parsed_results if r.get("success")),
        "failed": sum(1 for r in parsed_results if not r.get("success")),
        "success_rate": 0.0,
        "results": parsed_results,
    }
    total = fix_output_data["fixed"] + fix_output_data["failed"]
    fix_output_data["success_rate"] = (fix_output_data["fixed"] / total * 100) if total else 0.0

    if output_format == "json":
        _write_output(fix_output_data, output_format, output, console)
    else:
        console.print("\n[bold]Fix Summary:[/bold]")
        console.print(f"  Dry run: {dry_run}")
        console.print(
            f"  Fixed: [green]{fix_output_data['fixed']}[/green] | "
            f"Failed: [red]{fix_output_data['failed']}[/red] | "
            f"Success rate: {fix_output_data['success_rate']:.1f}%"
        )


def _load_cached_finding(scan_path: Path, finding_id: str) -> dict[str, Any] | None:
    """Load one finding from the last serialization-safe scan cache."""
    cache_path = scan_path / ".seraph-cache" / "last_scan.json"
    if not cache_path.is_file():
        return None

    try:
        payload = json.loads(cache_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logging.getLogger(__name__).debug(
            "Failed to read explanations cache %s: %s", cache_path, exc
        )
        return None

    records = payload.get("findings", []) if isinstance(payload, dict) else []
    if not isinstance(records, list):
        return None

    target = str(finding_id).strip().lower()
    for record in records:
        if not isinstance(record, dict):
            continue
        candidate = str(record.get("id") or record.get("finding_id") or "").strip().lower()
        rule_id = str(record.get("rule_id") or "").strip().lower()
        if target in {candidate, rule_id} or target in candidate or target in rule_id:
            return record
    return None


def _render_scan_explanations(findings: list[Finding], output_format: str) -> None:
    """Render bounded explanations without corrupting machine-readable stdout."""
    explain_console = progress_console if output_format in MACHINE_OUTPUT_FORMATS else console
    engine = ExplanationEngine()

    explain_console.print("\n[bold cyan]Generating Explanations...[/bold cyan]")
    for shown, finding in enumerate(findings):
        if shown >= 3:
            break

        metadata = getattr(finding, "metadata", None)
        report: dict[str, Any] | None = None
        if isinstance(metadata, dict):
            cached = metadata.get("explanation")
            if isinstance(cached, dict):
                report = cached

        if report is None:
            report = engine.build_report(finding)

        finding_id = str(report.get("finding_id") or getattr(finding, "id", "") or "unknown")
        title = str(report.get("title") or getattr(finding, "title", "") or finding_id)
        detail = str(report.get("detail") or report.get("message") or "").strip()
        severity = str(report.get("effective_severity") or report.get("severity") or "info").upper()
        category = str(report.get("category") or "unknown").upper()

        content = f"Severity: {severity}\nCategory: {category}\n\n{detail}"
        explain_console.print(
            Panel(content, title=f"{finding_id} — {title}", border_style="cyan", expand=False)
        )


def _cmd_explain(
    finding_id: str,
    output_format: str,
    output: str | None,
    verbose: bool,
    path: str = ".",
) -> None:
    """Explain a finding from the last scan's serialized, secret-safe result."""
    setup_logging(verbose)
    scan_path = Path(path).resolve()
    finding = _load_cached_finding(scan_path, finding_id)

    if finding is None:
        message = (
            f"No explanation available: finding '{finding_id}' was not found in the last scan cache at "
            f"{scan_path / '.seraph-cache' / 'last_scan.json'}. "
            "Run `seraph-guard scan --path <repo> --explain` first."
        )
        if output_format == "json":
            _write_output(
                {
                    "schema": "seraph-explanation-v1",
                    "status": "not_found",
                    "finding_id": finding_id,
                    "message": message,
                },
                output_format,
                output,
                console,
            )
        else:
            console.print(f"[red]{message}[/red]")
        return

    engine = ExplanationEngine()
    report = engine.build_report(finding)

    if output_format == "json":
        _write_output(report, output_format, output, console)
        return

    detail = str(
        report.get("detail") or report.get("explanation") or report.get("message") or ""
    ).strip()
    title = str(report.get("title") or finding_id)
    severity = str(report.get("effective_severity") or report.get("severity") or "info").upper()
    category = str(report.get("category") or "unknown").upper()
    header_text = f"{finding_id} — {title}"
    content = f"Severity: {severity}\nCategory: {category}\n\n{detail}"
    panel = Panel(content, title=header_text, border_style="cyan", expand=False)
    console.print(panel)

    if output:
        Path(output).write_text(detail + "\n", encoding="utf-8")
        console.print(f"[green]Explanation written to {output}[/green]")


def _cmd_report(
    path: str, report_format: str, output: str, verbose: bool, config_path: str | None = None
) -> None:
    setup_logging(verbose)
    scan_path = Path(path).resolve()
    console.print("\n[bold blue]Seraph Guard Report Generator[/bold blue]")
    console.print(f"[dim]Path: {scan_path}[/dim]\n")

    cli_config = ConfigLoader.load(str(scan_path), config_path)

    console.print("[bold]Step 1/2:[/bold] Running scan...")
    config = SeraphConfig(scan_path=scan_path)
    _resolve_config_paths(config, scan_path)
    if "timeout" in cli_config and hasattr(config.scanners, "timeout_seconds"):
        config.scanners.timeout_seconds = cli_config["timeout"]
    if "policies_dir" in cli_config and hasattr(config, "policies_dir"):
        p = Path(cli_config["policies_dir"])
        config.policies_dir = p if p.is_absolute() else scan_path / p
    if "auto_policies_dir" in cli_config and hasattr(config, "auto_policies_dir"):
        p = Path(cli_config["auto_policies_dir"])
        config.auto_policies_dir = p if p.is_absolute() else scan_path / p
    if hasattr(config, "policies_dir"):
        pd = Path(config.policies_dir)
        if not pd.exists():
            builtin = Path(__file__).parent.parent.parent.parent / "policies" / "builtin"
            if builtin.exists():
                config.policies_dir = builtin
                if hasattr(config, "auto_policies_dir"):
                    config.auto_policies_dir = builtin.parent / "auto-generated"

    # Propagate SBOM config from YAML to the config object
    sbom_cfg = cli_config.get("sbom", {})
    if isinstance(sbom_cfg, dict):
        for key in (
            "include_dev_dependencies",
            "deduplicate_across_manifests",
            "chunk_size",
            "max_dependencies",
            "quick_mode",
        ):
            if key in sbom_cfg:
                setattr(config.sbom, key, sbom_cfg[key])

    discovery = RepoDiscovery(scan_path)
    profile = discovery.discover()
    context = ScanContext(
        path=str(scan_path), is_git_repo=profile.is_git_repo, config=config, profile=profile
    )
    scanners = build_scanners(config)
    scheduler = Scheduler(config)
    pipeline_result = _run_pipeline(scheduler, context, scanners)

    findings = list(pipeline_result.layer2.findings)

    if report_format == "dashboard":
        try:
            from seraph.output.dashboard import launch_web_dashboard

            console.print("\n[bold]Step 2/2:[/bold] Generating Causal Blast Radius Graph...")
            ranker = CausalRanker()
            ranker.rank(findings)
            build_graph = getattr(ranker, "build_causal_graph", None)
            serialize_graph = getattr(ranker, "serialize_causal_graph", None)
            if build_graph and serialize_graph:
                graph = build_graph(findings)
                palantir_json = serialize_graph(graph)
            else:
                nodes = [
                    {
                        "id": getattr(finding, "id", str(i)),
                        "type": "finding",
                        "severity": _severity_to_str(_finding_effective_severity(finding)),
                        "title": getattr(finding, "title", ""),
                    }
                    for i, finding in enumerate(findings)
                ]
                palantir_json = {"nodes": nodes, "edges": []}
            launch_web_dashboard(palantir_json)
            return
        except ImportError as e:
            console.print(f"[red]Dashboard unavailable: {e}[/red]")
            return

    console.print(f"\n[bold]Step 2/2:[/bold] Generating {report_format} report...")
    metadata = {"scan_path": str(scan_path), "duration_ms": pipeline_result.scan_duration_ms}
    reporter = ReportGenerator(findings, metadata)
    out_path = Path("")
    if report_format == "html":
        out_path = Path(output + ".html")
        reporter.generate_html(out_path)
    elif report_format == "markdown":
        out_path = Path(output + ".md")
        reporter.generate_markdown(out_path)
    elif report_format == "executive":
        out_path = Path(output + "-executive.txt")
        reporter.generate_executive_summary(out_path)
    console.print(f"\n[bold green]Report generated: {out_path}[/bold green]\n")


def _cmd_status(path: str) -> None:
    from seraph.intelligence.learning import AdaptiveLearningEngine

    scan_path = Path(path).resolve()
    learning = AdaptiveLearningEngine(cache_dir=scan_path / ".seraph-learn")
    summary = learning.get_team_summary()

    console.print(f"\n[bold blue]Seraph Guard Learning Status ({scan_path.name})[/bold blue]\n")
    console.print(f"  Total findings seen:       {summary.get('total_findings_seen', 0)}")
    console.print(f"  Total findings fixed:      {summary.get('total_findings_fixed', 0)}")
    console.print(f"  Total findings suppressed: {summary.get('total_findings_suppressed', 0)}")
    console.print(f"  Mean time to fix:          {summary.get('mean_time_to_fix_hours', 0.0):.1f}h")
    console.print(f"  Learned patterns:          {summary.get('learned_patterns', 0)}")
    console.print(f"  Team Sync patterns:        {summary.get('team_sync_patterns', 0)}")
    fix_rates = summary.get("fix_rate_by_severity", {})
    if fix_rates:
        console.print("\n  Fix rates by severity:")
        for sev, data in fix_rates.items():
            total = data.get("total", 0)
            fixed = data.get("fixed", 0)
            rate = int(fixed / total * 100) if total > 0 else 0
            console.print(f"    {sev}: {rate}% ({fixed}/{total})")
    else:
        console.print("\n  [dim]No fix data yet. Run scans to build history.[/dim]")


def _cmd_config() -> None:
    cfg = SeraphConfig()
    console.print("\n[bold blue]Seraph Guard Configuration[/bold blue]\n")
    console.print("[bold]Scanner Settings:[/bold]")
    console.print("  Secret Scanner:   Native (Entropy + Regex, Zero Dependencies)")
    console.print("  SBOM Scanner:     Native (OSV.dev API, Zero Dependencies)")
    console.print("  IaC Scanner:      Available (Direct Import)")
    console.print("  UFIC Engine:      Available (Direct Import)")
    console.print(f"  Timeout:          {cfg.scanners.timeout_seconds}s")
    console.print(f"  Parallel workers: {cfg.scanners.parallel_workers}\n")
    console.print("[bold]Intelligence Settings:[/bold]")
    console.print(f"  Conformal alpha:  {cfg.intelligence.conformal_alpha}")
    console.print(f"  Learning enabled: {cfg.intelligence.learning_enabled}")
    console.print(f"  Causal depth:     {cfg.intelligence.causal_depth}\n")
    console.print("[bold]Cache Settings:[/bold]")
    console.print(f"  Enabled:   {cfg.cache.enabled}")
    console.print(f"  Directory: {cfg.cache.directory}")
    console.print(f"  TTL:       {cfg.cache.ttl_seconds}s\n")
    console.print("[bold]Fail Settings:[/bold]")
    console.print(f"  Fail on severity:  {cfg.fail.fail_on_severity}")
    console.print(f"  Ignore suppressed: {cfg.fail.ignore_suppressed}\n")
    console.print("[bold]Policy Paths:[/bold]")
    console.print(f"  Built-in:       {cfg.policies_dir}")
    console.print(f"  Auto-generated: {cfg.auto_policies_dir}\n")


def _cmd_cache(clear: bool, info: bool) -> None:
    cache_config = CacheConfig()
    scan_cache = ScanCache(cache_config)
    if clear:
        scan_cache.clear()
        console.print("[green]Scan cache cleared.[/green]")
    elif info:
        console.print("\n[bold blue]Cache Info[/bold blue]\n")
        console.print(f"  Directory: {cache_config.directory}")
        console.print(f"  Entries:   {scan_cache.size}")
        console.print(f"  TTL:       {cache_config.ttl_seconds}s")
        console.print(f"  Enabled:   {cache_config.enabled}\n")
    else:
        console.print("[yellow]Use --clear or --info[/yellow]")


def _cmd_init(path: str) -> None:
    init_path = Path(path).resolve()
    console.print(f"\n[bold blue]Initializing Seraph Guard in: {init_path}[/bold blue]\n")
    dirs_to_create = [
        init_path / ".seraph-learn",
        init_path / ".seraph-cache",
        init_path / "policies" / "auto-generated",
    ]
    for d in dirs_to_create:
        d.mkdir(parents=True, exist_ok=True)
        console.print(f"  Created: {d.relative_to(init_path)}")
    config_path = init_path / ".seraph-guard.yaml"
    if not config_path.exists():
        default_config = """# Seraph Guard Configuration
severity: medium
format: table
timeout: 900
exit_code: false
rank_by_impact: false
learn: false

scanners:
  - secrets
  - sbom
  - policy
  - pattern
  - iac

ignore:
  - "**/node_modules/**"
  - "**/vendor/**"
  - "**/dist/**"
  - "**/build/**"
  - "**/.git/**"
  - "**/.next/**"
  - "**/*.min.js"
  - "**/*.gen.go"
  - "**/__pycache__/**"
  - "**/coverage/**"
  - "**/.tox/**"
  - "**/.pytest_cache/**"
  - "**/.mypy_cache/**"
  - "**/.ruff_cache/**"
  - "**/.eslintcache"
  - "**/.parcel-cache/**"
  - "**/.turbo/**"
  - "**/target/debug/**"
  - "**/target/release/**"
  - "**/.DS_Store"
  - "**/Thumbs.db"
  - "**/examples/**"
  - "**/fixtures/**"
  - "**/*.test.js"
  - "**/*.spec.ts"
  - "**/bench/**"
  - "**/e2e/**"
  - "**/__testfixtures__/**"
  - "**/.github/**"

suppression:
  enabled: true
  test_files: true
  framework_internals: true
  build_scripts: true
  examples: true
  documentation: true

output:
  show_suppressed_count: true
  show_blast_radius: true
  show_conformal_prediction: true
  max_findings: 0
  max_explanations: 10

sbom:
  include_dev_dependencies: false
  deduplicate_across_manifests: true

secrets:
  validate_live: false
  min_entropy: 3.5

policy:
  compliance_frameworks:
    - CIS
    - SOC2

pattern:
  language_aware: true
  framework_context: true

intelligence:
  ufic_enabled: true
  conformal_alpha: 0.1
  min_calibration_samples: 30
  causal_depth: 3
"""
        config_path.write_text(default_config, encoding="utf-8")
        console.print(f"  Created: {config_path.name}")
    else:
        console.print(f"  Skipped: {config_path.name} (already exists)")
    gitignore_path = init_path / ".gitignore"
    seraph_entries = "\n# Seraph Guard\n.seraph-learn/\n.seraph-cache/\n"
    if gitignore_path.exists():
        content = gitignore_path.read_text(encoding="utf-8")
        if ".seraph-learn/" not in content:
            with gitignore_path.open("a", encoding="utf-8") as f:
                f.write(seraph_entries)
            console.print("  Updated: .gitignore")
        else:
            console.print("  Skipped: .gitignore (already configured)")
    else:
        gitignore_path.write_text(seraph_entries, encoding="utf-8")
        console.print("  Created: .gitignore")
    console.print("\n[bold green]Seraph Guard initialized successfully![/bold green]")
    console.print("[dim]Run 'seraph guard scan --path .' to start your first scan.[/dim]\n")


def _cmd_ci(
    path: str,
    output_format: str,
    fail_on: str,
    verbose: bool,
    output_file: str | None,
    timeout: int | None,
    config_path: str | None,
    exit_code: bool = False,
) -> int:
    scan_path = Path(path).resolve()
    scan_console = _get_scan_console(output_format, output_file)
    setup_logging(verbose, scan_console)
    console = scan_console
    console.print(f"\n[bold blue]Seraph Guard CI Mode v{__version__}[/bold blue]")
    console.print(f"[dim]Scanning: {scan_path}  |  Optimized for CI pipelines[/dim]\n")

    cli_config = ConfigLoader.load(str(scan_path), config_path)
    cli_config["suppression"] = cli_config.get("suppression", {})
    cli_config["suppression"]["enabled"] = True

    gitleaks_config = _load_gitleaks_toml(scan_path)
    if gitleaks_config:
        cli_config["ignore"] = list(
            set(cli_config.get("ignore", []) + gitleaks_config.get("ignore", []))
        )

    config_obj = SeraphConfig.from_cli_args(
        path=str(scan_path),
        output_format=output_format,
        fail_on=fail_on,
        rank_by_impact=False,
        learn=False,
        verbose=verbose,
    )
    _resolve_config_paths(config_obj, scan_path)
    if timeout:
        config_obj.scanners.timeout_seconds = timeout
    else:
        config_obj.scanners.timeout_seconds = min(config_obj.scanners.timeout_seconds, 300)

    # Propagate SBOM config from YAML to the config object
    sbom_cfg = cli_config.get("sbom", {})
    if isinstance(sbom_cfg, dict):
        for key in (
            "include_dev_dependencies",
            "deduplicate_across_manifests",
            "chunk_size",
            "max_dependencies",
            "quick_mode",
        ):
            if key in sbom_cfg:
                setattr(config_obj.sbom, key, sbom_cfg[key])

    discovery = RepoDiscovery(scan_path)
    profile = discovery.discover()
    context = ScanContext(
        path=str(scan_path), is_git_repo=profile.is_git_repo, config=config_obj, profile=profile
    )
    scanners = build_scanners(config_obj)
    scheduler = Scheduler(config_obj)
    pipeline_result = _run_pipeline(
        scheduler, context, scanners, {"suppression": True, "deduplication": True}
    )
    scanner_errors = _get_pipeline_errors(pipeline_result)

    findings = list(pipeline_result.layer2.findings)
    findings = apply_severity_filter(findings, cli_config.get("severity", "medium"))

    metadata = {
        "scan_path": str(scan_path),
        "duration_ms": pipeline_result.scan_duration_ms,
        "scanners": pipeline_result.scanners_executed,
        "version": __version__,
        "suppressed_count": pipeline_result.total_suppressed,
        "total_raw": pipeline_result.total_raw_findings,
        "scanner_errors": scanner_errors,
        "scan_status": "failed" if scanner_errors else "completed",
    }

    _render_scan_output(
        output_format,
        pipeline_result.layer1.findings,
        findings,
        pipeline_result.layer2.suppressed_findings,
        metadata,
        config_obj,
        False,
        output_file,
        pipeline_result.scanner_status,
        cli_config,
    )
    return _evaluate_build_result(
        findings,
        pipeline_result.layer2.suppressed_findings,
        pipeline_result.layer2.suppression_stats,
        fail_on,
        exit_code,
        cli_config,
        output_console=scan_console,
        scanner_errors=scanner_errors,
    )


def _cmd_sync(
    path: str, sync_file: str | None, export_only: bool, import_only: bool, verbose: bool
) -> None:
    from seraph.intelligence.learning import AdaptiveLearningEngine

    setup_logging(verbose)
    scan_path = Path(path).resolve()
    console.print("\n[bold blue]Seraph Guard Team Sync[/bold blue]")
    console.print(f"[dim]Path: {scan_path}[/dim]\n")
    learning = AdaptiveLearningEngine(cache_dir=scan_path / ".seraph-learn")
    sync_path = Path(sync_file) if sync_file else (scan_path / ".seraph-learn" / "team-sync.json")

    if export_only:
        console.print("[bold]Exporting privacy-safe learning data...[/bold]")
        export_data = learning.get_privacy_safe_export()
        try:
            sync_path.parent.mkdir(parents=True, exist_ok=True)
            sync_path.write_text(
                json.dumps({"team_sync": export_data, "version": __version__}, indent=2),
                encoding="utf-8",
            )
        except PermissionError:
            console.print(f"[red]❌ Permission denied: cannot write to {sync_path}.[/red]")
            console.print(
                "[yellow]Ensure the directory exists and is writable, or use --file to specify a different path.[/yellow]"
            )
            sys.exit(1)
        console.print(f"[green]✅ Exported {len(export_data)} patterns to {sync_path}[/green]")
        console.print("[dim]Commit this file to your shared repository or upload to S3.[/dim]")
        return

    if import_only:
        if not sync_path.exists():
            console.print(f"[red]❌ Sync file not found: {sync_path}[/red]")
            return
        console.print(f"[bold]Importing team data from {sync_path}...[/bold]")
        data = json.loads(sync_path.read_text(encoding="utf-8"))
        team_data = data.get("team_sync", [])
        merged = learning.merge_team_sync(team_data)
        console.print(
            f"[green]✅ Merged {merged} new team patterns. "
            f"Total team patterns: {len(learning.state.get('team_sync', {}))}[/green]"
        )
        return

    if sync_path.exists():
        console.print(f"[bold]Importing team data from {sync_path}...[/bold]")
        data = json.loads(sync_path.read_text(encoding="utf-8"))
        team_data = data.get("team_sync", [])
        merged = learning.merge_team_sync(team_data)
        console.print(f"  Imported {merged} new team patterns.")
    else:
        console.print(
            f"[dim]No existing team sync file found at {sync_path}. Skipping import.[/dim]"
        )

    console.print("[bold]Exporting privacy-safe learning data...[/bold]")
    export_data = learning.get_privacy_safe_export()
    try:
        sync_path.parent.mkdir(parents=True, exist_ok=True)
        sync_path.write_text(
            json.dumps({"team_sync": export_data, "version": __version__}, indent=2),
            encoding="utf-8",
        )
    except PermissionError:
        console.print(f"[red]❌ Permission denied: cannot write to {sync_path}.[/red]")
        console.print(
            "[yellow]Ensure the directory exists and is writable, or use --file to specify a different path.[/yellow]"
        )
        sys.exit(1)
    console.print(
        f"[green]✅ Sync complete. {len(export_data)} patterns exported to {sync_path}[/green]"
    )


def _cmd_lsp(_stdio: bool = True, socket: str | None = None, port: int | None = None) -> None:
    """Start the Language Server Protocol (LSP) backend for real-time IDE integration."""
    if port is not None:
        console.print(
            "[yellow]Warning: --port is not supported by this LSP implementation; using stdio.[/yellow]"
        )
    if socket is not None:
        console.print(
            "[yellow]Warning: --socket is not supported by this LSP implementation; using stdio.[/yellow]"
        )

    try:
        start_lsp()
    except Exception as e:
        console.print(f"[red]LSP Server crashed: {e}[/red]")
        sys.exit(1)


# ═══════════════════════════════════════════════════════════════
# Click CLI Definitions
# ═══════════════════════════════════════════════════════════════


@click.group(
    name="seraph",
    epilog="""
Examples:
  seraph guard scan --path .
  seraph guard scan --secret-only
  seraph guard scan --sbom-only
  seraph guard scan --git-history
  seraph guard scan --image python:3.9-slim
  seraph guard scan --learn --rank-by-impact
  seraph guard scan --no-suppress --format json -o raw.json
  seraph guard scan --show-suppressed
  seraph guard scan --explain
  seraph guard report --path . --format dashboard
  seraph guard sync --export
  seraph guard lsp
  seraph guard status
  seraph guard config
  seraph guard cache --clear
  seraph guard init --path .
  seraph guard ci --path .
    """,
    context_settings={"help_option_names": ["-h", "--help"]},
)
@click.version_option(version=__version__, prog_name="seraph")
def seraph_main() -> None:
    """Seraph — Security Intelligence Platform"""


@seraph_main.group()
def guard() -> None:
    """Protect What Is Yours: Scan your code, repos, and infrastructure."""


@guard.command("scan")
@click.option("--path", "-p", default=".", help="Path to scan", type=click.Path(exists=True))
@click.option("--secret-only", is_flag=True, help="Run only the SecretScanner (3-4x faster)")
@click.option("--sbom-only", is_flag=True, help="Run only the SBOMScanner for dependency analysis")
@click.option(
    "--git-history",
    is_flag=True,
    default=False,
    help="Scan git history for leaked secrets (fast diff-based)",
)
@click.option(
    "--image", default=None, help="Scan a Docker/OCI container image (e.g., alpine:latest)"
)
@click.option(
    "--format",
    "-f",
    "output_format",
    default="table",
    type=click.Choice(["table", "json", "sarif", "junit", "github"]),
    help="Output format",
)
@click.option(
    "--fail-on",
    default="high",
    type=click.Choice(["critical", "high", "medium", "low"]),
    help="Exit non-zero at this severity threshold",
)
@click.option(
    "--rank-by-impact", is_flag=True, default=False, help="Rank findings by blast-radius impact"
)
@click.option(
    "--learn", is_flag=True, default=False, help="Enable adaptive learning and auto-suppression"
)
@click.option("--verbose", "-v", is_flag=True, default=False, help="Verbose output")
@click.option("--output-file", "-o", default=None, type=click.Path(), help="Write output to file")
@click.option(
    "--exclude",
    multiple=True,
    help="Exclude scanners: secrets, sbom, policy, pattern, iac, ufic, taint",
)
@click.option("--only", multiple=True, help="Run only specific scanners")
@click.option("--severity", default="medium", help="Minimum severity to include in output")
@click.option("--timeout", type=int, default=None, help="Override scanner timeout (seconds)")
@click.option(
    "--baseline",
    default=None,
    type=click.Path(exists=True),
    help="Baseline JSON to show only new findings",
)
@click.option(
    "--exit-code",
    is_flag=True,
    default=False,
    help="Exit with code 1 if any findings exist (for CI gates)",
)
@click.option(
    "--config", "-c", default=None, type=click.Path(), help="Path to .seraph-guard.yaml config file"
)
@click.option(
    "--ignore", multiple=True, default=[], help="Ignore pattern (can be used multiple times)"
)
@click.option(
    "--no-suppress",
    is_flag=True,
    default=False,
    help="Disable suppression engine (show all raw findings)",
)
@click.option("--dedup/--no-dedup", default=True, help="Enable deduplication (default: enabled)")
@click.option(
    "--include-suppressed",
    is_flag=True,
    default=False,
    help="Include suppressed findings in JSON/SARIF/JUnit output",
)
@click.option(
    "--show-suppressed",
    is_flag=True,
    default=False,
    help="Print suppressed findings to console after production output",
)
@click.option(
    "--explain",
    is_flag=True,
    default=False,
    help="Generate explanations for findings",
)
def guard_scan(
    path: str,
    secret_only: bool,
    sbom_only: bool,
    git_history: bool,
    image: str | None,
    output_format: str,
    fail_on: str,
    rank_by_impact: bool,
    learn: bool,
    verbose: bool,
    output_file: str | None,
    exclude: tuple[str, ...],
    only: tuple[str, ...],
    severity: str,
    timeout: int | None,
    baseline: str | None,
    exit_code: bool,
    config: str | None,
    ignore: tuple[str, ...],
    no_suppress: bool,
    dedup: bool,
    include_suppressed: bool,
    show_suppressed: bool,
    explain: bool,
) -> None:
    """Run a security scan on the specified path."""
    code = _cmd_scan(
        path,
        secret_only,
        sbom_only,
        output_format,
        fail_on,
        rank_by_impact,
        learn,
        verbose,
        output_file,
        exclude,
        only,
        severity,
        timeout,
        baseline,
        exit_code,
        config,
        ignore,
        no_suppress,
        dedup,
        include_suppressed,
        show_suppressed,
        git_history,
        image,
        explain,
    )
    sys.exit(code)


@guard.command("report")
@click.option("--path", "-p", default=".", help="Path to scan", type=click.Path(exists=True))
@click.option(
    "--format",
    "-f",
    "report_format",
    default="html",
    type=click.Choice(["html", "markdown", "executive", "dashboard"]),
    help="Report format",
)
@click.option("--output", "-o", default="seraph-report", help="Output filename")
@click.option("--verbose", "-v", is_flag=True, help="Verbose output")
@click.option(
    "--config", "-c", default=None, type=click.Path(), help="Path to .seraph-guard.yaml config file"
)
def guard_report(
    path: str, report_format: str, output: str, verbose: bool, config: str | None
) -> None:
    """Generate a scan report in HTML, Markdown, Executive summary, or Interactive Dashboard."""
    _cmd_report(path, report_format, output, verbose, config)


@guard.command("sync")
@click.option("--path", "-p", default=".", help="Repository path", type=click.Path(exists=True))
@click.option(
    "--file",
    "sync_file",
    default=None,
    help="Path to team sync file (default: .seraph-learn/team-sync.json)",
)
@click.option("--export", "export_only", is_flag=True, help="Only export local data")
@click.option("--import", "import_only", is_flag=True, help="Only import team data")
@click.option("--verbose", "-v", is_flag=True, help="Verbose output")
def guard_sync(
    path: str, sync_file: str | None, export_only: bool, import_only: bool, verbose: bool
) -> None:
    """Sync adaptive learning data with your team (Privacy-preserving)."""
    _cmd_sync(path, sync_file, export_only, import_only, verbose)


@guard.command("lsp")
@click.option(
    "--stdio", is_flag=True, default=True, help="Use stdio for LSP communication (default)"
)
@click.option("--socket", type=str, default=None, help="Use Unix socket path for LSP communication")
@click.option("--port", type=int, default=None, help="Port for TCP LSP communication")
def guard_lsp(stdio: bool, socket: str | None, port: int | None) -> None:
    """Start the Language Server Protocol (LSP) backend for real-time IDE integration."""
    _cmd_lsp(_stdio=stdio, socket=socket, port=port)


@guard.command("status")
@click.option("--path", "-p", default=".", help="Repository path", type=click.Path(exists=True))
def guard_status(path: str) -> None:
    """Show the adaptive learning engine's current state."""
    _cmd_status(path)


@guard.command("config")
def guard_config() -> None:
    """Display current configuration values."""
    _cmd_config()


@guard.command("cache")
@click.option("--clear", is_flag=True, help="Clear the entire scan cache")
@click.option("--info", is_flag=True, help="Show cache statistics")
def guard_cache(clear: bool, info: bool) -> None:
    """Manage the incremental scan cache."""
    _cmd_cache(clear, info)


@guard.command("init")
@click.option("--path", "-p", default=".", help="Path to initialize")
def guard_init(path: str) -> None:
    """Initialize Seraph Guard in the target repository."""
    _cmd_init(path)


@guard.command("ci")
@click.option("--path", "-p", default=".", help="Path to scan", type=click.Path(exists=True))
@click.option(
    "--format",
    "-f",
    "output_format",
    default="sarif",
    type=click.Choice(["table", "json", "sarif", "junit", "github"]),
    help="Output format",
)
@click.option(
    "--fail-on",
    default="critical",
    type=click.Choice(["critical", "high", "medium", "low"]),
    help="Exit non-zero at this severity threshold",
)
@click.option("--verbose", "-v", is_flag=True, default=False, help="Verbose output")
@click.option("--output-file", "-o", default=None, type=click.Path(), help="Write output to file")
@click.option("--timeout", type=int, default=None, help="Override scanner timeout (seconds)")
@click.option(
    "--config", "-c", default=None, type=click.Path(), help="Path to .seraph-guard.yaml config file"
)
@click.option(
    "--exit-code",
    is_flag=True,
    default=False,
    help="Exit with code 1 if any findings exist (for CI gates)",
)
def guard_ci(
    path: str,
    output_format: str,
    fail_on: str,
    verbose: bool,
    output_file: str | None,
    timeout: int | None,
    config: str | None,
    exit_code: bool,
) -> None:
    """CI/CD mode. Runs a scan optimized for CI pipelines."""
    code = _cmd_ci(path, output_format, fail_on, verbose, output_file, timeout, config, exit_code)
    sys.exit(code)


# ═══════════════════════════════════════════════════════════════
# Standalone Entry Point (seraph-guard)
# ═══════════════════════════════════════════════════════════════


@click.group(
    name="seraph-guard",
    epilog="""
Examples:
  seraph-guard --version
  seraph-guard scan
  seraph-guard scan --path .
  seraph-guard scan --path . --git-history
  seraph-guard scan --path . --image alpine:latest
  seraph-guard scan --path . --format json
  seraph-guard scan --path . --format table
  seraph-guard scan --path . --format sarif
  seraph-guard scan --path . --format github
  seraph-guard scan --path . --learn
  seraph-guard scan --path . --learn --rank-by-impact
  seraph-guard scan --learn --rank-by-impact --format sarif --path .
  seraph-guard scan --path . --verbose
  seraph-guard scan --path . --output-file results.json
  seraph-guard scan --path . --fail-on high
  seraph-guard scan --path . --no-suppress --format json -o raw.json
  seraph-guard scan --path . --show-suppressed
  seraph-guard scan --path . --explain
  seraph-guard fix --all --dry-run
  seraph-guard fix --finding F001
  seraph-guard explain F001
  seraph-guard report --format dashboard
  seraph-guard sync --export
  seraph-guard lsp
  seraph-guard ci --path .
  seraph-guard status
  seraph-guard config
  seraph-guard cache --info
  seraph-guard cache --clear
  seraph-guard init --path .
    """,
    context_settings={"help_option_names": ["-h", "--help"]},
)
@click.version_option(version=__version__, prog_name="seraph-guard")
def seraph_guard_main() -> None:
    """Seraph Guard — Direct entry point. All commands work standalone."""


@seraph_guard_main.command("scan")
@click.option("--path", "-p", default=".", help="Path to scan", type=click.Path(exists=True))
@click.option("--secret-only", is_flag=True, help="Run only the SecretScanner (3-4x faster)")
@click.option("--sbom-only", is_flag=True, help="Run only the SBOMScanner for dependency analysis")
@click.option(
    "--git-history",
    is_flag=True,
    default=False,
    help="Scan git history for leaked secrets (fast diff-based)",
)
@click.option(
    "--image", default=None, help="Scan a Docker/OCI container image (e.g., alpine:latest)"
)
@click.option(
    "--format",
    "-f",
    "output_format",
    default="table",
    type=click.Choice(["table", "json", "sarif", "junit", "github"]),
    help="Output format",
)
@click.option(
    "--fail-on",
    default="high",
    type=click.Choice(["critical", "high", "medium", "low"]),
    help="Exit non-zero at this severity threshold",
)
@click.option(
    "--rank-by-impact", is_flag=True, default=False, help="Rank findings by blast-radius impact"
)
@click.option(
    "--learn", is_flag=True, default=False, help="Enable adaptive learning and auto-suppression"
)
@click.option("--verbose", "-v", is_flag=True, default=False, help="Verbose output")
@click.option("--output-file", "-o", default=None, type=click.Path(), help="Write output to file")
@click.option(
    "--exclude",
    multiple=True,
    help="Exclude scanners: secrets, sbom, policy, pattern, iac, ufic, taint",
)
@click.option("--only", multiple=True, help="Run only specific scanners")
@click.option("--severity", default="medium", help="Minimum severity to include in output")
@click.option("--timeout", type=int, default=None, help="Override scanner timeout (seconds)")
@click.option(
    "--baseline",
    default=None,
    type=click.Path(exists=True),
    help="Baseline JSON to show only new findings",
)
@click.option(
    "--exit-code",
    is_flag=True,
    default=False,
    help="Exit with code 1 if any findings exist (for CI gates)",
)
@click.option(
    "--config", "-c", default=None, type=click.Path(), help="Path to .seraph-guard.yaml config file"
)
@click.option(
    "--ignore", multiple=True, default=[], help="Ignore pattern (can be used multiple times)"
)
@click.option(
    "--no-suppress",
    is_flag=True,
    default=False,
    help="Disable suppression engine (show all raw findings)",
)
@click.option("--dedup/--no-dedup", default=True, help="Enable deduplication (default: enabled)")
@click.option(
    "--include-suppressed",
    is_flag=True,
    default=False,
    help="Include suppressed findings in JSON/SARIF/JUnit output",
)
@click.option(
    "--show-suppressed",
    is_flag=True,
    default=False,
    help="Print suppressed findings to console after production output",
)
@click.option(
    "--explain",
    is_flag=True,
    default=False,
    help="Generate explanations for findings",
)
def sg_scan(
    path: str,
    secret_only: bool,
    sbom_only: bool,
    git_history: bool,
    image: str | None,
    output_format: str,
    fail_on: str,
    rank_by_impact: bool,
    learn: bool,
    verbose: bool,
    output_file: str | None,
    exclude: tuple[str, ...],
    only: tuple[str, ...],
    severity: str,
    timeout: int | None,
    baseline: str | None,
    exit_code: bool,
    config: str | None,
    ignore: tuple[str, ...],
    no_suppress: bool,
    dedup: bool,
    include_suppressed: bool,
    show_suppressed: bool,
    explain: bool,
) -> None:
    """Run a security scan on the specified path."""
    code = _cmd_scan(
        path,
        secret_only,
        sbom_only,
        output_format,
        fail_on,
        rank_by_impact,
        learn,
        verbose,
        output_file,
        exclude,
        only,
        severity,
        timeout,
        baseline,
        exit_code,
        config,
        ignore,
        no_suppress,
        dedup,
        include_suppressed,
        show_suppressed,
        git_history,
        image,
        explain,
    )
    sys.exit(code)


@seraph_guard_main.command("fix")
@click.option("--path", "-p", default=".", help="Path to fix", type=click.Path(exists=True))
@click.option("--all", "fix_all", is_flag=True, help="Fix all auto-fixable findings")
@click.option("--finding", "finding_id", default=None, help="Fix a specific finding by ID")
@click.option("--dry-run", is_flag=True, help="Preview changes without applying")
@click.option(
    "--format",
    "-f",
    "output_format",
    default="table",
    type=click.Choice(["table", "json"]),
    help="Output format",
)
@click.option("--output", "-o", default=None, type=click.Path(), help="Write output to file")
@click.option("--verbose", "-v", is_flag=True, help="Verbose output")
@click.option(
    "--exclude",
    multiple=True,
    help="Exclude scanners: secrets, sbom, policy, pattern, iac, ufic, taint",
)
@click.option("--only", multiple=True, help="Run only specific scanners")
def sg_fix(
    path: str,
    fix_all: bool,
    finding_id: str | None,
    dry_run: bool,
    output_format: str,
    output: str | None,
    verbose: bool,
    exclude: tuple[str, ...],
    only: tuple[str, ...],
) -> None:
    """Auto-fix issues where possible."""
    _cmd_fix(
        path, fix_all, finding_id, dry_run, output_format, output, verbose, only, exclude, None
    )


@seraph_guard_main.command("explain")
@click.argument("finding_id", required=False)
@click.option("--finding", "finding_flag", default=None, help="Finding ID to explain (legacy flag)")
@click.option("--path", "-p", default=".", help="Repository path", type=click.Path(exists=True))
@click.option(
    "--format",
    "-f",
    "output_format",
    default="table",
    type=click.Choice(["table", "json"]),
    help="Output format",
)
@click.option("--output", "-o", default=None, type=click.Path(), help="Write output to file")
@click.option("--verbose", "-v", is_flag=True, help="Verbose output")
def sg_explain(
    finding_id: str | None,
    finding_flag: str | None,
    path: str,
    output_format: str,
    output: str | None,
    verbose: bool,
) -> None:
    """Explain a specific finding by its ID."""
    target = finding_id or finding_flag
    if not target:
        console.print("[red]Error: Provide a finding ID. Example: seraph-guard explain F001[/red]")
        sys.exit(1)
    _cmd_explain(target, output_format, output, verbose, path)


@seraph_guard_main.command("report")
@click.option("--path", "-p", default=".", help="Path to scan", type=click.Path(exists=True))
@click.option(
    "--format",
    "-f",
    "report_format",
    default="html",
    type=click.Choice(["html", "markdown", "executive", "dashboard"]),
    help="Report format",
)
@click.option("--output", "-o", default="seraph-report", help="Output filename")
@click.option("--verbose", "-v", is_flag=True, help="Verbose output")
def sg_report(path: str, report_format: str, output: str, verbose: bool) -> None:
    """Generate a scan report."""
    _cmd_report(path, report_format, output, verbose, None)


@seraph_guard_main.command("sync")
@click.option("--path", "-p", default=".", help="Repository path", type=click.Path(exists=True))
@click.option(
    "--file",
    "sync_file",
    default=None,
    help="Path to team sync file (default: .seraph-learn/team-sync.json)",
)
@click.option("--export", "export_only", is_flag=True, help="Only export local data")
@click.option("--import", "import_only", is_flag=True, help="Only import team data")
@click.option("--verbose", "-v", is_flag=True, help="Verbose output")
def sg_sync(
    path: str, sync_file: str | None, export_only: bool, import_only: bool, verbose: bool
) -> None:
    """Sync adaptive learning data with your team (Privacy-preserving)."""
    _cmd_sync(path, sync_file, export_only, import_only, verbose)


@seraph_guard_main.command("lsp")
@click.option(
    "--stdio", is_flag=True, default=True, help="Use stdio for LSP communication (default)"
)
@click.option("--socket", type=str, default=None, help="Use Unix socket path for LSP communication")
@click.option("--port", type=int, default=None, help="Port for TCP LSP communication")
def sg_lsp(stdio: bool, socket: str | None, port: int | None) -> None:
    """Start the Language Server Protocol (LSP) backend for real-time IDE integration."""
    _cmd_lsp(_stdio=stdio, socket=socket, port=port)


@seraph_guard_main.command("status")
@click.option("--path", "-p", default=".", help="Repository path", type=click.Path(exists=True))
def sg_status(path: str) -> None:
    """Show the adaptive learning engine's current state."""
    _cmd_status(path)


@seraph_guard_main.command("config")
def sg_config() -> None:
    """Display current configuration values."""
    _cmd_config()


@seraph_guard_main.command("cache")
@click.option("--clear", is_flag=True, help="Clear the entire scan cache")
@click.option("--info", is_flag=True, help="Show cache statistics")
def sg_cache(clear: bool, info: bool) -> None:
    """Manage the incremental scan cache."""
    _cmd_cache(clear, info)


@seraph_guard_main.command("init")
@click.option("--path", "-p", default=".", help="Path to initialize")
def sg_init(path: str) -> None:
    """Initialize Seraph Guard in the target repository."""
    _cmd_init(path)


@seraph_guard_main.command("ci")
@click.option("--path", "-p", default=".", help="Path to scan", type=click.Path(exists=True))
@click.option(
    "--format",
    "-f",
    "output_format",
    default="sarif",
    type=click.Choice(["table", "json", "sarif", "junit", "github"]),
    help="Output format",
)
@click.option(
    "--fail-on",
    default="critical",
    type=click.Choice(["critical", "high", "medium", "low"]),
    help="Exit non-zero at this severity threshold",
)
@click.option("--verbose", "-v", is_flag=True, default=False, help="Verbose output")
@click.option("--output-file", "-o", default=None, type=click.Path(), help="Write output to file")
@click.option("--timeout", type=int, default=None, help="Override scanner timeout (seconds)")
@click.option(
    "--config", "-c", default=None, type=click.Path(), help="Path to .seraph-guard.yaml config file"
)
@click.option(
    "--exit-code",
    is_flag=True,
    default=False,
    help="Exit with code 1 if any findings exist (for CI gates)",
)
def sg_ci(
    path: str,
    output_format: str,
    fail_on: str,
    verbose: bool,
    output_file: str | None,
    timeout: int | None,
    config: str | None,
    exit_code: bool,
) -> None:
    """CI/CD mode. Runs a scan optimized for CI pipelines."""
    code = _cmd_ci(path, output_format, fail_on, verbose, output_file, timeout, config, exit_code)
    sys.exit(code)


def main() -> None:
    """Main entry point that routes to the correct CLI based on how it was invoked."""
    prog = Path(sys.argv[0]).name
    if prog == "seraph-guard" or "seraph_guard" in prog or prog == "seraph-peak":
        seraph_guard_main()
    else:
        seraph_main()


if __name__ == "__main__":
    main()
