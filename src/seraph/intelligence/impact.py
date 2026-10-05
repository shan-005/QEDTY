"""Static repository impact assessment for Seraph Guard.

The engine never executes target code. It builds a bounded source/config graph,
parses repository-local relationships, and emits finding-specific evidence.
Impact scores are normalized structural prioritization values from 0..100;
they are not production-loss probabilities and not causal-effect estimates.
"""

from __future__ import annotations

import ast
import os
import re

from collections import defaultdict, deque
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, cast

from seraph.sources.repository.scanners.base import BlastRadius, Finding, ScanContext


DEFAULT_SKIP_DIRS = {
    ".git",
    ".hg",
    ".svn",
    ".venv",
    "venv",
    "env",
    "node_modules",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".tox",
    ".nox",
    ".seraph-learn",
    ".seraph",
    ".seraph-cache",
    ".cache",
    ".terraform",
    ".parcel-cache",
    ".next",
    ".nuxt",
    ".turbo",
    ".svelte-kit",
    ".serverless",
    ".direnv",
    "dist",
    "build",
    "target",
    "coverage",
    ".gradle",
    ".idea",
    ".vscode",
    "vendor",
    "third_party",
    "generated",
    "gen",
    "Pods",
    "Carthage",
    "DerivedData",
}

SPECIAL_FILENAMES = {
    "Dockerfile",
    "Containerfile",
    "Makefile",
    "GNUmakefile",
    "Jenkinsfile",
    ".dockerignore",
    "docker-compose.yml",
    "docker-compose.yaml",
    "compose.yml",
    "compose.yaml",
    "Procfile",
    "Vagrantfile",
    "Gemfile",
    "Rakefile",
    "Brewfile",
}

SOURCE_SUFFIXES = {
    ".py",
    ".pyi",
    ".js",
    ".jsx",
    ".ts",
    ".tsx",
    ".mjs",
    ".cjs",
    ".vue",
    ".svelte",
    ".go",
    ".java",
    ".kt",
    ".kts",
    ".groovy",
    ".scala",
    ".rs",
    ".c",
    ".h",
    ".cc",
    ".cpp",
    ".cxx",
    ".hpp",
    ".hh",
    ".cs",
    ".fs",
    ".fsx",
    ".vb",
    ".php",
    ".rb",
    ".swift",
    ".m",
    ".mm",
    ".dart",
    ".ex",
    ".exs",
    ".erl",
    ".hrl",
    ".clj",
    ".cljs",
    ".sh",
    ".bash",
    ".zsh",
    ".fish",
    ".pl",
    ".pm",
    ".tf",
    ".tfvars",
    ".yaml",
    ".yml",
    ".json",
    ".toml",
    ".xml",
    ".gradle",
    ".properties",
    ".proto",
    ".graphql",
    ".gql",
    ".sql",
}

MAX_FILE_BYTES = 2 * 1024 * 1024
DEFAULT_MAX_FILES = 20_000
DEFAULT_MAX_REVERSE_HOPS = 3
DEFAULT_MAX_AFFECTED_FILES = 40


def _default_str_set_map() -> defaultdict[str, set[str]]:
    return defaultdict[str, set[str]](set)


@dataclass(frozen=True)
class EdgeEvidence:
    source: str
    target: str
    relation: str
    evidence: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "target": self.target,
            "relation": self.relation,
            "evidence": self.evidence,
        }


