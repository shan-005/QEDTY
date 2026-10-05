"""seraph.intelligence.ufic.classifier — v2.0.1 Ontology-Driven UFIC Classifier

Fixes in v2.0.1:
- Critical/high/secret findings now bypass ALL intent-based suppression.
- OmissionDetector caps raised for real-world repos.
- evaluate_finding checks severity BEFORE intent classification.
- OmissionDetector safely ignores directories whose names match file globs.
"""

from __future__ import annotations

import json
import logging
import re

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from seraph.intelligence.ufic.identity import stable_ufic_object_id


logger = logging.getLogger("seraph.intelligence.ufic.classifier")


@dataclass
class ClassificationResult:
    should_suppress: bool = False
    intent: str = "production"
    language: str = "unknown"
    blast_radius_multiplier: float = 1.0
    confidence_interval: tuple[float, float] = (0.0, 1.0)
    reason: str = ""
    causal_impact: dict[str, Any] = field(default_factory=dict)
    recommended_action: str = "none"
    ontology_objects: list[dict[str, Any]] = field(default_factory=list)
    ontology_links: list[dict[str, Any]] = field(default_factory=list)


DEFAULT_FRAMEWORK_RULES: dict[str, dict[str, Any]] = {
    # Framework metadata is descriptive/contextual. It must never silently convert
    # one language into another or apply unrelated test/build paths.
    "vault": {
        "display_name": "Go Application",
        "safe_patterns": [],
        "framework_paths": ["builtin/", "command/", "physical/", "plugins/"],
        "rule_suppressions": {
            "hardcoded_password": {
                "frameworks": ["vault"],
                "paths": ["builtin/credential/", "builtin/logical/database/"],
            },
        },
    },
    "airflow": {
        "display_name": "Python Workflow Platform",
        "safe_patterns": [],
        "framework_paths": [
            "airflow-core/src/airflow/",
            "providers/",
            "tests/",
            "examples/",
            "devenv/",
        ],
        "rule_suppressions": {
            "eval": {
                "frameworks": ["airflow"],
                "paths": ["airflow-core/src/airflow/policies.py"],
            },
            "exec": {
                "frameworks": ["airflow"],
                "paths": ["airflow-core/src/airflow/"],
            },
            "hardcoded_password": {
                "frameworks": ["airflow"],
                "paths": ["airflow/", "providers/"],
            },
        },
    },
    "nextjs": {
        "display_name": "JavaScript/TypeScript Web Framework",
        "safe_patterns": [],
        "framework_paths": ["app/", "pages/", "src/", "test/", "tests/"],
    },
    "react": {
        "display_name": "JavaScript UI Library",
        "safe_patterns": [],
        "framework_paths": ["src/", "test/", "tests/", "examples/"],
    },
    "go": {
        "display_name": "Go Application",
        "safe_patterns": [],
        "framework_paths": ["cmd/", "pkg/", "internal/", "test/", "tests/"],
    },
    "java": {
        "display_name": "Java Application",
        "safe_patterns": [],
        "framework_paths": ["src/main/", "src/test/", "test/", "tests/"],
    },
    "ruby": {
        "display_name": "Ruby Application",
        "safe_patterns": [],
        "framework_paths": ["app/", "lib/", "test/", "spec/", "examples/"],
    },
    "rust": {
        "display_name": "Rust Application",
        "safe_patterns": [],
        "framework_paths": ["src/", "tests/", "examples/"],
    },
}

DEFAULT_GLOBAL_SUPPRESSIONS: list[dict[str, Any]] = [
    {
        "rule_id": "dangerous_import",
        "title_contains": "__import__",
        "path_contains": "__init__.py",
        "action": "suppress",
    },
    {
        "language": "javascript",
        "title_contains": "exec",
        "path_contains_any": ["/ui/", "/src/utils/", "/src/components/", "/rules/"],
        "action": "suppress",
    },
    {"language": "javascript", "title_contains": "child_process", "action": "suppress"},
    {
        "language": "python",
        "title_contains": "os.system",
        "path_contains": "example_dag",
        "action": "suppress",
    },
    {
        "title_contains": "dockerfile",
        "path_contains_any": ["docker-stack-docs/", "docker-examples/", "providers/"],
        "action": "suppress",
    },
]

