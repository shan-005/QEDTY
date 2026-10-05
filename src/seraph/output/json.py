"""JSON Output Formatter — Stream-writes findings to prevent OOM on massive repos."""

from __future__ import annotations

import json

from collections.abc import Iterable
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any


if TYPE_CHECKING:
    from pathlib import Path

from seraph import __version__
from seraph.sources.repository.scanners.base import Finding


class JsonOutput:
    """Renders findings as structured JSON for APIs, pipelines, and dashboards."""

    def render(
        self, findings: list[Finding], metadata: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Build the complete JSON-serializable scan result."""
        return {
            "version": __version__,
            "tool": "seraph-guard",
            "generated_at": datetime.now(UTC).isoformat(),
            "metadata": metadata or {},
            "summary": self._build_summary(findings),
            "findings": [f.to_dict() for f in findings],
        }

    def to_json(
        self,
        findings: list[Finding],
        metadata: dict[str, Any] | None = None,
        indent: int = 2,
    ) -> str:
        """Return the complete scan result as a JSON string."""
        return json.dumps(
            self.render(findings, metadata),
            indent=indent,
            ensure_ascii=False,
        )

    def write(
        self,
        findings: Iterable[Finding],
        output_path: Path,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Stream-write JSON to a file to prevent OOM on massive finding lists."""
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "w", encoding="utf-8") as f:
            f.write("{\n")
            f.write(f'  "version": {json.dumps(__version__)},\n')
            f.write('  "tool": "seraph-guard",\n')
            f.write(f'  "generated_at": {json.dumps(datetime.now(UTC).isoformat())},\n')
            f.write('  "metadata": ')
            json.dump(metadata or {}, f, ensure_ascii=False)
            f.write(',\n  "summary": ')

            # Buffer to a list if it is an iterator so that the summary
            # can be calculated before streaming the findings.
            findings_list = list(findings) if not isinstance(findings, list) else findings
            json.dump(
                self._build_summary(findings_list),
                f,
                ensure_ascii=False,
            )

            f.write(',\n  "findings": [\n')
            first = True

            for finding in findings_list:
                if not first:
                    f.write(",\n")
                first = False

                # Safely extract a dictionary representation.
                if hasattr(finding, "to_dict"):
                    json.dump(
                        finding.to_dict(),
                        f,
                        ensure_ascii=False,
                    )
                else:
                    json.dump(
                        finding,
                        f,
                        ensure_ascii=False,
                        default=str,
                    )

            f.write("\n  ]\n}\n")

    def _build_summary(self, findings: list[Finding]) -> dict[str, Any]:
        """Build aggregate counts for the supplied findings."""
        severity_counts: dict[str, int] = {}
        category_counts: dict[str, int] = {}
        scanner_counts: dict[str, int] = {}
        fix_available_count = 0
        suppressed_count = 0

        for finding in findings:
            severity = (
                finding.severity.value
                if hasattr(finding.severity, "value")
                else str(finding.severity)
            )
            category = (
                finding.category.value
                if hasattr(finding.category, "value")
                else str(finding.category)
            )
            scanner = getattr(finding, "scanner", "unknown")

            severity_counts[severity] = severity_counts.get(severity, 0) + 1
            category_counts[category] = category_counts.get(category, 0) + 1
            scanner_counts[scanner] = scanner_counts.get(scanner, 0) + 1

            if getattr(finding, "fix_available", False):
                fix_available_count += 1

            if getattr(finding, "is_suppressed", False):
                suppressed_count += 1

        return {
            "total_findings": len(findings),
            "by_severity": severity_counts,
            "by_category": category_counts,
            "by_scanner": scanner_counts,
            "fix_available_count": fix_available_count,
            "suppressed_count": suppressed_count,
            "active_findings": len(findings) - suppressed_count,
        }