@dataclass
class RepositoryGraph:
    root: Path
    files: set[str] = field(default_factory=set)
    file_text: dict[str, str] = field(default_factory=dict)
    imports: dict[str, set[str]] = field(default_factory=_default_str_set_map)
    reverse_imports: dict[str, set[str]] = field(default_factory=_default_str_set_map)
    edge_evidence: list[EdgeEvidence] = field(default_factory=list)
    services_by_file: dict[str, set[str]] = field(default_factory=_default_str_set_map)
    data_by_file: dict[str, set[str]] = field(default_factory=_default_str_set_map)
    api_by_file: dict[str, set[str]] = field(default_factory=_default_str_set_map)
    package_to_files: dict[str, set[str]] = field(default_factory=_default_str_set_map)
    module_to_files: dict[str, set[str]] = field(default_factory=_default_str_set_map)
    truncated: bool = False
    unreadable_files: list[str] = field(default_factory=list)
    parsed_families: set[str] = field(default_factory=set)
    unparsed_source_extensions: set[str] = field(default_factory=set)

    @classmethod
    def build(
        cls,
        root: Path,
        *,
        max_files: int = DEFAULT_MAX_FILES,
        max_file_bytes: int = MAX_FILE_BYTES,
        skip_dirs: Iterable[str] = DEFAULT_SKIP_DIRS,
        required_paths: Iterable[str] | None = None,
    ) -> RepositoryGraph:
        root = root.resolve()
        graph = cls(root=root)
        skip = set(skip_dirs)
        required: set[str] = {
            _normalize_repo_path(str(p)) for p in (required_paths or []) if str(p).strip()
        }

        candidates: list[tuple[str, Path]] = []
        for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
            # Do not blanket-exclude hidden directories: repositories commonly
            # keep meaningful operational/security configuration in .github,
            # .gitlab, .circleci, .devcontainer, etc.  Skip only the explicit
            # generated/cache directories declared above.
            dirnames[:] = sorted(d for d in dirnames if d not in skip)
            for filename in sorted(filenames):
                path = Path(dirpath) / filename
                if (
                    path.suffix.lower() not in SOURCE_SUFFIXES
                    and path.name not in SPECIAL_FILENAMES
                ):
                    continue
                try:
                    rel = path.relative_to(root).as_posix()
                except ValueError:
                    continue
                candidates.append((rel, path))

        candidates.sort(key=lambda item: item[0])
        required_entries = [item for item in candidates if item[0] in required]
        selected: dict[str, Path] = dict(required_entries)

        for rel, path in candidates:
            if rel in selected:
                continue
            if len(selected) >= max_files:
                graph.truncated = True
                break
            selected[rel] = path

        # A required target is always retained, even in truncated repositories.
        if len(selected) > max_files:
            graph.truncated = True

        for rel, path in sorted(selected.items()):
            try:
                size = path.stat().st_size
                if size > max_file_bytes:
                    continue
                raw = path.read_bytes()
                if b"\x00" in raw[:8192]:
                    continue
                text = raw.decode("utf-8", errors="replace")
            except OSError:
                graph.unreadable_files.append(rel)
                continue

            graph.files.add(rel)
            graph.file_text[rel] = text
            graph._index_module(rel, text)
            graph.services_by_file[rel].update(_infer_services(rel, text))
            graph.data_by_file[rel].update(_infer_data_stores(rel, text))
            graph.api_by_file[rel].update(_infer_api_endpoints(rel, text))

        graph._build_import_graph()
        return graph

    def _index_module(self, rel: str, text: str) -> None:
        path = Path(rel)
        stem = path.with_suffix("")
        parts = list(stem.parts)

        if parts and parts[-1] in {"__init__", "index"}:
            parts = parts[:-1]

        dotted = ".".join(parts)
        if dotted:
            self.module_to_files[dotted].add(rel)

        if path.name == "__init__.py":
            self.module_to_files[".".join(path.parent.parts)].add(rel)

        for match in re.finditer(r"(?m)^\s*package\s+([A-Za-z_][\w.]*)\s*;?", text):
            self.package_to_files[match.group(1)].add(rel)

        go_module = re.search(r"(?m)^\s*module\s+([^\s]+)\s*$", text)
        if go_module and path.name == "go.mod":
            self.package_to_files[go_module.group(1)].add(rel)

    def _build_import_graph(self) -> None:
        for rel, text in self.file_text.items():
            suffix = Path(rel).suffix.lower()
            edges: list[tuple[str, str, str]] = []

            if suffix in {".py", ".pyi"}:
                self.parsed_families.add("python")
                edges.extend(_python_imports(rel, text, self))
            elif suffix in {".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs", ".vue", ".svelte"}:
                self.parsed_families.add("javascript-typescript")
                edges.extend(_javascript_imports(rel, text, self))
            elif suffix == ".go":
                self.parsed_families.add("go")
                edges.extend(_go_imports(rel, text, self))
            elif suffix in {".java", ".kt", ".kts", ".scala", ".groovy"}:
                self.parsed_families.add("jvm")
                edges.extend(_jvm_imports(rel, text, self))
            elif suffix == ".rs":
                self.parsed_families.add("rust")
                edges.extend(_rust_imports(rel, text, self))
            elif suffix in {".c", ".h", ".cc", ".cpp", ".cxx", ".hpp", ".hh", ".m", ".mm"}:
                self.parsed_families.add("c-cpp-objectivec")
                edges.extend(_c_cpp_imports(rel, text, self))
            else:
                self.unparsed_source_extensions.add(suffix or "<no-extension>")

            for target, relation, evidence in edges:
                if target not in self.files or target == rel:
                    continue
                self.imports[rel].add(target)
                self.reverse_imports[target].add(rel)
                self.edge_evidence.append(EdgeEvidence(rel, target, relation, evidence))

    def direct_evidence(self, source: str) -> list[EdgeEvidence]:
        source = _normalize_repo_path(source)
        return sorted(
            (e for e in self.edge_evidence if e.source == source),
            key=lambda e: (e.target, e.relation, e.evidence),
        )

    def reverse_evidence(self, target: str) -> list[EdgeEvidence]:
        target = _normalize_repo_path(target)
        return sorted(
            (e for e in self.edge_evidence if e.target == target),
            key=lambda e: (e.source, e.relation, e.evidence),
        )

    def related_files(
        self,
        start: str,
        *,
        limit: int = DEFAULT_MAX_AFFECTED_FILES,
        max_reverse_hops: int = 2,
    ) -> list[tuple[str, str]]:
        """Return bounded direct dependencies plus downstream dependents.

        The graph is deliberately structural rather than runtime-aware.  We
        include a small number of reverse hops because a finding in a shared
        service can affect callers several files away, while bounding traversal
        prevents large monorepos from exploding the evidence set.
        """
        start = _normalize_repo_path(start)
        result: list[tuple[str, str]] = []
        seen: set[str] = set()

        for target in sorted(self.imports.get(start, ())):
            if target == start or target in seen:
                continue
            seen.add(target)
            result.append((target, "dependency"))
            if len(result) >= limit:
                return result

        max_hops = max(1, min(int(max_reverse_hops), 4))
        for target, depth in self.downstream_files(
            start, max_hops=max_hops, limit=max(0, limit - len(result))
        ):
            if target in seen:
                continue
            seen.add(target)
            relation = "dependent" if depth == 1 else f"dependent_hop_{depth}"
            result.append((target, relation))
            if len(result) >= limit:
                break

        return result

    def downstream_files(
        self,
        start: str,
        *,
        max_hops: int = DEFAULT_MAX_REVERSE_HOPS,
        limit: int = DEFAULT_MAX_AFFECTED_FILES,
    ) -> list[tuple[str, int]]:
        start = _normalize_repo_path(start)
        if start not in self.files:
            return []

        q: deque[tuple[str, int]] = deque([(start, 0)])
        seen = {start}
        result: list[tuple[str, int]] = []

        while q and len(result) < limit:
            node, depth = q.popleft()
            if depth:
                result.append((node, depth))
            if depth >= max_hops:
                continue
            for nxt in sorted(self.reverse_imports.get(node, ())):
                if nxt not in seen:
                    seen.add(nxt)
                    q.append((nxt, depth + 1))

        return result

    def shortest_undirected_path(
        self, start: str, targets: set[str], max_hops: int = DEFAULT_MAX_REVERSE_HOPS + 1
    ) -> list[str]:
        start = _normalize_repo_path(start)
        targets = {_normalize_repo_path(t) for t in targets}

        if start not in self.files:
            return []
        if start in targets:
            return [start]

        adjacency: dict[str, set[str]] = defaultdict[str, set[str]](set)

        for source, values in self.imports.items():
            for target in values:
                adjacency[source].add(target)
                adjacency[target].add(source)

        q: deque[tuple[str, list[str]]] = deque([(start, [start])])
        seen = {start}

        while q:
            node, path = q.popleft()
            if len(path) - 1 >= max_hops:
                continue

            for nxt in sorted(adjacency.get(node, ())):
                if nxt in seen:
                    continue

                next_path = [*path, nxt]
                if nxt in targets:
                    return next_path

                seen.add(nxt)
                q.append((nxt, next_path))

        return []


