import re

from typing import Any

from .styles import (
    BAR_EMPTY,
    BAR_FULL,
    BOLD,
    CHECK,
    CP_BAND,
    CRITICAL,
    CYAN,
    DIM,
    GREEN,
    HIGH,
    H_BL,
    H_BR,
    H_H,
    H_L,
    H_R,
    H_TL,
    H_TR,
    H_V,
    INFO,
    LEFT_PANEL_W,
    L_BL,
    L_BR,
    L_H,
    L_L,
    L_R,
    L_TL,
    L_TR,
    L_V,
    MAGENTA,
    MEDIUM,
    PANEL_WIDTH,
    RESET,
    RIGHT_PANEL_W,
    SEV_COLOR,
    WARN,
)


def _bar(pct: float, width: int = 20, color: str = CRITICAL) -> str:
    """Render an inline percentage bar."""
    filled = min(int(pct / (100 / width)), width)
    return f"{color}{BAR_FULL * filled}{RESET}{BAR_EMPTY * (width - filled)}"


def _center(text: str, width: int) -> str:
    """Center text within a width, accounting for ANSI codes."""
    plain_text = re.sub(r"\x1b\[[0-9;]*m", "", text)
    pad = max(0, width - len(plain_text))
    left_pad = pad // 2
    right_pad = pad - left_pad
    return " " * left_pad + text + " " * right_pad


def _pad_line(content: str, total_width: int) -> str:
    """Pad a content string to exact total_width (accounting for ANSI)."""
    plain = re.sub(r"\033\[[0-9;]*m", "", content)
    padding = max(0, total_width - len(plain) - 2)  # -2 for borders
    return f"{L_V} {content}{' ' * padding} {L_V}"


# ═════════════════════════════════════════════════════════════
# HEADER
# ═════════════════════════════════════════════════════════════
def header_panel(metadata: dict[str, Any]) -> list[str]:
    lines = []
    w = PANEL_WIDTH
    lines.append(f"{H_TL}{H_H * w}{H_TR}")
    lines.append(
        f"{H_V}  {BOLD}🛡️  SERAPH GUARD  v{metadata.get('version', '1.0.0'):<10}"
        f"{'Intelligence Layer':>{w - 35}}  {H_V}"
    )
    lines.append(f"{H_L}{H_H * w}{H_R}")

    target = metadata.get("target", ".")
    files = metadata.get("files", 0)
    prod = metadata.get("production", 0)
    test = metadata.get("test", 0)
    duration = metadata.get("duration", "0s")
    mode = metadata.get("mode", "")

    lines.append(
        f"{H_V}  {DIM}Target:{RESET}  {BOLD}{target:<30}{RESET}  "
        f"{DIM}Files:{RESET} {files:<6}  {DIM}Production:{RESET} {prod:<6}  "
        f"{DIM}Test:{RESET} {test:<6}  {H_V}"
    )
    lines.append(
        f"{H_V}  {DIM}Scanners:{RESET} {GREEN}Secret✓{RESET}  {GREEN}SBOM✓{RESET}  "
        f"{GREEN}Policy✓{RESET}  {GREEN}Pattern✓{RESET}     "
        f"{DIM}Duration:{RESET} {duration:<6}  {DIM}Mode:{RESET} {CYAN}{mode:<24}{RESET}  {H_V}"
    )
    lines.append(f"{H_BL}{H_H * w}{H_BR}")
    return lines


# ═════════════════════════════════════════════════════════════
# PROGRESS
# ═════════════════════════════════════════════════════════════
def progress_panel(phases: dict[str, str] | None = None) -> list[str]:
    if phases is None:
        phases = {
            "Discovery": "100%",
            "Intelligence": "100%",
            "Output": "100%",
            "Evaluation": "100%",
        }
    lines = []
    labels = "  ".join(f"{name:<16}" for name in phases)
    bars = "  ".join(f"{GREEN}{BAR_FULL * 20}{RESET}" for _ in phases)
    pcts = "  ".join(f"{pct:<16}" for pct in phases.values())
    lines.append(f"  {DIM}{labels}{RESET}")
    lines.append(f"  {bars}")
    lines.append(f"  {DIM}{pcts}{RESET}")
    return lines


