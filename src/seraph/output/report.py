import logging

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from seraph.sources.repository.scanners.base import Finding


logger = logging.getLogger(__name__)


class ReportGenerator:
    """Generates executive reports from scan findings."""

    def __init__(self, findings: list[Finding], scan_metadata: dict[str, Any] | None = None):
        self.findings = findings
        self.metadata = scan_metadata or {}
        self.timestamp = datetime.now(UTC).isoformat()

    def generate_html(self, output_path: Path) -> None:
        """Generate an HTML dashboard report."""
        summary = self._build_summary()
        html = self._render_html(summary)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(html, encoding="utf-8")
        logger.info(f"HTML report written to {output_path}")

    def generate_markdown(self, output_path: Path) -> None:
        """Generate a Markdown report."""
        summary = self._build_summary()
        md = self._render_markdown(summary)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(md, encoding="utf-8")
        logger.info(f"Markdown report written to {output_path}")

    def generate_executive_summary(self, output_path: Path) -> None:
        """Generate a brief executive summary (non-technical)."""
        summary = self._build_summary()
        text = self._render_executive_summary(summary)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(text, encoding="utf-8")
        logger.info(f"Executive summary written to {output_path}")

    def _build_summary(self) -> dict[str, Any]:
        """Build summary statistics from findings."""
        severity_counts: dict[str, int] = {}
        category_counts: dict[str, int] = {}
        scanner_counts: dict[str, int] = {}
        fixable = 0
        top_findings = []

        for f in self.findings:
            sev = f.severity.value
            cat = f.category.value
            scanner = f.scanner

            severity_counts[sev] = severity_counts.get(sev, 0) + 1
            category_counts[cat] = category_counts.get(cat, 0) + 1
            scanner_counts[scanner] = scanner_counts.get(scanner, 0) + 1

            if f.fix_available:
                fixable += 1

        sorted_findings = sorted(self.findings, key=lambda f: f.severity.weight, reverse=True)
        for f in sorted_findings[:10]:
            top_findings.append(
                {
                    "id": f.id,
                    "title": f.title,
                    "severity": f.severity.value,
                    "file": f.file,
                    "fix_available": f.fix_available,
                }
            )

        risk_score = self._calculate_risk_score(severity_counts)

        return {
            "total_findings": len(self.findings),
            "by_severity": severity_counts,
            "by_category": category_counts,
            "by_scanner": scanner_counts,
            "fixable": fixable,
            "risk_score": risk_score,
            "top_findings": top_findings,
            "risk_level": self._risk_level(risk_score),
        }

    def _calculate_risk_score(self, severity_counts: dict[str, int]) -> int:
        """Calculate an overall risk score from 0 to 100."""
        weights = {"critical": 40, "high": 25, "medium": 10, "low": 3, "info": 1}
        score = 0
        for sev, count in severity_counts.items():
            score += weights.get(sev, 0) * count
        return min(score, 100)

    def _risk_level(self, score: int) -> str:
        """Convert risk score to a human-readable level."""
        if score >= 80:
            return "CRITICAL"
        if score >= 60:
            return "HIGH"
        if score >= 40:
            return "MEDIUM"
        if score >= 20:
            return "LOW"
        return "MINIMAL"

    def _render_html(self, summary: dict[str, Any]) -> str:
        """Render findings as an HTML dashboard."""
        scan_path = self.metadata.get("scan_path", "unknown")
        duration = self.metadata.get("duration_ms", 0)

        severity_rows = ""
        severity_order = ["critical", "high", "medium", "low", "info"]
        colors = {
            "critical": "#dc3545",
            "high": "#fd7e14",
            "medium": "#ffc107",
            "low": "#17a2b8",
            "info": "#6c757d",
        }

        for sev in severity_order:
            count = summary["by_severity"].get(sev, 0)
            color = colors.get(sev, "#6c757d")
            severity_rows += f"<tr><td><span style='color:{color};font-weight:bold;'>● {sev.upper()}</span></td><td style='text-align:right;'>{count}</td></tr>"

        top_findings_rows = ""
        for f in summary["top_findings"]:
            fix_badge = "✅" if f["fix_available"] else "❌"
            sev_color = colors.get(f["severity"], "#6c757d")
            top_findings_rows += f"<tr><td>{f['id']}</td><td><span style='color:{sev_color};'>{f['severity'].upper()}</span></td><td>{f['title'][:60]}</td><td><code>{f['file'][:40]}</code></td><td>{fix_badge}</td></tr>"

        risk_color = (
            "#dc3545"
            if summary["risk_score"] >= 60
            else "#ffc107"
            if summary["risk_score"] >= 30
            else "#17a2b8"
        )
        val_class = (
            "critical"
            if summary["risk_score"] >= 60
            else "medium"
            if summary["risk_score"] >= 30
            else "low"
        )

        return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><title>Seraph Guard Security Report</title>