class ImpactAssessmentEngine:
    """Finding-specific structural impact assessment with explicit evidence."""

    version = "2.3.0"

    def __init__(
        self,
        *,
        max_files: int = DEFAULT_MAX_FILES,
        max_file_bytes: int = MAX_FILE_BYTES,
        max_reverse_hops: int = DEFAULT_MAX_REVERSE_HOPS,
        max_affected_files: int = DEFAULT_MAX_AFFECTED_FILES,
    ) -> None:
        self.max_files = max(100, int(max_files))
        self.max_file_bytes = max(64 * 1024, int(max_file_bytes))
        self.max_reverse_hops = max(1, int(max_reverse_hops))
        self.max_affected_files = max(5, int(max_affected_files))
        self._cache: dict[str, RepositoryGraph] = {}

    def graph_for(
        self,
        root: Path,
        *,
        required_paths: Iterable[str] | None = None,
        force_refresh: bool = True,
    ) -> RepositoryGraph:
        key = str(root.resolve())
        required = {_normalize_repo_path(p) for p in (required_paths or []) if str(p).strip()}
        graph = None if force_refresh else self._cache.get(key)

        if graph is not None and required.issubset(graph.files | set(graph.unreadable_files)):
            return graph

        graph = RepositoryGraph.build(
            root.resolve(),
            max_files=self.max_files,
            max_file_bytes=self.max_file_bytes,
            required_paths=required,
        )
        self._cache[key] = graph
        return graph

    def assess_findings(
        self, findings: list[Finding], context: ScanContext, *, force_refresh: bool = True
    ) -> list[Finding]:
        root = context.resolved_path
        required = {_finding_rel_path(f, root) for f in findings if _finding_rel_path(f, root)}
        graph = self.graph_for(root, required_paths=required, force_refresh=force_refresh)

        for finding in findings:
            self.assess_finding(finding, graph, context=context)

        return findings

    def assess_finding(
        self, finding: Finding, graph: RepositoryGraph, *, context: ScanContext | None = None
    ) -> BlastRadius | None:
        existing = getattr(finding, "blast_radius", None)
        if _blast_is_assessed(existing):
            return cast("BlastRadius | None", existing)

        rel = _finding_rel_path(finding, graph.root)
        if not rel or rel not in graph.files:
            _set_impact_status(finding, "file_not_in_graph")
            return None

        # Static blast assessment is intentionally for production code unless a
        # scanner supplied an explicit, already-assessed record. Tests/examples/
        # docs/framework/generated files remain unassessed and are handled by
        # severity-based ranking fallback.
        file_context = str(getattr(finding, "file_context", "") or "")
        if file_context != "production":
            _set_impact_status(finding, f"non_production_context:{file_context or 'unknown'}")
            return None

        affected: set[str] = {f"file:{rel}"}
        services: set[str] = set(graph.services_by_file.get(rel, ()))
        data_stores: set[str] = set(graph.data_by_file.get(rel, ()))
        endpoints: set[str] = set(graph.api_by_file.get(rel, ()))
        evidence: list[dict[str, Any]] = []

        direct_edges = graph.direct_evidence(rel)
        reverse_edges = graph.reverse_evidence(rel)
        taint_steps = _taint_path(finding)

        for edge in direct_edges:
            affected.add(f"file:{edge.target}")
            evidence.append(_edge_record(edge, "direct_repository_dependency"))

        for edge in reverse_edges:
            affected.add(f"file:{edge.source}")
            evidence.append(_edge_record(edge, "reverse_repository_dependency"))

        # Direct operational signals belong to the file that actually contains
        # the signal. Do not attribute a downstream datastore/API to the finding
        # merely because it is somewhere in the repository.
        for service in sorted(services):
            evidence.append(_signal_record("service", rel, service, "direct_file_signal"))

        for datastore in sorted(data_stores):
            evidence.append(_signal_record("data_store", rel, datastore, "direct_file_signal"))

        for endpoint in sorted(endpoints):
            evidence.append(_signal_record("api_endpoint", rel, endpoint, "direct_file_signal"))

        # Only follow bounded directly-connected files and preserve the actual
        # signal source in the evidence record.
        for path, relation in graph.related_files(
            rel,
            limit=self.max_affected_files,
            max_reverse_hops=self.max_reverse_hops,
        ):
            path_signals = False

            for service in sorted(graph.services_by_file.get(path, ())):
                evidence.append(_edge_signal_record(rel, path, relation, "service", service))
                services.add(service)
                path_signals = True

            for datastore in sorted(graph.data_by_file.get(path, ())):
                evidence.append(_edge_signal_record(rel, path, relation, "data_store", datastore))
                data_stores.add(datastore)
                path_signals = True

            for endpoint in sorted(graph.api_by_file.get(path, ())):
                evidence.append(_edge_signal_record(rel, path, relation, "api_endpoint", endpoint))
                endpoints.add(endpoint)
                path_signals = True

            if path_signals:
                affected.add(f"file:{path}")

        if len(taint_steps) >= 2:
            first = _stable_path_token(taint_steps[0])
            last = _stable_path_token(taint_steps[-1])
            evidence.append(
                {
                    "type": "taint_flow",
                    "relation": "source_to_sink",
                    "source": first,
                    "target": last,
                    "basis": "scanner-provided static taint path",
                    "path_length": len(taint_steps),
                }
            )

            for step in taint_steps[: self.max_affected_files]:
                token = _stable_path_token(step)
                affected.add(token)

        has_propagation_evidence = bool(direct_edges or reverse_edges or len(taint_steps) >= 2)

        # A service/data/API signal on the finding file is useful context, but by
        # itself it does not prove impact propagation. Require either a concrete
        # repository relation or a scanner-provided source-to-sink path before
        # calling the assessment structurally inferred.
        if not evidence or not has_propagation_evidence:
            _set_impact_status(finding, "insufficient_structural_evidence")
            return None

        # Build a structural path to the first operational/connected target.
        targets = {p[5:] for p in affected if p.startswith("file:") and p[5:] != rel}
        causal_path = graph.shortest_undirected_path(
            rel, targets, max_hops=self.max_reverse_hops + 1
        )

        if not causal_path and len(taint_steps) >= 2:
            causal_path = [rel, _stable_path_token(taint_steps[-1])]
        elif not causal_path:
            causal_path = [rel]

        score = _structural_score(
            direct_edges=len(direct_edges),
            reverse_edges=len(reverse_edges),
            affected_file_count=sum(1 for x in affected if x.startswith("file:")),
            service_count=len(services),
            datastore_count=len(data_stores),
            endpoint_count=len(endpoints),
            taint_hops=max(0, len(taint_steps) - 1),
            graph_truncated=graph.truncated,
        )

        blast = BlastRadius(
            affected_resources=_bounded_sorted(affected, self.max_affected_files),
            affected_services=_bounded_sorted(services, 32),
            data_at_risk=_bounded_sorted({f"data:{x}" for x in data_stores}, 32),
            blast_radius_score=score,
            reduction_if_fixed=score,
            is_assessed=True,
            causal_path=causal_path[: self.max_reverse_hops + 2],
            provenance="INFERRED",
            evidence=evidence,
            api_endpoints=_bounded_sorted(endpoints, 32),
            assessment_method="bounded_repository_graph+scanner_taint_evidence",
            caveats=(
                ["repository graph was truncated at the configured file limit"]
                if graph.truncated
                else []
            ),
        )

        try:
            object.__setattr__(finding, "blast_radius", blast)
        except (AttributeError, TypeError):
            pass

        _set_impact_status(finding, "assessed_inferred")
        _merge_blast_radius_metadata(finding, blast, graph)
        return blast


