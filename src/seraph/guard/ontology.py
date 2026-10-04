"""Central in-memory Seraph Ontology for scanner findings and impact state.

The ontology is deterministic within a scan, explicitly typed, safe for
serialization, and never stores raw secret values or source snippets.
"""

from __future__ import annotations

import hashlib
import logging
import threading

from collections.abc import Iterable
from typing import Any, cast

from seraph.guard.scanners.base import (
    Finding,
    LinkType,
    OntologyLink,
    OntologyObject,
    OntologyType,
)


logger = logging.getLogger(__name__)

_SCHEMA_VERSION = "2.2"


def _stable_id(kind: str, *parts: Any) -> str:
    raw = "|".join([kind, *[str(p) for p in parts]])
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:20]


def _enum_value(value: Any) -> str:
    return str(getattr(value, "value", value))


def _safe_metadata(value: Any) -> Any:
    if isinstance(value, dict):
        sensitive = {
            "value",
            "secret",
            "secret_value",
            "raw_secret",
            "token",
            "api_key",
            "password",
            "passwd",
            "credential",
            "private_key",
            "access_token",
            "refresh_token",
            "authorization",
            "cookie",
            "client_secret",
            "bearer",
        }
        return {
            str(k): "[REDACTED]"
            if str(k).lower().replace("-", "_") in sensitive
            else _safe_metadata(v)
            for k, v in value.items()
        }
    if isinstance(value, list):
        return [_safe_metadata(v) for v in value]
    return value


