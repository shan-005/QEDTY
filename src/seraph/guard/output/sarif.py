"""Standards-oriented SARIF 2.1.0 output for Seraph Guard.

The formatter deliberately preserves the finding's canonical ``rule_id`` so a
JSON finding and its SARIF counterpart have a stable cross-format identity.
Only sanitized fields supplied by the finding serialization contract are
emitted; raw secret values are never added by this formatter.
"""

from __future__ import annotations

import hashlib
import json
import math

from collections.abc import Iterable
from pathlib import Path
from typing import Any


class SARIFFormatter:
    """Generate SARIF 2.1.0 for sanitized Seraph finding dictionaries."""

    SARIF_VERSION = "2.1.0"
    SARIF_SCHEMA = (
        "https://raw.githubusercontent.com/oasis-tcs/sarif-spec/"
        "master/Schemata/sarif-schema-2.1.0.json"
    )

    _LEVELS = {
        "critical": "error",
        "high": "error",
        "medium": "warning",
        "low": "note",
        "info": "note",
    }

    def __init__(self, tool_name: str = "Seraph Guard", tool_version: str = "0.1.0") -> None:
        self.tool_name = str(tool_name)
        self.tool_version = str(tool_version)

    @staticmethod
    def _string(value: Any, default: str = "") -> str:
        if value is None:
            return default
        enum_value = getattr(value, "value", value)
        return str(enum_value)

    @classmethod
    def _sanitize_number(cls, value: Any, default: float = 0.0) -> float | int:
        if isinstance(value, bool):
            return int(value)
        try:
            number = float(value)
        except (TypeError, ValueError):
            return default
        if not math.isfinite(number):
            return default
        if number.is_integer():
            return int(number)
        return number

    @classmethod
    def _resolve_severity(cls, finding: dict[str, Any]) -> str:
        raw = finding.get("effective_severity") or finding.get("severity") or "info"
        return cls._string(raw, "info").strip().lower() or "info"

    @staticmethod
    def _fingerprint(finding: dict[str, Any]) -> str:
        """Return a deterministic Seraph-owned finding identity fingerprint."""
        parts = (
            str(finding.get("id") or ""),
            str(finding.get("rule_id") or ""),
            str(finding.get("file") or finding.get("path") or "").replace("\\", "/"),
            str(int(finding.get("line") or 0)),
            str(int(finding.get("column") or 0)),
            str(finding.get("cwe") or ""),
            str(finding.get("scanner") or ""),
        )
        return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()

    @staticmethod
    def _rule_id(finding: dict[str, Any]) -> str:
        value = finding.get("rule_id") or finding.get("id") or "seraph/unknown"
        text = str(value).strip()
        return text or "seraph/unknown"

    @staticmethod
    def _normalized_uri(path: Any) -> str:
        text = str(path or "").replace("\\", "/")
        text = text.removeprefix("file://")
        while text.startswith("./"):
            text = text[2:]
        return text

    @staticmethod
    def _blast_data(finding: dict[str, Any]) -> dict[str, Any]:
        blast = finding.get("blast_radius")
        if isinstance(blast, dict):
            return blast
        if blast is None:
            return {}
        if hasattr(blast, "to_dict"):
            value = blast.to_dict()
            return value if isinstance(value, dict) else {}
        return {
            key: getattr(blast, key)
            for key in (
                "blast_radius_score",
                "reduction_if_fixed",
                "is_assessed",
                "provenance",
                "evidence",
                "causal_path",
            )
            if hasattr(blast, key)
        }

    def _build_single_result(self, finding: dict[str, Any]) -> dict[str, Any]:
        rule_id = self._rule_id(finding)
        severity = self._resolve_severity(finding)
        file_path = self._normalized_uri(finding.get("file") or finding.get("path"))
        line = max(1, int(finding.get("line") or 1))
        column = max(1, int(finding.get("column") or 1))
        blast = self._blast_data(finding)

        message_text = self._string(
            finding.get("message")
            or finding.get("description")
            or finding.get("title")
            or "Finding"
        )
        if not message_text:
            message_text = "Finding"

        properties: dict[str, Any] = {
            "finding_id": self._string(finding.get("id")),
            "confidence": self._sanitize_number(finding.get("confidence", 0.0)),
            "blast_radius_score": self._sanitize_number(
                blast.get("blast_radius_score", blast.get("score", 0.0))
            ),
            "blast_radius_reduction_if_fixed": self._sanitize_number(
                blast.get("reduction_if_fixed", 0.0)
            ),
            "blast_radius_assessed": bool(blast.get("is_assessed", False)),
            "blast_radius_provenance": self._string(blast.get("provenance", "UNKNOWN")).upper(),
            "scanner": self._string(finding.get("scanner")),
            "category": self._string(finding.get("category")),
            "cwe": self._string(finding.get("cwe")),
            "causal_rank": self._sanitize_number(finding.get("causal_rank"), 0),
            "conformal_lower": self._sanitize_number(finding.get("conformal_lower"), 0.0)
            if finding.get("conformal_lower") is not None
            else None,
            "conformal_upper": self._sanitize_number(finding.get("conformal_upper"), 0.0)
            if finding.get("conformal_upper") is not None
            else None,
        }

        result: dict[str, Any] = {
            "ruleId": rule_id,
            "level": self._LEVELS.get(severity, "warning"),
            "message": {"text": message_text},
            "locations": [
                {
                    "physicalLocation": {
                        "artifactLocation": {
                            "uri": file_path,
                            "uriBaseId": "%SRCROOT%",
                        },
                        "region": {
                            "startLine": line,
                            "startColumn": column,
                        },
                    }
                }
            ],
            "partialFingerprints": {
                # Standard ecosystem-facing fingerprint retained for SARIF
                # consumers that recognize the conventional location key.
                "primaryLocationLineHash": self._string(
                    finding.get("id")
                    or finding.get("rule_id")
                    or f"{rule_id}:{file_path}:{line}:{column}"
                ),
                # Seraph-owned namespace is explicitly versioned so its
                # identity contract can evolve without silently changing the
                # meaning of existing fingerprints.
                "seraphFinding/v1": self._fingerprint(finding),
            },
            "properties": properties,
        }

        # Preserve an independently supplied flow representation only when it
        # contains concrete file locations. This does not execute project code.
        affected = finding.get("affected_files") or blast.get("affected_resources") or []
        flow_locations: list[dict[str, Any]] = []
        if isinstance(affected, (list, tuple)):
            for value in affected:
                text = str(value)
                text = text.removeprefix("file:")
                uri = self._normalized_uri(text)
                if uri:
                    flow_locations.append(
                        {
                            "location": {
                                "physicalLocation": {
                                    "artifactLocation": {"uri": uri, "uriBaseId": "%SRCROOT%"}
                                }
                            }
                        }
                    )
        if flow_locations:
            result["codeFlows"] = [{"threadFlows": [{"locations": flow_locations}]}]

        return result

    def _build_rules(self, finding_dicts: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
        rules: list[dict[str, Any]] = []
        seen: set[str] = set()
        for finding in finding_dicts:
            rule_id = self._rule_id(finding)
            if rule_id in seen:
                continue
            seen.add(rule_id)
            severity = self._resolve_severity(finding)
            title = self._string(finding.get("title") or finding.get("rule_name") or rule_id)
            description = self._string(
                finding.get("description") or finding.get("message") or title
            )
            rules.append(
                {
                    "id": rule_id,
                    "name": title[:256] or rule_id,
                    "shortDescription": {"text": title[:512] or rule_id},
                    "fullDescription": {"text": description[:2048] or title[:512] or rule_id},
                    "defaultConfiguration": {"level": self._LEVELS.get(severity, "warning")},
                    "properties": {
                        "category": self._string(finding.get("category"), "unknown"),
                        "scanner": self._string(finding.get("scanner"), "unknown"),
                        "severity": severity,
                    },
                }
            )
        return rules

    def format(self, finding_dicts: list[dict[str, Any]], scan_path: str = ".") -> dict[str, Any]:
        rules = self._build_rules(finding_dicts)
        results = [self._build_single_result(finding) for finding in finding_dicts]
        return {
            "$schema": self.SARIF_SCHEMA,
            "version": self.SARIF_VERSION,
            "runs": [
                {
                    "tool": {
                        "driver": {
                            "name": self.tool_name,
                            "version": self.tool_version,
                            "informationUri": "https://github.com/IRIN-0/seraph",
                            "organization": "Seraph Security",
                            "rules": rules,
                        }
                    },
                    "results": results,
                    "invocations": [
                        {"executionSuccessful": True, "toolExecutionNotifications": []}
                    ],
                    "originalUriBaseIds": {
                        "%SRCROOT%": {"uri": Path(scan_path).resolve().as_uri() + "/"}
                    },
                }
            ],
        }

    def write(
        self, finding_dicts: list[dict[str, Any]], scan_path: str, output_path: str | Path
    ) -> None:
        payload = self.format(finding_dicts, scan_path)
        target = Path(output_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


SarifOutput = SARIFFormatter

__all__ = ["SARIFFormatter", "SarifOutput"]