# ═════════════════════════════════════════════════════════════
# SEVERITY DISTRIBUTION (left column)
# ═════════════════════════════════════════════════════════════
def severity_panel(findings: list[dict[str, Any]], suppressed: int) -> list[str]:
    counts: dict[str, int] = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0, "INFO": 0}
    for f in findings:
        sev = f.get("severity", "INFO").upper()
        counts[sev] = counts.get(sev, 0) + 1
    total = sum(counts.values())

    lines = []
    w = LEFT_PANEL_W
    lines.append(f"{L_TL}{L_H * w}{L_TR}")
    lines.append(f"{L_V} {BOLD}SEVERITY DISTRIBUTION{RESET}{' ' * (w - 22)} {L_V}")
    lines.append(f"{L_L}{L_H * w}{L_R}")

    for sev in ("CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"):
        color = SEV_COLOR.get(sev, INFO)
        cnt = counts[sev]
        pct = (cnt / total * 100) if total else 0
        bar = _bar(pct, 20, color)
        line = f"  {color}{sev:<9}{RESET}  {bar}  {cnt:>3}  {DIM}({pct:>4.0f}%){RESET}"
        lines.append(_pad_line(line, w))

    lines.append(_pad_line("", w))
    lines.append(
        _pad_line(
            f"{DIM}Suppressed:{RESET} {GREEN}{suppressed}{RESET} {DIM}(test/framework/dev){RESET}",
            w,
        )
    )
    raw_total = total + suppressed
    lines.append(
        _pad_line(
            f"{DIM}Raw total:{RESET} {MEDIUM}{raw_total}{RESET}  {DIM}→ Production:{RESET} {GREEN}{total}{RESET}",
            w,
        )
    )
    lines.append(f"{L_BL}{L_H * w}{L_BR}")
    return lines


# ═════════════════════════════════════════════════════════════
# TOP RANKED FINDINGS (right column)
# ═════════════════════════════════════════════════════════════
def findings_panel(findings: list[dict[str, Any]]) -> list[str]:
    lines = []
    w = RIGHT_PANEL_W
    lines.append(f"{L_TL}{L_H * w}{L_TR}")
    lines.append(
        f"{L_V} {BOLD}TOP RANKED FINDINGS{RESET}  "
        f"{DIM}(by blast-radius x confidence){RESET}{' ' * 7} {L_V}"
    )
    lines.append(f"{L_L}{L_H * w}{L_R}")
    lines.append(_pad_line(f"{DIM}#  ID     SEVERITY  BLAST    CP(95%)   FILE{RESET}", w))

    for i, f in enumerate(findings[:5], 1):
        sev = f.get("severity", "INFO").upper()
        color = SEV_COLOR.get(sev, INFO)
        blast = f.get("blast_radius", 0.0)
        cp_low = f.get("cp_low", 0.0)
        cp_high = f.get("cp_high", 0.0)
        file_path = f.get("file", "unknown")[:25]
        fid = f.get("id", f"F{i:03d}")

        row = (
            f"{color}{i:<3}{fid:<7}{sev:<9}{blast:>6.1f}%{RESET}  "
            f"{CP_BAND}[{cp_low:.2f},{cp_high:.2f}]{RESET}  {DIM}{file_path}{RESET}"
        )
        lines.append(_pad_line(row, w))

    lines.append(_pad_line("", w))
    more = max(0, len(findings) - 5)
    lines.append(_pad_line(f"{DIM}... {more} more findings ranked by ROI per hour{RESET}", w))
    lines.append(_pad_line("", w))
    lines.append(_pad_line(f"{DIM}Sort: [r]ank  [s]everity  [f]ile  [t]ype{RESET}", w))
    lines.append(f"{L_BL}{L_H * w}{L_BR}")
    return lines


# ═════════════════════════════════════════════════════════════
# BLAST RADIUS (full width)
# ═════════════════════════════════════════════════════════════
def blast_radius_panel(findings: list[dict[str, Any]], max_show: int = 2) -> list[str]:
    lines = []
    w = PANEL_WIDTH
    lines.append(f"{L_TL}{L_H * w}{L_TR}")
    lines.append(
        f"{L_V} {BOLD}BLAST RADIUS ANALYSIS{RESET}  "
        f"{DIM}- Multiplicative impact propagation: 1 - prod(1 - r_i){RESET}{' ' * 35} {L_V}"
    )
    lines.append(f"{L_L}{L_H * w}{L_R}")

    for f in findings[:max_show]:
        sev = f.get("severity", "INFO").upper()
        color = SEV_COLOR.get(sev, INFO)
        fid = f.get("id", "UNK")
        title = f.get("title", "No title")[:60]

        lines.append(_pad_line("", w))
        lines.append(_pad_line(f"{color}{fid}{RESET}  {DIM}{title}{RESET}", w))

        for level, label in (
            ("direct", "Direct"),
            ("indirect", "Indirect"),
            ("cascade", "Cascade"),
        ):
            val = f.get(f"blast_{level}", 0.0)
            desc = f.get(f"blast_{level}_desc", "")
            bar = _bar(val, 20, CRITICAL if val > 50 else HIGH if val > 30 else MEDIUM)
            row = f"├── {label:<9} {bar}  {val:>5.0f}%  {DIM}{desc}{RESET}"
            lines.append(_pad_line(row, w))

        total = f.get("blast_radius", 0.0)
        cp_lo = f.get("cp_low", 0.0)
        cp_hi = f.get("cp_high", 0.0)
        total_line = (
            f"└── {BOLD}TOTAL BLAST RADIUS:  {CRITICAL}{total:.1f}%{RESET}  "
            f"{DIM}[CP 95%: {cp_lo:.1f}% — {cp_hi:.1f}%]{RESET}"
        )
        lines.append(_pad_line(total_line, w))
        lines.append(_pad_line("", w))

    lines.append(f"{L_BL}{L_H * w}{L_BR}")
    return lines