def _set_impact_status(finding: Finding, status: str) -> None:
    metadata = getattr(finding, "metadata", None)
    if isinstance(metadata, dict):
        impact = metadata.setdefault("impact_assessment", {})
        if isinstance(impact, dict):
            impact["status"] = status
            impact["engine"] = "ImpactAssessmentEngine"


def _edge_record(edge: EdgeEvidence, basis: str) -> dict[str, Any]:
    # Internal graph relations are scanner/parser implementation details.
    # Public intelligence evidence uses stable, directional vocabulary so
    # downstream consumers can reason over it without knowing the graph's
    # private edge taxonomy.
    relation = (
        "imported_dependency"
        if basis == "direct_repository_dependency"
        else "downstream_dependent"
        if basis == "reverse_repository_dependency"
        else edge.relation
    )

    return {
        "type": "repository_graph",
        "relation": relation,
        "source": f"file:{edge.source}",
        "target": f"file:{edge.target}",
        "basis": basis,
        "evidence": edge.evidence[:512],
    }


def _signal_record(signal_type: str, source_file: str, target: str, basis: str) -> dict[str, Any]:
    return {
        "type": signal_type,
        "relation": "contains_signal",
        "source": f"file:{source_file}",
        "target": f"{signal_type}:{target}",
        "basis": basis,
    }