class SeraphOntology:
    """Deterministic typed graph shared by Scheduler intelligence layers."""

    def __init__(self) -> None:
        self._objects: dict[str, OntologyObject] = {}
        self._links: dict[tuple[str, str, str], OntologyLink] = {}
        self._files: dict[str, OntologyObject] = {}
        self._finding_index: dict[str, str] = {}
        self._lock = threading.RLock()
        self.scan_id: str | None = None

    @property
    def object_count(self) -> int:
        return len(self._objects)

    @property
    def link_count(self) -> int:
        return len(self._links)

    @property
    def finding_count(self) -> int:
        """Number of canonical finding nodes currently present."""
        return len(self._finding_index)

    @property
    def files(self) -> dict[str, OntologyObject]:
        return dict(self._files)

    def reset(self) -> None:
        with self._lock:
            self._objects.clear()
            self._links.clear()
            self._files.clear()
            self._finding_index.clear()
            self.scan_id = None

    def _upsert_file(self, path: str) -> OntologyObject:
        key = path.replace("\\", "/")
        obj = self._files.get(key)
        if obj is None:
            obj = OntologyObject(
                id=_stable_id("file", key),
                type=OntologyType.FILE,
                name=key,
                path=key,
                properties={"category": "source_file"},
                scanner="Ontology",
                confidence=1.0,
            )
            self._files[key] = obj
            self._objects[obj.id] = obj
        return obj

    def _upsert_finding(self, finding: Finding) -> OntologyObject:
        finding_id = str(getattr(finding, "id", "") or getattr(finding, "rule_id", "finding"))
        existing_id = self._finding_index.get(finding_id)
        if existing_id and existing_id in self._objects:
            obj = self._objects[existing_id]
        else:
            obj = finding.to_ontology_object()
            # Finding bridge may already carry its stable ID; enforce it here.
            obj.id = _stable_id("finding", finding_id)
            obj.type = OntologyType.FINDING
            self._objects[obj.id] = obj
            self._finding_index[finding_id] = obj.id
            try:
                object.__setattr__(finding, "ontology_object_id", obj.id)
            except (AttributeError, TypeError):
                pass
        return obj

    def _link(
        self,
        source: str,
        target: str,
        link_type: LinkType,
        *,
        weight: float = 1.0,
        properties: dict[str, Any] | None = None,
        scanner: str = "Ontology",
    ) -> OntologyLink:
        key = (source, target, _enum_value(link_type))
        link = self._links.get(key)
        if link is not None:
            return link

        safe_properties = _safe_metadata(properties or {})
        if not isinstance(safe_properties, dict):
            safe_properties = {}

        link = OntologyLink(
            id=_stable_id("link", source, target, _enum_value(link_type)),
            source_id=source,
            target_id=target,
            type=link_type,
            weight=max(0.0, min(1.0, float(weight))),
            properties=cast("dict[str, Any]", safe_properties),
            scanner=scanner,
        )
        self._links[key] = link
        return link

    def ingest_findings(self, findings: Iterable[Finding], context: Any = None) -> None:
        with self._lock:
            if context is not None:
                self.scan_id = getattr(context, "scan_id", self.scan_id)

            for finding in findings:
                ingestion_failed = False
                try:
                    file_path = str(
                        getattr(finding, "file", "")
                        or getattr(finding, "path", "")
                        or getattr(finding, "source_file", "unknown")
                    ).replace("\\", "/")
                    file_obj = self._upsert_file(file_path)
                    finding_obj = self._upsert_finding(finding)
                    link = self._link(
                        file_obj.id,
                        finding_obj.id,
                        LinkType.CONTAINS,
                        weight=float(getattr(finding, "confidence", 1.0) or 0.0),
                        properties={
                            "line": int(getattr(finding, "line", 0) or 0),
                            "column": int(getattr(finding, "column", 0) or 0),
                        },
                        scanner=str(getattr(finding, "scanner", "Ontology")),
                    )
                    try:
                        object.__setattr__(finding, "ontology_link_ids", [link.id])
                    except (AttributeError, TypeError):
                        pass
                except Exception:
                    logger.debug(
                        "Ontology ingestion skipped due to unexpected error",
                        exc_info=True,
                    )
                    ingestion_failed = True

                if ingestion_failed:
                    continue

    def _ensure_resource(
        self, value: str, object_type: OntologyType, scanner: str = "Ontology"
    ) -> OntologyObject:
        key = str(value).strip()
        obj_id = _stable_id(object_type.value, key)
        obj = self._objects.get(obj_id)
        if obj is None:
            obj = OntologyObject(
                id=obj_id,
                type=object_type,
                name=key,
                path=key if object_type == OntologyType.FILE else "",
                properties={"resource_kind": object_type.value},
                scanner=scanner,
                confidence=1.0,
            )
            self._objects[obj.id] = obj
        return obj

    @staticmethod
    def _blast_dict(finding: Finding) -> dict[str, Any] | None:
        blast = getattr(finding, "blast_radius", None)
        if blast is None:
            return None

        if hasattr(blast, "to_dict"):
            raw = blast.to_dict()
        elif isinstance(blast, dict):
            raw = dict(blast)
        else:
            return None

        if isinstance(raw, dict):
            return cast("dict[str, Any]", raw)
        return None

    def enrich_findings(self, findings: Iterable[Finding]) -> None:
        with self._lock:
            for finding in findings:
                enrichment_failed = False
                try:
                    finding_id = str(
                        getattr(finding, "id", "") or getattr(finding, "rule_id", "finding")
                    )
                    raw_obj_id = self._finding_index.get(finding_id) or getattr(
                        finding, "ontology_object_id", ""
                    )
                    obj_id = str(raw_obj_id) if raw_obj_id else ""
                    obj = self._objects.get(obj_id) if obj_id else None
                    if obj is None:
                        obj = self._upsert_finding(finding)

                    blast = self._blast_dict(finding)
                    safe_meta = _safe_metadata(getattr(finding, "metadata", {}) or {})
                    new_props = {
                        "causal_rank": getattr(finding, "causal_rank", None),
                        "conformal_set": getattr(finding, "conformal_set", None),
                        "conformal_lower": getattr(finding, "conformal_lower", None),
                        "conformal_upper": getattr(finding, "conformal_upper", None),
                        "dedup_cluster_id": getattr(finding, "dedup_cluster_id", None),
                        "blast_radius": blast,
                        "learning": safe_meta.get("learning")
                        if isinstance(safe_meta, dict)
                        else None,
                    }
                    for key, value in new_props.items():
                        if obj.properties.get(key) != value:
                            obj.properties[key] = _safe_metadata(value)
                            obj.version += 1

                    scanner = str(getattr(finding, "scanner", "Ontology"))
                    if blast:
                        for file_path in blast.get("affected_resources", []) or []:
                            text = str(file_path)
                            if text.startswith("file:"):
                                target = self._ensure_resource(text[5:], OntologyType.FILE, scanner)
                            elif text.startswith("service:"):
                                target = self._ensure_resource(text, OntologyType.SERVICE, scanner)
                            elif text.startswith("data:"):
                                target = self._ensure_resource(
                                    text, OntologyType.DATA_STORE, scanner
                                )
                            elif text.startswith("api:"):
                                target = self._ensure_resource(
                                    text, OntologyType.API_ENDPOINT, scanner
                                )
                            else:
                                target = self._ensure_resource(text, OntologyType.FILE, scanner)
                            self._link(
                                obj.id, target.id, LinkType.BLAST_RADIUS, scanner="CausalRanker"
                            )

                        for service in blast.get("affected_services", []) or []:
                            target = self._ensure_resource(
                                str(service), OntologyType.SERVICE, scanner
                            )
                            self._link(
                                obj.id,
                                target.id,
                                LinkType.EXPOSES,
                                scanner="ImpactAssessmentEngine",
                            )

                        for datastore in blast.get("data_at_risk", []) or []:
                            target = self._ensure_resource(
                                str(datastore), OntologyType.DATA_STORE, scanner
                            )
                            self._link(
                                obj.id,
                                target.id,
                                LinkType.ACCESSES,
                                scanner="ImpactAssessmentEngine",
                            )

                        for endpoint in blast.get("api_endpoints", []) or []:
                            target = self._ensure_resource(
                                str(endpoint), OntologyType.API_ENDPOINT, scanner
                            )
                            self._link(
                                obj.id,
                                target.id,
                                LinkType.EXPOSES,
                                scanner="ImpactAssessmentEngine",
                            )

                    path = str(getattr(finding, "file", "") or getattr(finding, "path", ""))
                    file_obj = self._upsert_file(path.replace("\\", "/"))
                    link = self._link(file_obj.id, obj.id, LinkType.CONTAINS, scanner=scanner)
                    try:
                        ids = list(getattr(finding, "ontology_link_ids", []) or [])
                        if link.id not in ids:
                            ids.append(link.id)
                        object.__setattr__(finding, "ontology_link_ids", ids)
                    except (AttributeError, TypeError):
                        pass
                except Exception:
                    logger.debug(
                        "Ontology enrichment skipped due to unexpected error",
                        exc_info=True,
                    )
                    enrichment_failed = True

                if enrichment_failed:
                    continue

    def get_object(self, object_id: str) -> OntologyObject | None:
        return self._objects.get(str(object_id))

    def get_links(self) -> list[OntologyLink]:
        return list(self._links.values())

    def to_dict(self) -> dict[str, Any]:
        with self._lock:
            objects = [obj.to_dict() for obj in sorted(self._objects.values(), key=lambda x: x.id)]
            links = [link.to_dict() for link in sorted(self._links.values(), key=lambda x: x.id)]
        return {
            "schema_version": _SCHEMA_VERSION,
            "scan_id": self.scan_id,
            "object_count": len(objects),
            "link_count": len(links),
            "objects": objects,
            "links": links,
        }


__all__ = ["SeraphOntology"]