DEFAULT_INTENT_PATTERNS: dict[str, list[str]] = {
    "test": ["/test", "_test.", "testing.", ".spec.", ".stories.", "storybook"],
    "documentation": ["/docs/", ".rst", "/examples/", "/readme"],
    "ci_script": ["/scripts/ci/", "/scripts/in_container/", ".github/workflows/"],
    "dev_tooling": ["/dev/breeze/", "/enos/", "/dev/", "/tooling/"],
    "mock_frontend": ["/mirage/", "/registry/src/js/", "/mock/"],
    "generated": [".gen.", "/generated/", "/gen/", "/dist/"],
    "config": [".env", "/.release/", "/config/", ".yaml", ".yml"],
    "non_production": ["/fixtures/", "/stubs/", "/fakes/", "/samples/"],
}


class RuleRegistry:
    def __init__(
        self,
        framework_rules: dict[str, dict[str, Any]] | None = None,
        global_suppressions: list[dict[str, Any]] | None = None,
        intent_patterns: dict[str, list[str]] | None = None,
        ontology: Any | None = None,
    ) -> None:
        self.framework_rules = framework_rules or DEFAULT_FRAMEWORK_RULES
        self.global_suppressions = global_suppressions or DEFAULT_GLOBAL_SUPPRESSIONS
        self.intent_patterns = intent_patterns or DEFAULT_INTENT_PATTERNS
        self.ontology = ontology
        self._compiled: dict[str, list[re.Pattern[str]]] = {}
        self._compile_patterns()

    def _compile_patterns(self) -> None:
        for intent, patterns in self.intent_patterns.items():
            self._compiled[intent] = [re.compile(p, re.IGNORECASE) for p in patterns]

    def reload_from_ontology(self) -> None:
        if self.ontology is None:
            return
        if hasattr(self.ontology, "get_ufic_rules"):
            rules = self.ontology.get_ufic_rules()
            self.framework_rules = rules.get("framework_rules", self.framework_rules)
            self.global_suppressions = rules.get("global_suppressions", self.global_suppressions)
            self.intent_patterns = rules.get("intent_patterns", self.intent_patterns)
            self._compile_patterns()

    def match_framework_suppression(
        self, framework: str, rule_id: str, file_path: str
    ) -> dict[str, Any] | None:
        fw_rules = self.framework_rules.get(framework, {})
        sup_map = fw_rules.get("rule_suppressions", {})
        if rule_id not in sup_map:
            return None
        sup = sup_map[rule_id]
        frameworks = sup.get("frameworks", [])
        paths = sup.get("paths", [])
        if framework not in frameworks and "*" not in frameworks:
            return None
        if any(p in file_path for p in paths):
            return {"action": "suppress", "reason": f"Framework rule: {framework}/{rule_id}"}
        return None

    def match_global_suppression(
        self, rule_id: str, title: str, language: str, file_path: str
    ) -> dict[str, Any] | None:
        for rule in self.global_suppressions:
            match = True
            if "rule_id" in rule and rule["rule_id"] != rule_id:
                match = False
            if "title_contains" in rule and rule["title_contains"].lower() not in title.lower():
                match = False
            if "language" in rule and rule["language"] != language:
                match = False
            if "path_contains" in rule and rule["path_contains"] not in file_path:
                match = False
            if "path_contains_any" in rule and not any(
                p in file_path for p in rule["path_contains_any"]
            ):
                match = False
            if match:
                return {"action": rule.get("action", "suppress"), "reason": f"Global rule: {rule}"}
        return None


