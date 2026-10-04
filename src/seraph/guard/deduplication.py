"""Deterministic, scanner-independent finding deduplication for Seraph Guard.

The deduplicator merges observations of the same security condition while
preserving independent scanner provenance and distinct locations.  It never
uses scanner name as an identity key and never merges across different files,
CWEs, or incompatible source/sink semantics.
"""

from __future__ import annotations

import hashlib
import math
import re

from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any


class DeduplicationEngine:
    """Conservative semantic deduplication with deterministic output."""

    version = "2.2.0"
    MAX_TEXT = 240
    NEARBY_LINE_DISTANCE = 2

    def deduplicate(self, findings: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
        items = [dict(item) for item in findings]
        if not items:
            return []

        indexed = list(enumerate(items))
        indexed.sort(key=lambda pair: self._stable_sort_key(pair[1], pair[0]))

        clusters: list[dict[str, Any]] = []
        exact_index: dict[tuple[Any, ...], int] = {}
        flow_index: dict[tuple[Any, ...], int] = {}

        for original_index, item in indexed:
            prepared = self._prepare(item, original_index)
            exact_key = self._exact_key(prepared)
            cluster_index = exact_index.get(exact_key)
            if cluster_index is None:
                flow_key = self._flow_key(prepared)
                if flow_key is not None:
                    cluster_index = flow_index.get(flow_key)

            if cluster_index is None:
                cluster_index = self._find_near_cluster(prepared, clusters)

            if cluster_index is None:
                cluster = self._new_cluster(prepared)
                clusters.append(cluster)
                cluster_index = len(clusters) - 1
                exact_index[exact_key] = cluster_index
                flow_key = self._flow_key(prepared)
                if flow_key is not None:
                    flow_index.setdefault(flow_key, cluster_index)
            else:
                self._merge_into(clusters[cluster_index], prepared)
                exact_index.setdefault(exact_key, cluster_index)
                flow_key = self._flow_key(prepared)
                if flow_key is not None:
                    flow_index.setdefault(flow_key, cluster_index)

        output: list[dict[str, Any]] = []
        for cluster in clusters:
            result = self._finalize(cluster)
            output.append(result)

        output.sort(key=self._output_sort_key)
        return output

    # ------------------------------------------------------------------
    # Normalization and identity
    # ------------------------------------------------------------------

    def _prepare(self, item: Mapping[str, Any], index: int) -> dict[str, Any]:
        out = dict(item)
        out["_original_index"] = index
        out["_normalized_file"] = self._norm_path(out.get("file") or out.get("path") or "")
        out["_cwe"] = self._norm_cwe(out.get("cwe") or self._metadata(out).get("cwe"))
        out["_category"] = self._norm_text(out.get("category", ""))
        out["_rule_family"] = self._rule_family(out)
        out["_source_semantics"] = self._source_semantics(out)
        out["_sink_semantics"] = self._sink_semantics(out)
        out["_line"] = self._int_or_zero(out.get("line"))
        out["_column"] = self._int_or_zero(out.get("column"))
        return out

    def _exact_key(self, item: Mapping[str, Any]) -> tuple[Any, ...]:
        return (
            item.get("_normalized_file", ""),
            item.get("_cwe", ""),
            item.get("_category", ""),
            item.get("_rule_family", ""),
            item.get("_source_semantics", ""),
            item.get("_sink_semantics", ""),
        )

    def _flow_key(self, item: Mapping[str, Any]) -> tuple[Any, ...] | None:
        source = str(item.get("_source_semantics", ""))
        sink = str(item.get("_sink_semantics", ""))
        if not source and not sink:
            return None
        return (
            item.get("_normalized_file", ""),
            item.get("_cwe", ""),
            item.get("_category", ""),
            source,
            sink,
        )

    def _find_near_cluster(
        self, item: Mapping[str, Any], clusters: list[dict[str, Any]]
    ) -> int | None:
        for index, cluster in enumerate(clusters):
            canonical = cluster["canonical"]
            if not self._compatible_scope(item, canonical):
                continue
            if not self._compatible_flow(item, canonical):
                continue
            family_a = str(item.get("_rule_family", ""))
            family_b = str(canonical.get("_rule_family", ""))
            if family_a and family_b:
                similarity = self._token_similarity(family_a, family_b)
                if similarity < 0.78:
                    continue
            elif family_a != family_b:
                continue
            return index
        return None

    @staticmethod
    def _compatible_scope(a: Mapping[str, Any], b: Mapping[str, Any]) -> bool:
        return (
            str(a.get("_normalized_file", "")) == str(b.get("_normalized_file", ""))
            and str(a.get("_cwe", "")) == str(b.get("_cwe", ""))
            and str(a.get("_category", "")) == str(b.get("_category", ""))
        )

    @staticmethod
    def _compatible_flow(a: Mapping[str, Any], b: Mapping[str, Any]) -> bool:
        source_a = str(a.get("_source_semantics", ""))
        source_b = str(b.get("_source_semantics", ""))
        sink_a = str(a.get("_sink_semantics", ""))
        sink_b = str(b.get("_sink_semantics", ""))
        if source_a and source_b and source_a != source_b:
            return False
        return not (sink_a and sink_b and sink_a != sink_b)

    # ------------------------------------------------------------------
    # Cluster management
    # ------------------------------------------------------------------

    def _new_cluster(self, item: Mapping[str, Any]) -> dict[str, Any]:
        canonical = dict(item)
        cid = self._cluster_id(item)
        canonical["_cluster_id"] = cid
        locations = [self._location(item)]
        canonical["locations"] = locations
        canonical["location_count"] = len(locations)
        canonical["_scanner_sources"] = self._scanner_sources(item)
        canonical["_rule_ids"] = self._rule_ids(item)
        canonical["_finding_ids"] = self._finding_ids(item)
        canonical["_evidence_records"] = self._evidence(item)
        canonical["_originals"] = [item]
        return {"canonical": canonical}

    def _merge_into(self, cluster: dict[str, Any], item: Mapping[str, Any]) -> None:
        canonical = cluster["canonical"]
        originals: list[Mapping[str, Any]] = canonical.setdefault("_originals", [])
        originals.append(item)

        winner = self._better_observation(item, canonical)
        if winner is item:
            preserved = {
                "locations": canonical.get("locations", []),
                "location_count": canonical.get("location_count", 1),
                "_cluster_id": canonical.get("_cluster_id"),
                "_scanner_sources": canonical.get("_scanner_sources", []),
                "_rule_ids": canonical.get("_rule_ids", []),
                "_finding_ids": canonical.get("_finding_ids", []),
                "_evidence_records": canonical.get("_evidence_records", []),
                "_originals": originals,
            }
            canonical.clear()
            canonical.update(dict(item))
            canonical.update(preserved)

        canonical["locations"] = self._merge_locations(
            canonical.get("locations", []), [self._location(item)]
        )
        canonical["location_count"] = len(canonical["locations"])
        canonical["_scanner_sources"] = sorted(
            set(canonical.get("_scanner_sources", [])) | set(self._scanner_sources(item))
        )
        canonical["_rule_ids"] = sorted(
            set(canonical.get("_rule_ids", [])) | set(self._rule_ids(item))
        )
        canonical["_finding_ids"] = sorted(
            set(canonical.get("_finding_ids", [])) | set(self._finding_ids(item))
        )
        canonical["_evidence_records"] = self._merge_evidence(
            canonical.get("_evidence_records", []), self._evidence(item)
        )
        self._merge_metadata(canonical, item)

        # Preserve the strongest impact record while combining independent evidence.
        self._merge_blast_radius(canonical, item)

    def _finalize(self, cluster: dict[str, Any]) -> dict[str, Any]:
        item = dict(cluster["canonical"])
        cluster_id = str(item.pop("_cluster_id", ""))
        originals = item.pop("_originals", [])
        item.pop("_normalized_file", None)
        item.pop("_cwe", None)
        item.pop("_category", None)
        item.pop("_rule_family", None)
        item.pop("_source_semantics", None)
        item.pop("_sink_semantics", None)
        item.pop("_line", None)
        item.pop("_column", None)
        original_index = item.get("_original_index", 0)

        metadata = item.get("metadata")
        if not isinstance(metadata, dict):
            metadata = {}
        metadata = dict(metadata)
        metadata["dedup"] = {
            "engine_version": self.version,
            "cluster_id": cluster_id,
            "observation_count": max(1, len(originals)),
            "scanner_sources": sorted(set(item.pop("_scanner_sources", []))),
            "contributing_rule_ids": sorted(set(item.pop("_rule_ids", []))),
            "merged_finding_ids": sorted(set(item.pop("_finding_ids", []))),
            "semantic_key": self._semantic_key_for_output(item),
        }
        metadata.pop("_original", None)
        item["metadata"] = metadata
        item["dedup_cluster_id"] = cluster_id

        evidence = item.pop("_evidence_records", [])
        if evidence:
            metadata["dedup_evidence"] = evidence

        locations = item.get("locations", [])
        item["locations"] = locations
        item["location_count"] = len(locations) or 1
        original = item.get("_original")
        if original is not None:
            item["_original"] = original
        item["_original_index"] = original_index
        return item

    # ------------------------------------------------------------------
    # Merge helpers
    # ------------------------------------------------------------------

    def _better_observation(self, a: Mapping[str, Any], b: Mapping[str, Any]) -> Mapping[str, Any]:
        return a if self._observation_score(a) > self._observation_score(b) else b

    def _observation_score(self, item: Mapping[str, Any]) -> tuple[float, ...]:
        severity = self._severity_weight(item.get("effective_severity") or item.get("severity"))
        confidence = self._bounded_float(item.get("confidence"), 0.0)
        blast = item.get("blast_radius")
        assessed = 0.0
        if isinstance(blast, dict):
            assessed = (
                1.0 if bool(blast.get("is_assessed")) and bool(blast.get("evidence")) else 0.0
            )
        return (
            assessed,
            float(len(self._evidence(item))),
            severity,
            confidence,
            -float(self._int_or_zero(item.get("line"))),
        )

    def _merge_metadata(self, canonical: dict[str, Any], incoming: Mapping[str, Any]) -> None:
        current_raw = canonical.get("metadata")
        current: dict[str, Any] = current_raw if isinstance(current_raw, dict) else {}
        other_raw = incoming.get("metadata")
        other: dict[str, Any] = other_raw if isinstance(other_raw, dict) else {}

        merged = dict(current)
        for key, value in other.items():
            if key == "dedup":
                continue
            if key not in merged or merged[key] in (None, "", [], {}):
                merged[key] = value
        canonical["metadata"] = merged

        canonical["tags"] = sorted(
            set(self._as_strings(canonical.get("tags")))
            | set(self._as_strings(incoming.get("tags")))
        )
        canonical["affected_files"] = sorted(
            set(self._as_strings(canonical.get("affected_files")))
            | set(self._as_strings(incoming.get("affected_files")))
        )
        aliases = sorted(
            set(self._as_strings(canonical.get("cwe_aliases")))
            | set(self._as_strings(incoming.get("cwe_aliases")))
        )
        if aliases:
            canonical["cwe_aliases"] = aliases

    def _merge_blast_radius(self, canonical: dict[str, Any], incoming: Mapping[str, Any]) -> None:
        existing = canonical.get("blast_radius")
        other = incoming.get("blast_radius")
        if not isinstance(other, dict):
            return
        if not isinstance(existing, dict):
            canonical["blast_radius"] = dict(other)
            return
        existing = dict(existing)
        for key in ("affected_resources", "affected_services", "data_at_risk", "causal_path"):
            existing[key] = sorted(
                set(self._as_strings(existing.get(key))) | set(self._as_strings(other.get(key)))
            )
        existing["blast_radius_score"] = max(
            self._bounded_float(existing.get("blast_radius_score")),
            self._bounded_float(other.get("blast_radius_score")),
        )
        existing["reduction_if_fixed"] = max(
            self._bounded_float(existing.get("reduction_if_fixed")),
            self._bounded_float(other.get("reduction_if_fixed")),
        )
        evidence = self._merge_evidence(existing.get("evidence", []), other.get("evidence", []))
        existing["evidence"] = evidence
        assessed_candidates = [bool(existing.get("is_assessed")), bool(other.get("is_assessed"))]
        existing["is_assessed"] = any(assessed_candidates) and bool(evidence)
        prov = [str(existing.get("provenance", "")), str(other.get("provenance", ""))]
        existing["provenance"] = self._strongest_provenance(
            prov, bool(existing["is_assessed"]), bool(evidence)
        )
        caveats = self._as_strings(existing.get("caveats")) + self._as_strings(other.get("caveats"))
        existing["caveats"] = sorted(set(caveats))
        canonical["blast_radius"] = existing

    # ------------------------------------------------------------------
    # Evidence / provenance helpers
    # ------------------------------------------------------------------

    def _evidence(self, item: Mapping[str, Any]) -> list[dict[str, Any]]:
        blast = item.get("blast_radius")
        if isinstance(blast, dict) and isinstance(blast.get("evidence"), list):
            return [dict(x) for x in blast["evidence"] if isinstance(x, dict)]
        metadata = self._metadata(item)
        raw = metadata.get("impact_evidence", metadata.get("dedup_evidence", []))
        return [dict(x) for x in raw if isinstance(x, dict)] if isinstance(raw, list) else []

    def _merge_evidence(self, left: Any, right: Any) -> list[dict[str, Any]]:
        merged: list[dict[str, Any]] = []
        seen: set[str] = set()
        for record in [
            *(left if isinstance(left, list) else []),
            *(right if isinstance(right, list) else []),
        ]:
            if not isinstance(record, dict):
                continue
            key = repr(sorted((str(k), str(v)) for k, v in record.items()))
            if key not in seen:
                seen.add(key)
                merged.append(dict(record))
        merged.sort(key=lambda x: repr(sorted((str(k), str(v)) for k, v in x.items())))
        return merged

    @staticmethod
    def _strongest_provenance(values: list[str], assessed: bool, evidence: bool) -> str:
        normalized = {v.upper() for v in values if v}
        if assessed and evidence and "MEASURED" in normalized:
            return "MEASURED"
        if assessed and evidence and "INFERRED" in normalized:
            return "INFERRED"
        if assessed and evidence and "ASSERTED_ASSESSED" in normalized:
            return "ASSERTED_ASSESSED"
        if normalized & {"ESTIMATED", "UNKNOWN"}:
            return "ESTIMATED" if "ESTIMATED" in normalized else "UNKNOWN"
        return "INFERRED" if assessed and evidence else "UNKNOWN"

    # ------------------------------------------------------------------
    # String/identity utilities
    # ------------------------------------------------------------------

    def _cluster_id(self, item: Mapping[str, Any]) -> str:
        raw = "|".join(map(str, self._exact_key(item)))
        return "DEDUP-" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]

    def _semantic_key_for_output(self, item: Mapping[str, Any]) -> str:
        raw = "|".join(
            (
                str(item.get("file", "")),
                str(item.get("line", 0)),
                str(item.get("cwe", "")),
                self._rule_family(item),
                self._source_semantics(item),
                self._sink_semantics(item),
            )
        )
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]

    def _rule_family(self, item: Mapping[str, Any]) -> str:
        metadata = self._metadata(item)
        raw = str(
            item.get("rule_name")
            or metadata.get("rule_name")
            or item.get("title")
            or item.get("rule_id")
            or ""
        )
        raw = raw.lower()
        for prefix in ("pattern-", "pattern:", "taint-", "taint:", "seraph-", "rule-"):
            raw = raw.removeprefix(prefix)
        raw = re.sub(r"[0-9a-f]{8,}", "", raw)
        raw = re.sub(r"[^a-z0-9]+", " ", raw)
        return " ".join(raw.split())[: self.MAX_TEXT]

    def _source_semantics(self, item: Mapping[str, Any]) -> str:
        metadata = self._metadata(item)
        value = metadata.get("source") or metadata.get("source_function")
        if not value:
            path = metadata.get("taint_path")
            if isinstance(path, list) and path:
                first = path[0] if isinstance(path[0], dict) else {}
                value = first.get("source") or first.get("function") or first.get("from")
        return self._norm_text(value)

    def _sink_semantics(self, item: Mapping[str, Any]) -> str:
        metadata = self._metadata(item)
        value = metadata.get("sink") or metadata.get("sink_function")
        if not value:
            path = metadata.get("taint_path")
            if isinstance(path, list) and path:
                last = path[-1] if isinstance(path[-1], dict) else {}
                value = last.get("sink") or last.get("function") or last.get("to")
        return self._norm_text(value)

    @staticmethod
    def _location(item: Mapping[str, Any]) -> dict[str, Any]:
        return {
            "file": item.get("file") or item.get("path") or "",
            "line": int(item.get("line", 0) or 0),
            "column": int(item.get("column", 0) or 0),
        }

    @staticmethod
    def _merge_locations(left: Any, right: list[dict[str, Any]]) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        seen: set[tuple[Any, ...]] = set()
        for record in [*(left if isinstance(left, list) else []), *right]:
            if not isinstance(record, dict):
                continue
            key = (
                str(record.get("file", "")),
                int(record.get("line", 0) or 0),
                int(record.get("column", 0) or 0),
            )
            if key not in seen:
                seen.add(key)
                result.append({"file": key[0], "line": key[1], "column": key[2]})
        result.sort(key=lambda x: (x["file"], x["line"], x["column"]))
        return result

    @staticmethod
    def _scanner_sources(item: Mapping[str, Any]) -> list[str]:
        scanner = str(item.get("scanner", "")).strip()
        return [scanner] if scanner else []

    @staticmethod
    def _rule_ids(item: Mapping[str, Any]) -> list[str]:
        rule = str(item.get("rule_id", "")).strip()
        return [rule] if rule else []

    @staticmethod
    def _finding_ids(item: Mapping[str, Any]) -> list[str]:
        fid = str(item.get("id", "")).strip()
        return [fid] if fid else []

    @staticmethod
    def _metadata(item: Mapping[str, Any]) -> dict[str, Any]:
        value = item.get("metadata")
        return value if isinstance(value, dict) else {}

    @staticmethod
    def _norm_path(value: Any) -> str:
        return Path(str(value or "").replace("\\", "/")).as_posix().lstrip("./").lower()

    @staticmethod
    def _norm_cwe(value: Any) -> str:
        text = str(value or "").strip().upper()
        if not text:
            return ""
        match = re.search(r"CWE[-_: ]?(\d+)", text)
        return f"CWE-{match.group(1)}" if match else text

    @staticmethod
    def _norm_text(value: Any) -> str:
        text = str(value or "").strip().lower()
        text = re.sub(r"\s+", " ", text)
        return text[:240]

    @staticmethod
    def _token_similarity(a: str, b: str) -> float:
        sa = set(a.split())
        sb = set(b.split())
        if not sa and not sb:
            return 1.0
        if not sa or not sb:
            return 0.0
        return len(sa & sb) / len(sa | sb)

    @staticmethod
    def _int_or_zero(value: Any) -> int:
        try:
            return max(0, int(value or 0))
        except (TypeError, ValueError):
            return 0

    @staticmethod
    def _bounded_float(value: Any, default: float = 0.0) -> float:
        try:
            x = float(value)
        except (TypeError, ValueError):
            return default
        if not math.isfinite(x):
            return default
        return max(0.0, min(100.0, x))

    @staticmethod
    def _severity_weight(value: Any) -> int:
        raw = str(getattr(value, "value", value) or "info").lower()
        return {"critical": 4, "high": 3, "medium": 2, "low": 1, "info": 0}.get(raw, 0)

    @staticmethod
    def _as_strings(value: Any) -> list[str]:
        if isinstance(value, str):
            return [value] if value else []
        if not isinstance(value, (list, tuple, set)):
            return []
        return [str(v) for v in value if str(v)]

    def _output_sort_key(self, item: Mapping[str, Any]) -> tuple[Any, ...]:
        return (
            self._norm_path(item.get("file") or item.get("path")),
            self._int_or_zero(item.get("line")),
            self._int_or_zero(item.get("column")),
            self._norm_cwe(item.get("cwe") or self._metadata(item).get("cwe")),
            self._norm_text(item.get("rule_id") or item.get("title")),
            str(item.get("id", "")),
        )

    def _stable_sort_key(self, item: Mapping[str, Any], index: int) -> tuple[Any, ...]:
        return (*self._output_sort_key(item), index)


__all__ = ["DeduplicationEngine"]
