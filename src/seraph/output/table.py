from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from seraph.sources.repository.scanners.base import Finding, Severity


SEVERITY_COLORS = {
    Severity.CRITICAL: "bold red",
    Severity.HIGH: "red",
    Severity.MEDIUM: "yellow",
    Severity.LOW: "blue",
    Severity.INFO: "dim",
}

SEVERITY_ICONS = {
    Severity.CRITICAL: "🔴",
    Severity.HIGH: "🟠",
    Severity.MEDIUM: "🟡",
    Severity.LOW: "🔵",
    Severity.INFO: "⚪",
}


def _resolve_severity(finding: Finding) -> Severity:
    """Return effective_severity if set, otherwise fall back to severity, then INFO."""
    return (
        getattr(finding, "effective_severity", None)
        or getattr(finding, "severity", None)
        or Severity.INFO
    )


class TableOutput:
    """Renders findings as a rich terminal table."""

    def __init__(self, console: Console | None = None):
        self.console = console or Console()

    def render(
        self,
        findings: list[Finding],
        all_findings: list[Finding] | None = None,
        scanner_status: dict[str, str] | None = None,
    ) -> None:
        if not findings:
            self.console.print("[bold green]No production findings found.[/bold green]")
            return

        self._render_severity_distribution(findings)

        table = Table(
            title=f"Seraph Guard — Production Code Findings ({len(findings)} issues)",
            show_lines=True,
            title_style="bold",
            expand=True,
        )

        # --- ADDED ID COLUMN ---
        table.add_column("ID", style="dim", width=12, max_width=12)
        table.add_column("#", style="dim", width=4, justify="right")
        table.add_column("Severity", width=12)
        table.add_column("Scanner", width=13, style="cyan")
        table.add_column("Location", width=48, style="white", overflow="fold")
        table.add_column("Title", width=32, overflow="fold")
        table.add_column("Conformal Set", width=24, overflow="fold")
        table.add_column("Fix", width=4, justify="center")

        for finding in findings:
            sev = _resolve_severity(finding)
            severity_style = SEVERITY_COLORS.get(sev, "white")
            severity_icon = SEVERITY_ICONS.get(sev, "")
            severity_text = Text(
                f"{severity_icon} {sev.value.upper()}",
                style=severity_style,
            )
            fix_indicator = "✅" if getattr(finding, "fix_available", False) else "❌"
            rank_str = (
                str(getattr(finding, "causal_rank", ""))
                if getattr(finding, "causal_rank", None)
                else "-"
            )
            location = f"{getattr(finding, 'file', '')}:{getattr(finding, 'line', '')}"

            conf_set = getattr(finding, "conformal_set", None)
            if conf_set:
                conf_str = "{" + ", ".join(s.upper() for s in conf_set) + "}"
                conf_val = getattr(finding, "conformal_confidence", None)
                if conf_val:
                    conf_str += f" @ {int(conf_val * 100)}%"
            else:
                conf_str = "-"

            # --- EXTRACT AND TRUNCATE ID ---
            fid = getattr(finding, "id", "") or getattr(finding, "rule_id", "?")
            display_id = fid[:12] if len(fid) > 12 else fid

            table.add_row(
                display_id,  # <--- ADDED ID
                rank_str,
                severity_text,
                getattr(finding, "scanner", "")[:13],
                location,
                getattr(finding, "title", "")[:32],
                conf_str,
                fix_indicator,
            )

        self.console.print(table)

        if all_findings:
            test_sup = sum(1 for f in all_findings if getattr(f, "file_context", "") == "test")
            fw_sup = sum(
                1
                for f in all_findings
                if getattr(f, "file_context", "") == "framework"
                and _resolve_severity(f) == Severity.LOW
            )
            suppressed = sum(1 for f in all_findings if getattr(f, "is_suppressed", False))
            gaps = sum(1 for v in (scanner_status or {}).values() if str(v).startswith("✗"))
            self.console.print(
                f"\n[dim]Info: {test_sup} test findings suppressed  |  "
                f"{fw_sup} framework internals suppressed  |  "
                f"{suppressed} grouped suppressions  |  Scanner gaps: {gaps}[/dim]"
            )

    def _render_severity_distribution(self, findings: list[Finding]) -> None:
        counts: dict[Severity, int] = {}
        for f in findings:
            sev = _resolve_severity(f)
            counts[sev] = counts.get(sev, 0) + 1

        summary_parts = []
        for severity in [
            Severity.CRITICAL,
            Severity.HIGH,
            Severity.MEDIUM,
            Severity.LOW,
            Severity.INFO,
        ]:
            count = counts.get(severity, 0)
            if count > 0:
                icon = SEVERITY_ICONS.get(severity, "")
                color = SEVERITY_COLORS.get(severity, "white")
                summary_parts.append(f"[{color}]{icon} {severity.value}: {count}[/{color}]")

        summary = "  |  ".join(summary_parts)
        self.console.print(
            Panel(summary, title="Severity Distribution (Production Code)", border_style="blue")
        )

    def render_explanation(self, finding: Finding, explanation: str) -> None:
        sev = _resolve_severity(finding)
        severity_color = SEVERITY_COLORS.get(sev, "white")
        sev_str = sev.value.upper()
        rank = getattr(finding, "causal_rank", "-")
        panel_title = f"{sev_str} #{rank}: {explanation}"
        self.console.print(
            Panel(
                explanation,
                title=panel_title,
                border_style=severity_color,
                expand=True,
                padding=(1, 2),
            )
        )

    def render_fix_plan(self, plan: dict[str, Any]) -> None:
        # CausalRanker returns "steps", fallback to "plan" for safety
        steps = plan.get("steps", plan.get("plan", []))
        if not plan or not steps:
            self.console.print("[yellow]No fix plan generated.[/yellow]")
            return

        budget = plan.get("total_effort_minutes", plan.get("budget", 30))
        table = Table(
            title=f"Optimal Fix Plan ({budget} min budget) — multiplicative reduction",
            show_lines=True,
            title_style="bold",
            expand=True,
        )
        table.add_column("Ord", width=4, justify="right")
        table.add_column("Finding", width=35)
        table.add_column("Fix Command", width=48)
        table.add_column("Effort", width=8, justify="right")
        table.add_column("Blast Radius ↓", width=14, justify="right")

        for i, item in enumerate(steps, 1):
            effort = item.get("effort_minutes", item.get("effort", 0))
            reduction = item.get("blast_radius_reduction", item.get("risk_reduction", 0.0))

            # Format reduction safely
            if isinstance(reduction, (int, float)):
                red_str = f"-{reduction:.0f}%"
            else:
                red_str = str(reduction)

            table.add_row(
                str(i),
                str(item.get("title", "Unknown"))[:35],
                str(item.get("fix_command") or "N/A")[:48],
                f"{effort} min",
                red_str,
            )

        self.console.print(table)

        total_time = plan.get("total_effort_minutes", plan.get("total_time", 0))
        total_reduction = plan.get(
            "cumulative_reduction", plan.get("total_blast_radius_reduction", 0.0)
        )

        # Convert 0-1 float to percentage if necessary
        if isinstance(total_reduction, float) and total_reduction <= 1.0:
            total_reduction = total_reduction * 100

        addressed = plan.get("findings_addressed", len(steps))

        self.console.print(
            f"\n[bold green]Total: {addressed} findings fixed, "
            f"{total_reduction:.0f}% blast radius reduction, {total_time} min[/bold green]"
        )
        self.console.print("[dim]Math: multiplicative — total = 1 - product(1 - r_i)[/dim]")