class FileClassifier:
    LANGUAGE_MAP: dict[str, str] = {
        ".py": "python",
        ".js": "javascript",
        ".ts": "typescript",
        ".tsx": "typescript",
        ".go": "go",
        ".java": "java",
        ".kt": "kotlin",
        ".yaml": "yaml",
        ".yml": "yaml",
        ".tf": "terraform",
        ".json": "json",
        ".md": "markdown",
        ".rst": "markdown",
        ".rb": "ruby",
        ".php": "php",
        ".rs": "rust",
        ".cs": "csharp",
        ".cpp": "cpp",
        ".c": "c",
        ".h": "c",
        ".swift": "swift",
        ".dart": "dart",
        ".lua": "lua",
        ".zig": "zig",
        ".nim": "nim",
        ".ex": "elixir",
        ".exs": "elixir",
        ".erl": "erlang",
        ".hrl": "erlang",
        ".r": "r",
        ".pl": "perl",
        ".pm": "perl",
    }

    def __init__(self, registry: RuleRegistry) -> None:
        self.registry = registry
        self._intent_cache: dict[str, str] = {}

    def detect_language(self, file_path: str) -> str:
        ext = Path(file_path).suffix.lower()
        return self.LANGUAGE_MAP.get(ext, "unknown")

    def get_file_intent(self, filepath: Path | str) -> str:
        key = str(filepath)
        if key in self._intent_cache:
            return self._intent_cache[key]

        rel_path = self._normalize_path(filepath)
        intent = "production"

        for intent_name, patterns in self.registry.intent_patterns.items():
            for pat in patterns:
                if pat in rel_path or re.search(pat, rel_path, re.IGNORECASE):
                    intent = intent_name
                    break
            if intent != "production":
                break

        self._intent_cache[key] = intent
        return intent

    @staticmethod
    def _normalize_path(filepath: Path | str) -> str:
        return Path(filepath).as_posix().lower()