def _edge_signal_record(
    source: str, related: str, relation: str, signal_type: str, target: str
) -> dict[str, Any]:
    return {
        "type": signal_type,
        "relation": relation,
        "source": f"file:{related}",
        "target": f"{signal_type}:{target}",
        "bridge": f"file:{source} -> file:{related}",
        "basis": "directly-connected-file signal",
    }


def _finding_rel_path(finding: Finding, root: Path) -> str:
    raw = str(getattr(finding, "file", "") or getattr(finding, "path", "") or "")
    if not raw:
        return ""

    path = Path(raw)
    if path.is_absolute():
        try:
            return path.resolve().relative_to(root.resolve()).as_posix()
        except ValueError:
            return ""

    return _normalize_repo_path(raw)


def _normalize_repo_path(path: str) -> str:
    text = str(path or "").replace("\\", "/")
    while text.startswith("./"):
        text = text[2:]
    return text.strip("/")


def _blast_is_assessed(blast: Any) -> bool:
    """Accept an assessed impact record only when its evidence contract is valid."""
    if blast is None:
        return False

    valid_provenance = {"MEASURED", "ASSERTED_ASSESSED", "INFERRED"}

    if isinstance(blast, BlastRadius):
        return bool(
            blast.is_assessed
            and str(blast.provenance or "UNKNOWN").upper() in valid_provenance
            and bool(blast.evidence)
        )

    if isinstance(blast, dict):
        assessed = bool(blast.get("is_assessed", False))
        provenance = str(
            blast.get("provenance", "ASSERTED_ASSESSED" if assessed else "UNKNOWN")
        ).upper()
        evidence = blast.get("evidence", [])
        return bool(
            assessed and provenance in valid_provenance and isinstance(evidence, list) and evidence
        )

    return bool(
        getattr(blast, "is_assessed", False)
        and str(getattr(blast, "provenance", "UNKNOWN") or "UNKNOWN").upper() in valid_provenance
        and bool(getattr(blast, "evidence", []))
    )