<style>
body {{ font-family: sans-serif; background: #f5f5f5; padding: 20px; }}
.container {{ max-width: 1200px; margin: 0 auto; }}
header {{ background: #1a1a2e; color: white; padding: 30px; border-radius: 12px; margin-bottom: 20px; }}
.card {{ background: white; padding: 24px; border-radius: 12px; box-shadow: 0 2px 8px rgba(0,0,0,0.08); margin-bottom: 20px; }}
table {{ width: 100%; border-collapse: collapse; }}
th, td {{ padding: 12px; text-align: left; border-bottom: 1px solid #eee; }}
.risk-bar {{ width: 200px; height: 12px; background: #eee; border-radius: 6px; overflow: hidden; }}
.risk-fill {{ height: 100%; border-radius: 6px; }}
</style></head><body><div class="container">
<header><h1>🛡️ Seraph Guard Security Report</h1><p>Generated: {self.timestamp} | Path: {scan_path} | Duration: {duration}ms</p></header>
<div class="card"><h3>Risk Score</h3><span class="{val_class}" style="font-size:36px;font-weight:bold;">{summary["risk_score"]}</span> / 100
<div class="risk-bar"><div class="risk-fill" style="width:{summary["risk_score"]}%;background:{risk_color}"></div></div>
<p>Risk Level: <strong>{summary["risk_level"]}</strong></p></div>
<div class="card"><h2>Severity Distribution</h2><table><thead><tr><th>Severity</th><th>Count</th></tr></thead><tbody>{severity_rows}</tbody></table></div>
<div class="card"><h2>Top Findings</h2><table><thead><tr><th>ID</th><th>Severity</th><th>Title</th><th>File</th><th>Fix</th></tr></thead><tbody>{top_findings_rows}</tbody></table></div>
</div></body></html>"""

    def _render_markdown(self, summary: dict[str, Any]) -> str:
        """Render findings as a Markdown report."""
        lines = [
            "# 🛡️ Seraph Guard Security Report\n",
            f"**Generated:** {self.timestamp}",
            f"**Scan path:** {self.metadata.get('scan_path', 'unknown')}",
            f"**Duration:** {self.metadata.get('duration_ms', 0)}ms\n",
            "---\n",
            "## Summary\n",
            "| Metric | Value |",
            "|--------|-------|",
            f"| **Risk Score** | **{summary['risk_score']}/100 ({summary['risk_level']})** |",
            f"| Total Findings | {summary['total_findings']} |",
            f"| Auto-Fixable | {summary['fixable']} |",
            f"| Critical | {summary['by_severity'].get('critical', 0)} |",
            f"| High | {summary['by_severity'].get('high', 0)} |\n",
            "## Top Findings\n",
            "| ID | Severity | Title | File | Fix |",
            "|----|----------|-------|------|-----|",
        ]
        for f in summary["top_findings"]:
            fix = "✅" if f["fix_available"] else "❌"
            lines.append(
                f"| {f['id']} | {f['severity'].upper()} | {f['title'][:50]} | `{f['file'][:30]}` | {fix} |"
            )
        lines.append("\n---\n*Generated by Seraph Guard v0.1.0*")
        return "\n".join(lines)

    def _render_executive_summary(self, summary: dict[str, Any]) -> str:
        """Render a brief, non-technical executive summary."""
        risk_level = summary["risk_level"]
        total = summary["total_findings"]
        critical = summary["by_severity"].get("critical", 0)
        high = summary["by_severity"].get("high", 0)
        fixable = summary["fixable"]

        if risk_level == "CRITICAL":
            rec = "IMMEDIATE ACTION REQUIRED. The codebase contains critical security vulnerabilities."
        elif risk_level == "HIGH":
            rec = "HIGH PRIORITY. Multiple high-severity findings require urgent attention."
        elif risk_level == "MEDIUM":
            rec = "MODERATE RISK. Findings should be addressed in the next development cycle."
        else:
            rec = "LOW RISK. Codebase is in good security health."

        lines = [
            "EXECUTIVE SECURITY SUMMARY",
            "=" * 40,
            f"Date: {self.timestamp.split('T')[0]}",
            f"Overall Risk Level: {risk_level}",
            f"Risk Score: {summary['risk_score']}/100\n",
            "KEY METRICS",
            f"  Total security findings: {total}",
            f"  Critical/High issues: {critical + high}",
            f"  Auto-fixable issues: {fixable}\n",
            "RECOMMENDATION",
            f"  {rec}\n",
            "Generated by Seraph Guard v0.1.0",
        ]
        return "\n".join(lines)
