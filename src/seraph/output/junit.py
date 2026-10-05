"""seraph.output.junit — JUnit XML Output Formatter

Converts Seraph findings into JUnit-compatible XML for CI/CD ingestion
(Jenkins, GitLab CI, CircleCI, Azure DevOps, etc.).

Zero external dependencies — completely self-contained using standard library.
Note: defusedxml is only required for PARSING untrusted XML. For GENERATING XML,
the standard library xml.etree.ElementTree is secure and sufficient.
"""

from __future__ import annotations

import html
import xml.etree.ElementTree as ET  # nosec B405

from datetime import UTC, datetime
from pathlib import Path
from typing import Any


class JUnitFormatter:
    """Production-grade JUnit XML formatter for CI pipeline integration.

    Maps Seraph findings to JUnit <testcase> elements:
      - critical / high  → <failure>
      - medium           → <error>
      - low / info       → <skipped>
    """

    # Severity → JUnit status mapping
    SEVERITY_STATUS: dict[str, str] = {
        "critical": "failure",
        "high": "failure",
        "medium": "error",
        "low": "skipped",
        "info": "skipped",
    }

    def __init__(self, tool_name: str = "Seraph Guard") -> None:
        self.tool_name = tool_name

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def format(self, findings: list[dict[str, Any]], path: str) -> str:
        """Generate JUnit XML string from Seraph finding dicts."""
        testsuites = ET.Element("testsuites")
        testsuites.set("name", self.tool_name)
        testsuites.set("tests", str(len(findings)))
        testsuites.set("failures", str(self._count_by_status(findings, "failure")))
        testsuites.set("errors", str(self._count_by_status(findings, "error")))
        testsuites.set("skipped", str(self._count_by_status(findings, "skipped")))
        testsuites.set("time", "0")
        testsuites.set("timestamp", datetime.now(UTC).isoformat())

        # Group findings by scanner → test suite
        by_scanner: dict[str, list[dict[str, Any]]] = {}
        for f in findings:
            scanner = str(f.get("scanner", "unknown"))
            by_scanner.setdefault(scanner, []).append(f)

        for scanner, scanner_findings in by_scanner.items():
            suite = ET.SubElement(testsuites, "testsuite")
            suite.set("name", f"{self.tool_name} — {scanner}")
            suite.set("tests", str(len(scanner_findings)))
            suite.set("failures", str(self._count_by_status(scanner_findings, "failure")))
            suite.set("errors", str(self._count_by_status(scanner_findings, "error")))
            suite.set("skipped", str(self._count_by_status(scanner_findings, "skipped")))
            suite.set("file", path)

            for f in scanner_findings:
                self._add_testcase(suite, f)

        # Pretty-print (Python 3.9+)
        try:
            ET.indent(testsuites, space="  ")
        except AttributeError:
            pass  # Fallback for Python < 3.9

        return '<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(
            testsuites, encoding="unicode"
        )

    def write(self, findings: list[dict[str, Any]], path: str, output_file: str) -> None:
        """Write JUnit XML to disk."""
        xml_str = self.format(findings, path)
        out = Path(output_file)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(xml_str, encoding="utf-8")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _add_testcase(self, suite: ET.Element, finding: dict[str, Any]) -> None:
        sev = str(finding.get("severity", "info")).lower()
        status = self.SEVERITY_STATUS.get(sev, "skipped")

        case = ET.SubElement(suite, "testcase")
        case.set("name", str(finding.get("rule_id", finding.get("id", "unknown"))))
        case.set("classname", str(finding.get("category", "security")))
        case.set("file", str(finding.get("file", finding.get("path", ""))))
        line = finding.get("line", 0)
        case.set("line", str(line))
        case.set("time", "0")

        # Conformal confidence annotation
        cl = finding.get("conformal_lower")
        cu = finding.get("conformal_upper")
        blast = finding.get("blast_radius")
        blast_score = None
        if isinstance(blast, dict):
            blast_score = blast.get("blast_radius_score")

        props = ET.SubElement(case, "properties")
        if cl is not None and cu is not None:
            p = ET.SubElement(props, "property")
            p.set("name", "conformal_confidence")
            p.set("value", f"[{cl:.0%}, {cu:.0%}]")
        if blast_score is not None:
            p = ET.SubElement(props, "property")
            p.set("name", "blast_radius")
            p.set("value", f"{blast_score:.0f}%")

        msg = str(finding.get("message", finding.get("title", "No message")))
        detail = str(finding.get("description", ""))
        full_msg = f"{msg}\n{detail}".strip()
        safe_msg = html.escape(full_msg)

        if status == "failure":
            fail = ET.SubElement(case, "failure")
            fail.set("message", html.escape(msg))
            fail.set("type", str(finding.get("category", "security")))
            fail.text = safe_msg
        elif status == "error":
            err = ET.SubElement(case, "error")
            err.set("message", html.escape(msg))
            err.set("type", str(finding.get("category", "security")))
            err.text = safe_msg
        elif status == "skipped":
            skip = ET.SubElement(case, "skipped")
            skip.set("message", html.escape(msg))

    def _count_by_status(self, findings: list[dict[str, Any]], status: str) -> int:
        return sum(
            1
            for f in findings
            if self.SEVERITY_STATUS.get(str(f.get("severity", "")).lower(), "skipped") == status
        )