def _merge_blast_radius_metadata(
    finding: Finding, blast: BlastRadius, graph: RepositoryGraph
) -> None:
    metadata = getattr(finding, "metadata", None)
    if not isinstance(metadata, dict):
        return

    causal = metadata.setdefault("causal_score", {})
    if isinstance(causal, dict):
        causal.update(
            {
                "has_real_data": bool(blast.is_assessed and blast.evidence),
                "impact_provenance": blast.provenance,
                "impact_evidence_count": len(blast.evidence),
                "graph_file_count": len(graph.files),
                "graph_truncated": graph.truncated,
                "affected_resource_count": len(blast.affected_resources),
                "assessment_basis": "repository-local-static-evidence",
                "graph_parsed_families": sorted(graph.parsed_families),
                "graph_unparsed_source_extensions": sorted(graph.unparsed_source_extensions),
            }
        )

    impact = metadata.setdefault("impact_assessment", {})
    if isinstance(impact, dict):
        impact.update(
            {
                "provenance": blast.provenance,
                "is_assessed": blast.is_assessed,
                "evidence_count": len(blast.evidence),
                "graph_truncated": graph.truncated,
            }
        )


def _structural_score(
    *,
    direct_edges: int,
    reverse_edges: int,
    affected_file_count: int,
    service_count: int,
    datastore_count: int,
    endpoint_count: int,
    taint_hops: int,
    graph_truncated: bool,
) -> float:
    score = 8.0
    score += min(direct_edges, 8) * 4.0
    score += min(reverse_edges, 8) * 5.0
    score += max(0, min(12, affected_file_count - 1)) * 2.0
    score += min(service_count, 4) * 12.0
    score += min(datastore_count, 4) * 13.0
    score += min(endpoint_count, 4) * 8.0
    score += min(taint_hops, 10) * 5.0

    if graph_truncated:
        score *= 0.92

    return round(max(0.0, min(100.0, score)), 4)


def _bounded_sorted(values: Iterable[str], limit: int = 40) -> list[str]:
    return sorted({str(v) for v in values if str(v).strip()})[: max(1, int(limit))]


def _taint_path(finding: Finding) -> list[Any]:
    candidate = getattr(finding, "taint_path", None)
    if isinstance(candidate, list):
        return candidate

    meta = getattr(finding, "metadata", None)
    if isinstance(meta, dict):
        candidate = meta.get("taint_path") or meta.get("causal_path")
        if isinstance(candidate, list):
            return candidate

    return []


def _stable_path_token(step: Any) -> str:
    if isinstance(step, dict):
        file = _normalize_repo_path(str(step.get("file", "")))
        line = int(step.get("line", 0) or 0)
        action = str(step.get("action", "step"))[:80]
        if file:
            return f"flow:{file}:{line}:{action}"

    return f"flow:{str(step)[:120]}"


def _infer_services(rel: str, text: str) -> set[str]:
    parts = Path(rel).parts
    services: set[str] = set()
    markers = {
        "services",
        "apps",
        "packages",
        "components",
        "cmd",
        "deploy",
        "deployments",
        "containers",
    }

    lower = [p.lower() for p in parts]
    for marker in markers:
        if marker in lower:
            idx = lower.index(marker)
            if idx + 1 < len(parts):
                services.add(parts[idx + 1])

    if Path(rel).name.lower() in {
        "docker-compose.yml",
        "docker-compose.yaml",
        "compose.yml",
        "compose.yaml",
    }:
        for match in re.finditer(r"(?m)^\s{2}([A-Za-z0-9_.-]+):\s*$", _service_block(text)):
            services.add(match.group(1))

    kind = re.search(r"(?m)^\s*kind:\s*([A-Za-z0-9_.-]+)\s*$", text)
    name = re.search(
        r"(?ms)^metadata:\s*\n(?:\s+[^\n]+\n)*?\s{2,}name:\s*([A-Za-z0-9_.-]+)\s*$", text
    )

    if (
        kind
        and name
        and kind.group(1).lower()
        in {"deployment", "statefulset", "daemonset", "service", "job", "cronjob"}
    ):
        services.add(name.group(1))

    for match in re.finditer(r'(?m)^\s*resource\s+"([^"]+)"\s+"([^"]+)"\s*\{', text):
        services.add(f"terraform:{match.group(1)}.{match.group(2)}")

    return services


