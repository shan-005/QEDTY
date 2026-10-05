from seraph.sources.repository.scanners.base import Finding, Severity


GITHUB_LEVEL_MAP = {
    Severity.CRITICAL: "error",
    Severity.HIGH: "error",
    Severity.MEDIUM: "warning",
    Severity.LOW: "notice",
    Severity.INFO: "notice",
}


class GitHubAnnotationsOutput:
    """Renders findings as GitHub Actions workflow annotations."""

    def render(self, findings: list[Finding]) -> str:
        """Generate GitHub Actions annotation commands as a string."""
        lines = []
        for finding in findings:
            if finding.is_suppressed:
                continue
            level = GITHUB_LEVEL_MAP.get(finding.severity, "notice")
            message = self._escape(finding.description)
            title = self._escape(finding.title)
            file_path = finding.file.replace("\\", "/")
            annotation = f"::{level} file={file_path},line={max(finding.line, 1)},col={max(finding.column, 1)},title={title}::{message}"
            lines.append(annotation)
        return "\n".join(lines)

    def print_annotations(self, findings: list[Finding]) -> None:
        """Print annotations to stdout for GitHub Actions to capture."""
        output = self.render(findings)
        if output:
            print(output)

    def should_fail_build(self, findings: list[Finding], fail_on: str = "high") -> bool:
        """Determine if the build should fail based on finding severities."""
        try:
            fail_severity = Severity(fail_on)
        except ValueError:
            fail_severity = Severity.HIGH
        fail_weight = fail_severity.weight
        for finding in findings:
            if finding.is_suppressed:
                continue
            if finding.severity.weight >= fail_weight:
                return True
        return False

    def render_summary(self, findings: list[Finding]) -> str:
        """Generate a GitHub Actions job summary in Markdown."""
        if not findings:
            return "## ✅ Seraph Guard\n\nNo security findings detected.\n"

        lines = [
            "## 🛡️ Seraph Guard Security Scan\n",
            f"**Total findings:** {len(findings)}\n",
            "| Severity | Count |",
            "|----------|-------|",
        ]

        severity_order = [
            Severity.CRITICAL,
            Severity.HIGH,
            Severity.MEDIUM,
            Severity.LOW,
            Severity.INFO,
        ]
        counts: dict[str, int] = {}
        for f in findings:
            counts[f.severity.value] = counts.get(f.severity.value, 0) + 1

        for severity in severity_order:
            count = counts.get(severity.value, 0)
            if count > 0:
                lines.append(f"| {severity.value.upper()} | {count} |")

        lines.append("\n### Top Findings\n")
        for i, finding in enumerate(findings[:10], 1):
            fix_badge = "✅" if finding.fix_available else "❌"
            lines.append(
                f"{i}. **{finding.title}** (`{finding.location}`) — {finding.severity.value.upper()} {fix_badge}"
            )

        return "\n".join(lines)

    @staticmethod
    def _escape(value: str) -> str:
        """Escape characters that break GitHub annotation format."""
        return (
            value.replace("%", "%25")
            .replace("\r", "%0D")
            .replace("\n", "%0A")
            .replace(":", "%3A")
            .replace(",", "%2C")
        )
