import hashlib
import json

from datetime import UTC, datetime
from typing import Any


class SarifFormatter:
    """Convert Seraph findings to SARIF 2.1.0 format."""

    SEVERITY_MAP = {
        "CRITICAL": "error",
        "HIGH": "error",
        "MEDIUM": "warning",
        "LOW": "note",
        "INFO": "note",
    }

    def format(self, scan_result: dict[str, Any]) -> str:
        """Return SARIF JSON string."""
        findings: list[dict[str, Any]] = scan_result.get("findings", [])
        metadata: dict[str, Any] = scan_result.get("metadata", {})

        rules: list[dict[str, Any]] = []
        results: list[dict[str, Any]] = []
        rule_indices: dict[str, int] = {}

        for f in findings:
            rule_id = f.get("id", "SERAPH-000")
            if rule_id not in rule_indices:
                rule_indices[rule_id] = len(rules)
                rules.append(self._make_rule(f))

            results.append(self._make_result(f, rule_indices[rule_id]))

        now = datetime.now(UTC).isoformat().replace("+00:00", "Z")
        start_time = metadata.get("started", now)
        end_time = metadata.get("ended", now)

        sarif = {
            "$schema": "https://raw.githubusercontent.com/oasis-tcs/sarif-spec/master/Schemata/sarif-schema-2.1.0.json",
            "version": "2.1.0",
            "runs": [
                {
                    "tool": {
                        "driver": {
                            "name": "Seraph Guard",
                            "informationUri": "https://github.com/nirik/seraph-guard",
                            "version": metadata.get("version", "1.0.0"),
                            "rules": rules,
                        }
                    },
                    "results": results,
                    "invocations": [
                        {
                            "executionSuccessful": True,
                            "startTimeUtc": start_time,
                            "endTimeUtc": end_time,
                        }
                    ],
                    "properties": {
                        "seraph": {
                            "suppressed": scan_result.get("result", {}).get("suppressed_count", 0),
                            "duplicates": scan_result.get("result", {}).get("duplicate_count", 0),
                            "conformal_prediction_applied": True,
                            "blast_radius_calculated": True,
                        }
                    },
                }
            ],
        }
        return json.dumps(sarif, indent=2, ensure_ascii=False)

    def write(self, scan_result: dict[str, Any], path: str) -> None:
        with open(path, "w", encoding="utf-8") as f:
            f.write(self.format(scan_result))

    def _make_rule(self, finding: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": finding.get("id", "SERAPH-000"),
            "name": finding.get("title", "Unknown finding"),
            "shortDescription": {"text": finding.get("title", "")},
            "fullDescription": {"text": finding.get("what", "")},
            "help": {"text": finding.get("fix", "No fix available.")},
            "defaultConfiguration": {
                "level": self.SEVERITY_MAP.get(finding.get("severity", "INFO").upper(), "warning"),
            },
            "properties": {
                "tags": [
                    finding.get("severity", "INFO").lower(),
                    finding.get("scanner", "unknown"),
                ],
                "precision": "very-high",
                "security-severity": str(self._cvss_from_severity(finding.get("severity", "INFO"))),
            },
        }

    def _make_result(self, finding: dict[str, Any], rule_index: int) -> dict[str, Any]:
        file_path = finding.get("file", "")
        line = finding.get("line", 1)
        start_col = finding.get("column", 1)
        end_col = finding.get("end_column", start_col + 1)

        return {
            "ruleId": finding.get("id", "SERAPH-000"),
            "ruleIndex": rule_index,
            "level": self.SEVERITY_MAP.get(finding.get("severity", "INFO").upper(), "warning"),
            "message": {
                "text": self._result_message(finding),
            },
            "locations": [
                {
                    "physicalLocation": {
                        "artifactLocation": {"uri": file_path, "uriBaseId": "%SRCROOT%"},
                        "region": {
                            "startLine": line,
                            "startColumn": start_col,
                            "endColumn": end_col,
                        },
                    }
                }
            ],
            "properties": {
                "blast_radius": finding.get("blast_radius", 0.0),
                "cp_confidence": finding.get("cp_confidence", 0.0),
                "cp_low": finding.get("cp_low", 0.0),
                "cp_high": finding.get("cp_high", 0.0),
                "roi_per_hour": finding.get("roi_per_hour", 0.0),
            },
        }

    def _result_message(self, finding: dict[str, Any]) -> str:
        parts = [finding.get("what", "")]
        if finding.get("blast_radius"):
            parts.append(f"Blast radius: {finding['blast_radius']:.1f}%")
        if finding.get("cp_confidence"):
            parts.append(f"CP confidence: {finding['cp_confidence']:.1f}%")
        return " | ".join(parts)

    def _cvss_from_severity(self, severity: str) -> float:
        mapping = {"CRITICAL": 9.5, "HIGH": 8.0, "MEDIUM": 5.5, "LOW": 3.0, "INFO": 0.0}
        return mapping.get(severity.upper(), 5.0)

    def _uuid_from_target(self, target: str) -> str:
        return hashlib.sha256(target.encode()).hexdigest()[:16]