class OmissionDetector:
    def __init__(self, topology: dict[str, Any] | None = None, ontology: Any | None = None) -> None:
        self.topology = topology or {}
        self.ontology = ontology

    @staticmethod
    def _safe_read_text(path: Path) -> str | None:
        """Read a file defensively.

        Returns None when the path is missing, is a directory, or cannot be read.
        This prevents IsADirectoryError when glob patterns match directories whose
        names resemble source files, for example a directory named ``fake.py``.
        """
        try:
            if not path.is_file():
                return None
        except OSError:
            return None

        try:
            return path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            return None

    def scan(self, root_path: Path | str) -> list[dict[str, Any]]:
        root = Path(root_path)
        omissions: list[dict[str, Any]] = []
        omissions.extend(self._detect_missing_auth(root))
        omissions.extend(self._detect_missing_rls(root))
        omissions.extend(self._detect_missing_rate_limiting(root))
        omissions.extend(self._detect_missing_csrf(root))
        omissions.extend(self._detect_missing_validation(root))
        omissions.extend(self._detect_missing_security_headers(root))
        omissions.extend(self._detect_hallucinated_deps(root))
        if self.ontology is not None:
            self._write_omissions_to_ontology(omissions)
        return omissions

    def _detect_missing_auth(self, root: Path) -> list[dict[str, Any]]:
        findings = []
        auth_decorators = re.compile(
            r"@(require_auth|login_required|authenticated|jwt_required|auth_required|protect|authorize|roles_allowed|permission_required|pre_authorize|has_authority)",
            re.IGNORECASE,
        )
        auth_middleware = re.compile(
            r"(auth_middleware|authenticate|verify_token|check_auth|ensure_auth)",
            re.IGNORECASE,
        )

        for py_file in root.rglob("*.py"):
            if self._skip_path(py_file):
                continue
            text = self._safe_read_text(py_file)
            if text is None:
                continue
            lines = text.splitlines()
            for i, line in enumerate(lines):
                stripped = line.strip()
                is_route = any(
                    k in stripped
                    for k in ("@app.route", "@router.get", "@router.post", "@api_view", "@action")
                )
                if not is_route:
                    continue
                snippet = "\n".join(lines[i : i + 12])
                has_auth = bool(auth_decorators.search(snippet) or auth_middleware.search(snippet))
                if not has_auth:
                    findings.append(
                        {
                            "rule_id": "missing_auth",
                            "title": "Missing Authentication on API Endpoint",
                            "file": str(py_file.relative_to(root)),
                            "line": i + 1,
                            "snippet": stripped[:120],
                            "severity": "critical",
                            "confidence_interval": (0.65, 0.95),
                            "reason": "API route defined without auth decorator or middleware",
                            "omission_type": "absence_of_control",
                            "blast_radius_multiplier": 1.3,
                        }
                    )

        for ext in ("*.js", "*.ts"):
            for js_file in root.rglob(ext):
                if self._skip_path(js_file):
                    continue
                text = self._safe_read_text(js_file)
                if text is None:
                    continue
                lines = text.splitlines()
                for i, line in enumerate(lines):
                    stripped = line.strip()
                    is_route = any(
                        k in stripped
                        for k in (".get('", ".post('", ".put('", ".delete('", ".patch('")
                    )
                    if not is_route or ("router" not in stripped and "app." not in stripped):
                        continue
                    snippet = "\n".join(lines[i : i + 12])
                    has_auth = bool(
                        auth_middleware.search(snippet)
                        or "passport" in snippet
                        or "jwt" in snippet
                        or "auth" in snippet
                    )
                    if not has_auth:
                        findings.append(
                            {
                                "rule_id": "missing_auth",
                                "title": "Missing Authentication on API Endpoint",
                                "file": str(js_file.relative_to(root)),
                                "line": i + 1,
                                "snippet": stripped[:120],
                                "severity": "critical",
                                "confidence_interval": (0.60, 0.92),
                                "reason": "Express/Nest route without auth middleware",
                                "omission_type": "absence_of_control",
                                "blast_radius_multiplier": 1.3,
                            }
                        )

        return findings[:500]  # v2.0.1: raised cap

    def _detect_missing_rls(self, root: Path) -> list[dict[str, Any]]:
        findings = []
        rls_keywords = re.compile(
            r"(row_level_security|rls|tenant_id|organization_id|user_id\s*=|current_user|auth\.uid)",
            re.IGNORECASE,
        )
        orm_patterns = re.compile(
            r"(sqlalchemy|django\.db|prisma|typeorm|sequelize|gorm|hibernate)", re.IGNORECASE
        )

        for py_file in root.rglob("*.py"):
            if self._skip_path(py_file):
                continue
            text = self._safe_read_text(py_file)
            if text is None:
                continue
            if not orm_patterns.search(text):
                continue
            has_queries = "SELECT " in text or ".query(" in text or "execute(" in text
            has_rls = rls_keywords.search(text)
            if (
                has_queries
                and not has_rls
                and any(k in str(py_file) for k in ("model", "query", "db", "repository", "dao"))
            ):
                findings.append(
                    {
                        "rule_id": "missing_rls",
                        "title": "Missing Row-Level Security on Data Access",
                        "file": str(py_file.relative_to(root)),
                        "severity": "high",
                        "confidence_interval": (0.50, 0.85),
                        "reason": "Database queries without RLS or tenant isolation pattern",
                        "omission_type": "absence_of_control",
                        "blast_radius_multiplier": 1.2,
                    }
                )

        for prisma in root.glob("**/schema.prisma"):
            if self._skip_path(prisma):
                continue
            text = self._safe_read_text(prisma)
            if text is None:
                continue
            if (
                "@auth" not in text
                and "rowLevelSecurity" not in text
                and "tenant" not in text.lower()
            ):
                findings.append(
                    {
                        "rule_id": "missing_rls",
                        "title": "Prisma Schema Lacks RLS / Tenant Isolation",
                        "file": str(prisma.relative_to(root)),
                        "severity": "high",
                        "confidence_interval": (0.55, 0.88),
                        "reason": "Prisma schema has no RLS or multi-tenant directives",
                        "omission_type": "absence_of_control",
                        "blast_radius_multiplier": 1.2,
                    }
                )

        return findings

    def _detect_missing_rate_limiting(self, root: Path) -> list[dict[str, Any]]:
        findings = []
        rate_limit_keywords = re.compile(
            r"(rate_limit|throttle|@RateLimit|express-rate-limit|slowdown|bucket4j|redis\.throttle)",
            re.IGNORECASE,
        )
        for py_file in root.rglob("*.py"):
            if self._skip_path(py_file):
                continue
            text = self._safe_read_text(py_file)
            if text is None:
                continue
            if "@app.route" not in text and "@router" not in text:
                continue
            if not rate_limit_keywords.search(text):
                findings.append(
                    {
                        "rule_id": "missing_rate_limiting",
                        "title": "Missing Rate Limiting on Public API",
                        "file": str(py_file.relative_to(root)),
                        "severity": "medium",
                        "confidence_interval": (0.40, 0.75),
                        "reason": "Route file has no rate limiting decorators or middleware",
                        "omission_type": "absence_of_control",
                        "blast_radius_multiplier": 1.1,
                    }
                )
        return findings[:100]

    def _detect_missing_csrf(self, root: Path) -> list[dict[str, Any]]:
        findings = []
        csrf_keywords = re.compile(
            r"(csrf|@csrf_exempt|CsrfViewMiddleware|csrf_protect|csrf_token)", re.IGNORECASE
        )
        for py_file in root.rglob("*.py"):
            if self._skip_path(py_file):
                continue
            text = self._safe_read_text(py_file)
            if text is None:
                continue
            has_post = "@app.route" in text and "methods=['POST']" in text
            has_form = "request.form" in text or "request.POST" in text
            if (has_post or has_form) and not csrf_keywords.search(text):
                findings.append(
                    {
                        "rule_id": "missing_csrf",
                        "title": "Missing CSRF Protection on Form Handler",
                        "file": str(py_file.relative_to(root)),
                        "severity": "high",
                        "confidence_interval": (0.45, 0.80),
                        "reason": "POST/form handler without CSRF token or middleware",
                        "omission_type": "absence_of_control",
                        "blast_radius_multiplier": 1.15,
                    }
                )
        return findings[:100]

    def _detect_missing_validation(self, root: Path) -> list[dict[str, Any]]:
        findings = []
        validation_keywords = re.compile(
            r"(pydantic|@validate|schema|validator|zod|joi|yup|class-validator|@NotNull|@Valid|assert\s|raise\s.*Error)",
            re.IGNORECASE,
        )
        for py_file in root.rglob("*.py"):
            if self._skip_path(py_file):
                continue
            text = self._safe_read_text(py_file)
            if text is None:
                continue
            has_request = "request.json" in text or "request.get_json" in text or "Body(" in text
            if has_request and not validation_keywords.search(text):
                findings.append(
                    {
                        "rule_id": "missing_input_validation",
                        "title": "Missing Input Validation on User-Facing Endpoint",
                        "file": str(py_file.relative_to(root)),
                        "severity": "high",
                        "confidence_interval": (0.50, 0.82),
                        "reason": "Endpoint accepts user input without validation schema",
                        "omission_type": "absence_of_control",
                        "blast_radius_multiplier": 1.2,
                    }
                )
        return findings[:200]

    def _detect_missing_security_headers(self, root: Path) -> list[dict[str, Any]]:
        findings = []
        header_keywords = re.compile(
            r"(X-Frame-Options|Content-Security-Policy|X-Content-Type-Options|Strict-Transport-Security|Referrer-Policy|Permissions-Policy)",
            re.IGNORECASE,
        )
        for cfg in root.rglob("nginx.conf"):
            if self._skip_path(cfg):
                continue
            text = self._safe_read_text(cfg)
            if text is None:
                continue
            if not header_keywords.search(text):
                findings.append(
                    {
                        "rule_id": "missing_security_headers",
                        "title": "Nginx Config Missing Security Headers",
                        "file": str(cfg.relative_to(root)),
                        "severity": "medium",
                        "confidence_interval": (0.55, 0.85),
                        "reason": "No CSP, HSTS, or X-Frame-Options headers configured",
                        "omission_type": "absence_of_control",
                        "blast_radius_multiplier": 1.05,
                    }
                )
        return findings

    def _detect_hallucinated_deps(self, root: Path) -> list[dict[str, Any]]:
        findings = []
        pkg_json = root / "package.json"
        pkg_text = self._safe_read_text(pkg_json)
        if pkg_text is not None:
            try:
                data = json.loads(pkg_text)
                raw_deps = data.get("dependencies", {})
                deps = list(raw_deps.keys()) if isinstance(raw_deps, dict) else []
                all_imports = set()
                for js_file in root.rglob("*.js"):
                    if self._skip_path(js_file):
                        continue
                    text = self._safe_read_text(js_file)
                    if text is None:
                        continue
                    for line in text.splitlines():
                        if "require(" in line or "import " in line:
                            all_imports.update(re.findall(r"""["']([@\w\-/]+)["']""", line))
                for dep in deps:
                    base = dep.split("/")[0] if "/" in dep else dep
                    if base not in all_imports and not base.startswith("@types/"):
                        findings.append(
                            {
                                "rule_id": "hallucinated_dependency",
                                "title": f"Potentially Unused Dependency: {dep}",
                                "file": "package.json",
                                "severity": "low",
                                "confidence_interval": (0.30, 0.70),
                                "reason": f"{dep} declared but never imported in JS/TS source",
                                "omission_type": "unused_asset",
                                "blast_radius_multiplier": 0.8,
                            }
                        )
            except Exception as e:
                logger.debug("Hallucination scan failed for package.json: %s", e)
        return findings[:50]

    def _skip_path(self, path: Path) -> bool:
        """Skip non-files and known dependency/build/cache directories.

        This is important because glob patterns such as ``*.py`` can match
        directories, for example a directory named ``fake.py``.
        """
        try:
            if not path.is_file():
                return True
        except OSError:
            return True

        s = path.as_posix().lower()
        return any(
            k in s
            for k in (
                "node_modules",
                ".venv",
                "site-packages",
                "dist",
                "build",
                ".git",
                ".pytest_cache",
                ".mypy_cache",
                ".ruff_cache",
                ".seraph-cache",
                ".seraph-learn",
            )
        )

    def _write_omissions_to_ontology(self, omissions: list[dict[str, Any]]) -> None:
        if self.ontology is None:
            return
        ont = self.ontology
        for om in omissions:
            obj = {
                "id": stable_ufic_object_id(
                    rule_id=om.get("rule_id", ""),
                    file_path=om.get("file", ""),
                    line=om.get("line", 0),
                    column=om.get("column", 0),
                ),
                "type": "OmissionFinding",
                "attributes": om,
            }
            if hasattr(ont, "add_object"):
                ont.add_object(obj)
            if hasattr(ont, "add_link"):
                ont.add_link(
                    {
                        "source": "repo:root",
                        "target": obj["id"],
                        "relation": "has_omission",
                        "confidence": om.get("confidence_interval", [0.0, 1.0])[1],
                    }
                )