# ═════════════════════════════════════════════════════════════
# XAI EXPLANATION (full width)
# ═════════════════════════════════════════════════════════════
def explanation_panel(finding: dict[str, Any]) -> list[str]:
    lines = []
    w = PANEL_WIDTH
    fid = finding.get("id", "UNK")
    template = finding.get("template", "unknown")

    lines.append(f"{L_TL}{L_H * w}{L_TR}")
    lines.append(
        f"{L_V} {BOLD}XAI EXPLANATION{RESET}  {DIM}— Finding {fid}  |  "
        f"Template: {template}  |  Deterministic{RESET}  {L_V}"
    )
    lines.append(f"{L_L}{L_H * w}{L_R}")
    lines.append(_pad_line("", w))

    # WHAT
    what = finding.get("what", "No description available.")
    lines.append(_pad_line(f"{MAGENTA}WHAT:{RESET}  {what}", w))
    lines.append(_pad_line("", w))

    # WHY
    why = finding.get("why", "")
    if why:
        lines.append(_pad_line(f"{MAGENTA}WHY IT MATTERS:{RESET}  {why}", w))
        lines.append(_pad_line("", w))

    # BLAST
    blast = finding.get("blast_radius", 0.0)
    lines.append(
        _pad_line(
            f"{MAGENTA}BLAST RADIUS:{RESET}  {CRITICAL}{blast:.1f}%{RESET} of total attack surface. "
            f"{BOLD}This is the #1 priority fix.{RESET}",
            w,
        )
    )
    lines.append(_pad_line("", w))

    # CONFIDENCE
    cp = finding.get("cp_confidence", 0.0)
    cp_set = finding.get("cp_set", "{}")
    cp_lo = finding.get("cp_low", 0.0)
    cp_hi = finding.get("cp_high", 0.0)
    lines.append(
        _pad_line(
            f"{MAGENTA}CONFIDENCE:{RESET}  {CP_BAND}{cp:.1f}%{RESET} conformal prediction coverage. "
            f"True severity in {cp_set}.",
            w,
        )
    )
    lines.append(
        _pad_line(
            f"         {DIM}[CP 95% interval: {cp_lo:.1f}% — {cp_hi:.1f}% blast radius]{RESET}", w
        )
    )
    lines.append(_pad_line("", w))

    # FIX
    fix_steps = finding.get("fix_steps", [finding.get("fix", "No fix available.")])
    if isinstance(fix_steps, str):
        fix_steps = [fix_steps]
    lines.append(_pad_line(f"{GREEN}FIX:{RESET}  {fix_steps[0]}", w))
    for step in fix_steps[1:]:
        lines.append(_pad_line(f"       {step}", w))
    lines.append(_pad_line("", w))

    # Footer
    effort = finding.get("fix_effort_min", 0)
    roi = finding.get("roi_per_hour", 0.0)
    lines.append(
        _pad_line(
            f"{DIM}Estimated fix time: {effort} minutes  |  "
            f"Risk reduction: {blast:.1f}%  |  ROI: {roi:.1f}% per hour{RESET}",
            w,
        )
    )
    lines.append(f"{L_BL}{L_H * w}{L_BR}")
    return lines