def _service_block(text: str) -> str:
    match = re.search(r"(?ms)^services:\s*\n(.*?)(?:^\S|\Z)", text)
    return match.group(1) if match else text[:8000]


def _infer_data_stores(_rel: str, text: str) -> set[str]:
    hay = text.lower()
    rules = {
        "postgres": ("postgres", "psycopg", "asyncpg", "jdbc:postgresql"),
        "mysql": ("mysql", "pymysql", "mysqlclient", "jdbc:mysql"),
        "mariadb": ("mariadb", "mariadbconnector", "jdbc:mariadb"),
        "sqlite": ("sqlite", "sqlite3"),
        "redis": ("redis", "redis.asyncio"),
        "mongodb": ("mongodb", "pymongo", "mongoose", "mongoengine"),
        "cassandra": ("cassandra", "cassandra-driver"),
        "elasticsearch": ("elasticsearch", "elastic.client"),
        "opensearch": ("opensearch",),
        "clickhouse": ("clickhouse",),
        "snowflake": ("snowflake.connector",),
        "bigquery": ("google.cloud.bigquery", "bigquery"),
        "redshift": ("redshift", "jdbc:redshift"),
        "mssql": ("pyodbc", "mssql", "sqlserver", "jdbc:sqlserver"),
        "oracle": ("cx_oracle", "oracledb", "jdbc:oracle"),
        "dynamodb": ("dynamodb", "boto3.client('dynamodb'", "@aws-sdk/client-dynamodb"),
        "object-storage": (
            "s3://",
            "boto3.client('s3'",
            "@aws-sdk/client-s3",
            "azure.storage.blob",
            "google.cloud.storage",
        ),
        "cosmosdb": ("cosmosdb", "azure.cosmos"),
        "firestore": ("firestore", "firebase_admin"),
        "sql": ("database/sql", "sqlalchemy", "django.db", "jdbc", "prisma", "gorm"),
        "kafka": ("kafka", "confluent_kafka", "@kafkajs/"),
        "rabbitmq": ("rabbitmq", "pika", "amqp", "amqplib"),
        "nats": ("nats",),
        "sqs": ("sqs", "amazonaws.com/sqs"),
        "sns": ("sns", "amazonaws.com/sns"),
        "pubsub": ("pubsub", "google.cloud.pubsub"),
    }

    hits: set[str] = set()
    for label, needles in rules.items():
        if any(needle in hay for needle in needles):
            hits.add(label)

    return hits


def _infer_api_endpoints(rel: str, text: str) -> set[str]:
    patterns = [
        r"@(?:app|router|api)\.(?:route|get|post|put|patch|delete|options|head)\(\s*[\"']([^\"']+)",
        r"@(?:GetMapping|PostMapping|PutMapping|PatchMapping|DeleteMapping|RequestMapping)\(\s*[\"']?([^\"')]+)",
        r"\b(?:router|app)\.(?:GET|POST|PUT|PATCH|DELETE|OPTIONS|HEAD)\(\s*[\"']([^\"']+)",
        r"\bpath\(\s*[\"']([^\"']+)",
        r"@Controller\(\s*[\"']([^\"']+)",
        r"\broutes?\.\s*get\(\s*[\"']([^\"']+)",
    ]

    hits: set[str] = set()
    for pattern in patterns:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            endpoint = match.group(1).strip()
            if endpoint and len(endpoint) <= 200:
                hits.add(f"{rel}#{endpoint}")

    return hits


def _python_imports(rel: str, text: str, graph: RepositoryGraph) -> list[tuple[str, str, str]]:
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return []

    out: list[tuple[str, str, str]] = []
    current = Path(rel)
    current_module = ".".join(current.with_suffix("").parts)

    if current.name == "__init__.py":
        current_module = ".".join(current.parent.parts)

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                target = _resolve_python_module(alias.name, graph)
                if target:
                    out.append((target, "imports", f"import {alias.name}"))

        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""

            if node.level:
                base_parts = current_module.split(".")[: -node.level]
                module = ".".join(p for p in [*base_parts, module] if p)

            target = _resolve_python_module(module, graph)
            if target:
                out.append((target, "imports", f"from {module} import ..."))
            else:
                for alias in node.names:
                    dotted = f"{module}.{alias.name}" if module else alias.name
                    target = _resolve_python_module(dotted, graph)
                    if target:
                        out.append((target, "imports", f"from {module} import {alias.name}"))

    return out