class UFICClassifier:
    """v2.0.1 Ontology-Driven UFIC Classifier."""

    def __init__(
        self,
        topology: dict[str, Any] | None = None,
        ontology: Any | None = None,
        registry: RuleRegistry | None = None,
    ) -> None:
        self.topology = topology or {}
        self.ontology = ontology
        self.registry = registry or RuleRegistry(ontology=ontology)
        self.file_classifier = FileClassifier(self.registry)
        self.omission_detector = OmissionDetector(topology=topology, ontology=ontology)

    def should_skip_file(self, filepath: Path | str) -> bool:
        rel_path = self.file_classifier._normalize_path(filepath)
        if self.ontology is not None and hasattr(self.ontology, "get_skip_patterns"):
            for pat in self.ontology.get_skip_patterns():
                if re.search(pat, rel_path):
                    return True
        return any(
            k in rel_path for k in ("node_modules", ".venv", "site-packages", "dist/", "build/")
        )

    def get_file_intent(self, filepath: Path | str) -> str:
        return self.file_classifier.get_file_intent(filepath)

    def evaluate_finding(self, finding: Any) -> ClassificationResult:
        """v2.0.1: Main finding evaluation with severity-first logic."""
        result = ClassificationResult()

        file_path = getattr(finding, "file_path", "") or getattr(finding, "file", "")
        rule_id = getattr(finding, "rule_id", "")
        title = getattr(finding, "title", "")
        severity = str(getattr(finding, "severity", "")).lower()
        rel_path = self.file_classifier._normalize_path(file_path)
        intent = self.file_classifier.get_file_intent(file_path)
        language = self.file_classifier.detect_language(file_path)
        framework = self.topology.get("framework_guess", "")

        result.intent = intent
        result.language = language

        # v2.0.1 FIX: Severity-first exception — NEVER suppress critical/high/secret
        is_secret = any(
            kw in str(rule_id).lower()
            for kw in (
                "secret",
                "password",
                "token",
                "api_key",
                "apikey",
                "credential",
                "private_key",
                "privatekey",
                "hardcoded",
                "jwt",
                "bearer",
                "auth",
            )
        ) or any(
            kw in str(title).lower()
            for kw in (
                "secret",
                "password",
                "token",
                "api key",
                "credential",
                "private key",
                "hardcoded",
            )
        )

        if severity in ("critical", "high") or is_secret:
            result.should_suppress = False
            result.blast_radius_multiplier = 1.0 if severity == "critical" else 0.9
            result.reason = (
                f"{severity.upper() if severity else 'SEVERE'}/secret finding — production impact"
            )
            result.confidence_interval = (0.88, 1.0)
            result.recommended_action = "escalate"
            return result

        # 1. Intent-based suppression (test, docs, generated, etc.)
        if intent in (
            "test",
            "documentation",
            "ci_script",
            "dev_tooling",
            "mock_frontend",
            "generated",
            "config",
            "non_production",
        ):
            result.should_suppress = True
            result.blast_radius_multiplier = 0.05
            result.reason = f"Non-production intent: {intent}"
            result.confidence_interval = (0.80, 0.99)
            result.recommended_action = "suppress"
            return result

        # 2. Framework-specific rule suppression
        if framework:
            fw_match = self.registry.match_framework_suppression(framework, rule_id, rel_path)
            if fw_match:
                result.should_suppress = True
                result.blast_radius_multiplier = 0.0
                result.reason = fw_match["reason"]
                result.confidence_interval = (0.85, 0.99)
                result.recommended_action = "suppress"
                return result

        # 3. Global suppression rules
        global_match = self.registry.match_global_suppression(rule_id, title, language, rel_path)
        if global_match:
            result.should_suppress = global_match["action"] == "suppress"
            result.blast_radius_multiplier = 0.0 if result.should_suppress else 0.3
            result.reason = global_match["reason"]
            result.confidence_interval = (0.75, 0.98)
            result.recommended_action = global_match["action"]
            return result

        # 4. Default: pass through with production intent
        result.should_suppress = False
        result.blast_radius_multiplier = 1.0
        result.reason = "Production code — no suppression rule matched"
        result.confidence_interval = (0.50, 0.90)
        result.recommended_action = "none"
        return result

    def detect_omissions(self, root_path: Path | str) -> list[dict[str, Any]]:
        return self.omission_detector.scan(root_path)

    def classify_batch(
        self, findings: list[Any], root_path: Path | str | None = None
    ) -> list[ClassificationResult]:
        results = [self.evaluate_finding(f) for f in findings]
        if root_path is not None:
            omissions = self.detect_omissions(root_path)
            for om in omissions:
                results.append(
                    ClassificationResult(
                        should_suppress=False,
                        intent="production",
                        language="unknown",
                        blast_radius_multiplier=om.get("blast_radius_multiplier", 1.2),
                        confidence_interval=om.get("confidence_interval", (0.50, 0.85)),
                        reason=om.get("reason", ""),
                        causal_impact={"omission_type": om.get("omission_type", "")},
                        recommended_action="escalate",
                    )
                )
        return results