# ═════════════════════════════════════════════════════════════
# OPTIMAL FIX PLAN (full width)
# ═════════════════════════════════════════════════════════════
def fix_plan_panel(findings: list[dict[str, Any]], max_show: int = 5) -> list[str]:
    lines = []
    w = PANEL_WIDTH
    lines.append(f"{L_TL}{L_H * w}{L_TR}")
    lines.append(
        f"{L_V} {BOLD}OPTIMAL FIX PLAN{RESET}  {DIM}— Ranked by blast-radius-reduction per unit effort "
        f"(ROI per hour){RESET}  {L_V}"
    )
    lines.append(f"{L_L}{L_H * w}{L_R}")
    lines.append(_pad_line("", w))

    header = f"{DIM}RANK  FINDING   EFFORT    RISK REDUCTION   ROI/HR   ACTION{RESET}"
    lines.append(_pad_line(header, w))
    lines.append(
        _pad_line(
            f"{DIM}────  ────────  ────────  ──────────────  ───────  ──────────────────────────────────{RESET}",
            w,
        )
    )

    total_risk = 0.0
    total_effort = 0
    shown = findings[:max_show]

    for i, f in enumerate(shown, 1):
        effort = f.get("fix_effort_min", 0)
        risk = f.get("blast_radius", 0.0)
        roi = f.get("roi_per_hour", 0.0)
        action = f.get("fix_action", "Fix manually")[:40]
        sev = f.get("severity", "INFO").upper()
        color = SEV_COLOR.get(sev, INFO)
        fid = f.get("id", f"F{i:03d}")

        row = (
            f" #{i:<4}{fid:<9}{effort:>5} min       {color}{risk:>6.1f}%{RESET}       "
            f"{GREEN}{roi:>7.1f}%{RESET}   {action}"
        )
        lines.append(_pad_line(row, w))
        total_risk += risk
        total_effort += effort

    lines.append(_pad_line("", w))
    cumulative_roi = sum(f.get("roi_per_hour", 0.0) for f in shown)
    lines.append(
        _pad_line(
            f"{DIM}Total effort: {total_effort} minutes  |  "
            f"Total risk reduction: {min(total_risk, 100):.1f}%  |  "
            f"Cumulative ROI: {cumulative_roi:.1f}%/hr{RESET}",
            w,
        )
    )
    lines.append(f"{L_BL}{L_H * w}{L_BR}")
    return lines


# ═════════════════════════════════════════════════════════════
# BUILD RESULT (heavy border banner)
# ═════════════════════════════════════════════════════════════
def build_result_panel(result: dict[str, Any]) -> list[str]:
    lines = []
    w = PANEL_WIDTH
    lines.append(f"{H_TL}{H_H * w}{H_TR}")
    lines.append(f"{H_V}{' ' * w} {H_V}")

    passed = result.get("passed", False)
    crit = result.get("critical_count", 0)
    high = result.get("high_count", 0)

    if passed:
        msg = f"{GREEN}BUILD PASSED{RESET}  {DIM}— No critical or high severity findings in production code{RESET}"
    else:
        msg = f"{CRITICAL}BUILD FAILED{RESET}  {DIM}— {crit} critical + {high} high severity findings in production code{RESET}"

    # Calculate padding dynamically to avoid length mismatches with ANSI codes
    plain_msg = msg.replace("\033[", "").replace("m", "")
    padding = max(0, w - len(plain_msg) - 4)

    lines.append(f"{H_V}    {msg}{' ' * padding} {H_V}")
    lines.append(f"{H_V}{' ' * w} {H_V}")

    lines.append(
        f"{H_V}    {CHECK}  {result.get('suppressed_count', 0)} test/framework/dev findings suppressed (context-aware){' ' * 25} {H_V}"
    )
    lines.append(
        f"{H_V}    {CHECK}  {result.get('duplicate_count', 0)} duplicate findings (deduplication active){' ' * 35} {H_V}"
    )
    lines.append(
        f"{H_V}    {CHECK}  Conformal prediction applied (95% coverage guarantee){' ' * 28} {H_V}"
    )
    lines.append(
        f"{H_V}    {CHECK}  Blast radius calculated for all {result.get('production_findings', 0)} production findings{' ' * 20} {H_V}"
    )

    if result.get("threshold_exceeded"):
        tc = result.get("threshold_count", 0)
        lines.append(
            f"{H_V}    {WARN}  {tc} findings exceed blast-radius threshold (>=90%) — immediate action required{' ' * 5} {H_V}"
        )

    lines.append(f"{H_V}{' ' * w} {H_V}")

    exit_code = result.get("exit_code", 1)
    out_path = result.get("output_path", "N/A")
    top_fid = result.get("top_finding", "N/A")
    lines.append(
        f"{H_V}    {DIM}Exit code: {exit_code}  |  Format: table  |  Output: {out_path}{RESET}{' ' * 25} {H_V}"
    )
    lines.append(f"{H_V}    {DIM}Next: seraph guard fix --finding {top_fid}{RESET}{' ' * 35} {H_V}")
    lines.append(f"{H_V}{' ' * w} {H_V}")
    lines.append(f"{H_BL}{H_H * w}{H_BR}")
    return lines


# ═════════════════════════════════════════════════════════════
# FOOTER
# ═════════════════════════════════════════════════════════════
def footer_panel() -> list[str]:
    return [
        (
            f"  {DIM}[q]uit  [e]xplain next  [f]ix finding  "
            f"[j]son export  [s]arif export  [r]e-run scan  [?]help{RESET}"
        )
    ]
