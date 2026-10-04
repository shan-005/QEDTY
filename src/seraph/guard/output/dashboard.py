from typing import Any

from .panels import (
    blast_radius_panel,
    build_result_panel,
    explanation_panel,
    findings_panel,
    fix_plan_panel,
    footer_panel,
    header_panel,
    severity_panel,
)
from .styles import RESET


def _merge_side_by_side(left: list[str], right: list[str]) -> list[str]:
    """Merge two panels horizontally, padding the shorter one."""
    max_h = max(len(left), len(right))
    out = []
    for i in range(max_h):
        left_line = left[i] if i < len(left) else " " * len(left[0]) if left else ""
        right_line = right[i] if i < len(right) else " " * len(right[0]) if right else ""
        out.append(f"  {left_line}  {right_line}")
    return out


def render_dashboard(scan_result: dict[str, Any]) -> None:
    """Main entry point. Takes the full scan result and prints the dashboard."""
    findings: list[dict[str, Any]] = scan_result.get("findings", [])
    metadata: dict[str, Any] = scan_result.get("metadata", {})
    result_summary: dict[str, Any] = scan_result.get("result", {})

    # Rank by blast_radius * cp_confidence descending
    ranked = sorted(
        findings,
        key=lambda f: f.get("blast_radius", 0.0) * f.get("cp_confidence", 0.0),
        reverse=True,
    )
    top_finding = ranked[0] if ranked else {}

    output_lines: list[str] = []

    # 1. Header
    output_lines.extend(header_panel(metadata))
    output_lines.append("")

    # 2. Two-column: severity (left) + findings (right)
    sev_lines = severity_panel(ranked, result_summary.get("suppressed_count", 0))
    find_lines = findings_panel(ranked)
    output_lines.extend(_merge_side_by_side(sev_lines, find_lines))
    output_lines.append("")

    # 3. Blast radius (full width)
    output_lines.extend(blast_radius_panel(ranked, max_show=2))
    output_lines.append("")

    # 4. XAI Explanation (full width, top finding)
    if top_finding:
        output_lines.extend(explanation_panel(top_finding))
        output_lines.append("")

    # 5. Fix plan (full width)
    output_lines.extend(fix_plan_panel(ranked, max_show=5))
    output_lines.append("")

    # 6. Build result
    output_lines.extend(build_result_panel(result_summary))
    output_lines.append("")

    # 7. Footer shortcuts
    output_lines.extend(footer_panel())

    # Print
    for line in output_lines:
        print(line + RESET)