def _resolve_python_module(module: str, graph: RepositoryGraph) -> str | None:
    module = module.strip(".")
    if not module:
        return None

    for variant in (module, module + ".__init__"):
        candidates = sorted(graph.module_to_files.get(variant, ()))
        if candidates:
            return candidates[0]

    parts = module.split(".")
    for candidate in ("/".join(parts) + ".py", "/".join(parts) + "/__init__.py"):
        if candidate in graph.files:
            return candidate

    return None


def _javascript_imports(rel: str, text: str, graph: RepositoryGraph) -> list[tuple[str, str, str]]:
    out: list[tuple[str, str, str]] = []
    patterns = [
        r"\bfrom\s*[\"']([^\"']+)[\"']",
        r"\bimport\s*[\"']([^\"']+)[\"']",
        r"\brequire\(\s*[\"']([^\"']+)[\"']\s*\)",
    ]

    for pattern in patterns:
        for match in re.finditer(pattern, text):
            spec = match.group(1)
            if not spec.startswith("."):
                continue

            target = _resolve_js_path(rel, spec, graph)
            if target:
                out.append((target, "imports", f"javascript import {spec}"))

    return out


def _resolve_js_path(rel: str, spec: str, graph: RepositoryGraph) -> str | None:
    base = Path(rel).parent / spec
    candidates = [base]

    for suffix in (".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".vue", ".svelte", ".json"):
        candidates.append(Path(str(base) + suffix))

    candidates.extend(
        Path(str(base)) / f"index{suffix}" for suffix in (".ts", ".tsx", ".js", ".jsx")
    )

    for candidate in candidates:
        norm = candidate.as_posix()
        if norm in graph.files:
            return norm

    return None


def _go_imports(_rel: str, text: str, graph: RepositoryGraph) -> list[tuple[str, str, str]]:
    out: list[tuple[str, str, str]] = []

    for match in re.finditer(r"(?ms)\bimport\s*\((.*?)\)", text):
        for spec in re.findall(r'"([^"]+)"', match.group(1)):
            target = _resolve_generic_package(spec, graph)
            if target:
                out.append((target, "imports", f"go import {spec}"))

    for match in re.finditer(r'(?m)^\s*import\s+"([^"]+)"', text):
        target = _resolve_generic_package(match.group(1), graph)
        if target:
            out.append((target, "imports", f"go import {match.group(1)}"))

    return out


def _jvm_imports(_rel: str, text: str, graph: RepositoryGraph) -> list[tuple[str, str, str]]:
    out: list[tuple[str, str, str]] = []

    for match in re.finditer(r"(?m)^\s*import\s+([A-Za-z_][\w.]*)", text):
        spec = match.group(1)
        target = _resolve_generic_package(spec, graph)
        if target:
            out.append((target, "imports", f"JVM import {spec}"))

    return out


def _rust_imports(rel: str, text: str, graph: RepositoryGraph) -> list[tuple[str, str, str]]:
    out: list[tuple[str, str, str]] = []
    current_dir = Path(rel).parent

    for match in re.finditer(r"(?m)^\s*mod\s+([A-Za-z_][\w]*)\s*;", text):
        name = match.group(1)
        for candidate in (current_dir / f"{name}.rs", current_dir / name / "mod.rs"):
            if candidate.as_posix() in graph.files:
                out.append((candidate.as_posix(), "imports", f"rust mod {name}"))
                break

    for match in re.finditer(r"(?m)^\s*use\s+crate::([A-Za-z_][\w:]*)", text):
        target = _resolve_generic_package(match.group(1).replace("::", "."), graph)
        if target:
            out.append((target, "imports", f"rust use crate::{match.group(1)}"))

    return out


def _c_cpp_imports(rel: str, text: str, graph: RepositoryGraph) -> list[tuple[str, str, str]]:
    out: list[tuple[str, str, str]] = []
    current_dir = Path(rel).parent

    for match in re.finditer(r'(?m)^\s*#\s*include\s*["<]([^">]+)[">]', text):
        spec = match.group(1)
        for candidate in (current_dir / spec, Path(spec)):
            if candidate.as_posix() in graph.files:
                out.append((candidate.as_posix(), "imports", f"include {spec}"))
                break

    return out


def _resolve_generic_package(spec: str, graph: RepositoryGraph) -> str | None:
    spec = spec.strip()
    if not spec:
        return None

    direct = spec.replace(".", "/")

    for extension in (".java", ".kt", ".groovy", ".scala"):
        suffix = direct + extension
        for file in sorted(graph.files):
            if file.endswith(suffix):
                return file

    exact = f"{direct}/__init__.py"
    if exact in graph.files:
        return exact

    for file in sorted(graph.files):
        if file.startswith(direct + "/"):
            return file

    return None


__all__ = ["EdgeEvidence", "ImpactAssessmentEngine", "RepositoryGraph"]
