from typing import Any


class TableFormatter:
    """Produce a compact text table of findings."""

    SEV_COLOR = {
        "CRITICAL": "\x1b[91m",
        "HIGH": "\x1b[93m",
        "MEDIUM": "\x1b[33m",
        "LOW": "\x1b[94m",
        "INFO": "\x1b[90m",
    }
    RESET = "\x1b[0m"

    def format(self, scan_result: dict[str, Any]) -> str:
        findings: list[dict[str, Any]] = scan_result.get("findings", [])
        lines = []
        lines.append("-" * 90)
        lines.append(f"{'ID':<12} {'SEVERITY':<10} {'BLAST':>8} {'FILE':<50}")
        lines.append("-" * 90)
        for f in findings:
            sev = f.get("severity", "INFO").upper()
            color = self.SEV_COLOR.get(sev, "")
            fid = f.get("id", "UNK")
            blast = f"{f.get('blast_radius', 0):.1f}%"
            file_path = f.get("file", "unknown")[:48]
            lines.append(f"{color}{fid:<12}{sev:<10}{blast:>8}{self.RESET}  {file_path}")
        lines.append("-" * 90)
        return "\n".join(lines)

    def write(self, scan_result: dict[str, Any], path: str) -> None:
        with open(path, "w", encoding="utf-8") as f:
            f.write(self.format(scan_result))
