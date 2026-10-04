# ── ANSI 256-Color Palette ──────────────────────────────────
CRITICAL = "\033[38;5;203m"  # bright red   #ff7b72
HIGH = "\033[38;5;208m"  # orange       #ffa657
MEDIUM = "\033[38;5;178m"  # yellow       #d29922
LOW = "\033[38;5;75m"  # blue         #58a6ff
INFO = "\033[38;5;245m"  # gray         #8b949e
GREEN = "\033[38;5;84m"  # green        #3fb950
CYAN = "\033[38;5;87m"  # cyan         #39d0d8
MAGENTA = "\033[38;5;183m"  # purple       #d2a8ff
CP_BAND = "\033[38;5;183m"  # conformal prediction
DIM = "\033[38;5;240m"  # dark gray    #6e7681
RESET = "\033[0m"
BOLD = "\033[1m"

# ── Severity → Color Map ────────────────────────────────────
SEV_COLOR = {
    "CRITICAL": CRITICAL,
    "HIGH": HIGH,
    "MEDIUM": MEDIUM,
    "LOW": LOW,
    "INFO": INFO,
}

# ── Border Characters ───────────────────────────────────────
# Heavy (header, footer, build result)
H_H = "═"
H_V = "║"
H_TL = "╔"
H_TR = "╗"
H_BL = "╚"
H_BR = "╝"
H_L = "╠"
H_R = "╣"

L_H = "─"
L_V = "│"
L_TL = "┌"
L_TR = "┐"
L_BL = "└"
L_BR = "┘"
L_T = "┬"
L_B = "┴"
L_L = "├"
L_R = "┤"

# ── Bar Glyphs ──────────────────────────────────────────────
BAR_FULL = "█"
BAR_EMPTY = "░"

# ── Check / Warning ─────────────────────────────────────────
CHECK = f"{GREEN}✓{RESET}"
WARN = f"{MEDIUM}⚠{RESET}"
CROSS = f"{CRITICAL}✗{RESET}"

# ── Width Constants ─────────────────────────────────────────
PANEL_WIDTH = 90
LEFT_PANEL_W = 40
RIGHT_PANEL_W = 57
