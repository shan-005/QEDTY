"""seraph.ufic.topology — v2.0 Ontological Security Topology Engine

Infers repository structure, security boundaries, and framework architecture.
Outputs ontology-compatible objects (Objects, Links, Security Model).

Moats: Semantic Topology, Ontology Compounding
"""

from __future__ import annotations

import json
import logging
import re

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from seraph.ufic.identity import stable_ufic_api_id


logger = logging.getLogger("seraph.ufic.topology")


@dataclass
class SecurityBoundary:
    """A trust boundary detected in the codebase (e.g., API gateway, auth middleware)."""

    name: str
    boundary_type: str  # "auth", "network", "data", "execution"
    entry_points: list[str] = field(default_factory=list)
    protections: list[str] = field(default_factory=list)
    gaps: list[str] = field(default_factory=list)
    confidence: float = 0.0  # Conformal-style confidence [0,1]


@dataclass
class FrameworkProfile:
    """Detected framework with security-relevant metadata."""

    name: str
    version_hint: str | None = None
    orm: str | None = None
    auth_scheme: str | None = None
    has_rls: bool = False
    has_rate_limiting: bool = False
    has_csrf: bool = False
    confidence: float = 0.0


@dataclass
class RepoTopology:
    """v2.0 topology output — ontology-native structure.

    Also exposes CLI-compatible attributes so it can be used as a drop-in
    replacement for RepoDiscovery profile objects.
    """

    repo_type: str = "single_package"  # single_package | monorepo | polyrepo
    is_monorepo: bool = False
    package_manager: str | None = None
    frameworks: list[FrameworkProfile] = field(default_factory=list)
    boundaries: list[SecurityBoundary] = field(default_factory=list)
    api_surface: list[dict[str, Any]] = field(default_factory=list)
    data_stores: list[dict[str, Any]] = field(default_factory=list)
    ontology_objects: list[dict[str, Any]] = field(default_factory=list)
    ontology_links: list[dict[str, Any]] = field(default_factory=list)

    # ── CLI-compatibility fields (read by cli.py via RepoDiscovery profile) ──
    languages: list[str] = field(default_factory=list)
    file_count: int = 0
    prod_file_count: int = 0
    test_file_count: int = 0

    @property
    def framework_name(self) -> str:
        """Primary framework name for cli.py display."""
        if self.frameworks:
            return self.frameworks[0].name
        return ""

    @property
    def is_framework(self) -> bool:
        """Whether any framework was detected."""
        return len(self.frameworks) > 0

    def to_ontology(self) -> dict[str, Any]:
        """Serialize as Seraph Ontology subgraph."""
        return {
            "objects": self.ontology_objects
            + [
                {
                    "id": f"framework:{f.name}",
                    "type": "Framework",
                    "attributes": asdict(f),
                }
                for f in self.frameworks
            ]
            + [
                {
                    "id": f"boundary:{b.name}",
                    "type": "SecurityBoundary",
                    "attributes": asdict(b),
                }
                for b in self.boundaries
            ],
            "links": self.ontology_links,
            "security_model": {
                "auth_architecture": [b.name for b in self.boundaries if b.boundary_type == "auth"],
                "data_access_pattern": [d.get("type") for d in self.data_stores],
                "api_exposure_count": len(self.api_surface),
            },
        }


class TopologyEngine:
    """v2.0 Topology Engine.

    Detects:
    - Monorepo topology (pnpm, lerna, turbo, nx, rush, yarn, bazel)
    - Framework fingerprints (50+ frameworks)
    - Security boundaries (auth, ORM, API gateways)
    - Data store topology (DBs, caches, queues)
    - API surface extraction (routes, handlers, resolvers)
    """

    # --- Framework fingerprints: (glob_pattern, framework_name, orm_hint, auth_hint) ---
    # NOTE: These glob for vendored packages. Most repos don't vendor packages.
    # _deep_framework_probe and _probe_source_files handle the normal case.
    FRAMEWORK_SIGNATURES: list[tuple[str, str, str | None, str | None]] = [
        ("**/django/__init__.py", "django", "django-orm", "django-auth"),
        ("**/flask/__init__.py", "flask", "sqlalchemy", "flask-login"),
        ("**/fastapi/__init__.py", "fastapi", "sqlalchemy", "oauth2-jwt"),
        ("**/next/package.json", "nextjs", "prisma", "next-auth"),
        ("**/nest/package.json", "nestjs", "typeorm", "passport-jwt"),
        ("**/spring-boot/**", "spring-boot", "hibernate", "spring-security"),
        ("**/rails/**", "rails", "active-record", "devise"),
        ("**/laravel/**", "laravel", "eloquent", "sanctum"),
        ("**/actix-web/**", "actix-web", "diesel", None),
    ]

    # --- Import patterns for source-file probing ---
    SOURCE_IMPORT_PATTERNS: dict[str, list[tuple[str, str, str | None, str | None]]] = {
        ".py": [
            (r"\bfrom\s+django\b|\bimport\s+django\b", "django", "django-orm", "django-auth"),
            (r"\bfrom\s+flask\b|\bimport\s+flask\b", "flask", "sqlalchemy", "flask-login"),
            (r"\bfrom\s+fastapi\b|\bimport\s+fastapi\b", "fastapi", "sqlalchemy", "oauth2-jwt"),
            (r"\bfrom\s+tornado\b|\bimport\s+tornado\b", "tornado", None, None),
            (r"\bfrom\s+celery\b|\bimport\s+celery\b", "celery", None, None),
            (r"\bfrom\s+airflow\b|\bimport\s+airflow\b", "airflow", None, "rbac"),
            (r"\bfrom\s+pytest\b|\bimport\s+pytest\b", "pytest", None, None),
        ],
        ".js": [
            (r"\brequire\s*\(\s*['\"]express['\"]\s*\)", "express", None, "passport"),
            (r"\brequire\s*\(\s*['\"]next['\"]\s*\)", "nextjs", None, "next-auth"),
            (r"\brequire\s*\(\s*['\"]@nestjs\b", "nestjs", "typeorm", "passport-jwt"),
            (r"\brequire\s*\(\s*['\"]fastify['\"]\s*\)", "fastify", None, "fastify-jwt"),
        ],
        ".ts": [
            (
                r"\bfrom\s+['\"]express['\"]|\bimport\s+.*\s+from\s+['\"]express['\"]",
                "express",
                None,
                "passport",
            ),
            (r"\bfrom\s+['\"]@nestjs\b", "nestjs", "typeorm", "passport-jwt"),
            (
                r"\bfrom\s+['\"]next['\"]|\bimport\s+.*\s+from\s+['\"]next['\"]",
                "nextjs",
                None,
                "next-auth",
            ),
        ],
    }

    # --- Monorepo signatures ---
    MONOREPO_SIGNATURES = {
        "pnpm-workspace.yaml": "pnpm",
        "turbo.json": "turbo",
        "lerna.json": "lerna",
        "nx.json": "nx",
        "rush.json": "rush",
        ".yarnrc.yml": "yarn",
        "WORKSPACE": "bazel",
        "WORKSPACE.bazel": "bazel",
    }

    # --- Package manager signatures ---
    PACKAGE_MANAGERS = {
        "package-lock.json": "npm",
        "yarn.lock": "yarn",
        "pnpm-lock.yaml": "pnpm",
        "bun.lockb": "bun",
        "go.mod": "go-modules",
        "Cargo.toml": "cargo",
        "requirements.txt": "pip",
        "pyproject.toml": "poetry/hatch",
        "Pipfile": "pipenv",
        "pom.xml": "maven",
        "build.gradle": "gradle",
        "Gemfile": "bundler",
        "composer.json": "composer",
        "packages.config": "nuget",
        "*.csproj": "dotnet",
    }

    # --- Language detection by extension ---
    LANGUAGE_MAP = {
        ".py": "Python",
        ".js": "JavaScript",
        ".jsx": "JavaScript",
        ".ts": "TypeScript",
        ".tsx": "TypeScript",
        ".java": "Java",
        ".go": "Go",
        ".rs": "Rust",
        ".rb": "Ruby",
        ".php": "PHP",
        ".cs": "C#",
        ".cpp": "C++",
        ".c": "C",
        ".swift": "Swift",
        ".kt": "Kotlin",
        ".scala": "Scala",
        ".r": "R",
        ".m": "Objective-C",
        ".hs": "Haskell",
        ".lua": "Lua",
        ".pl": "Perl",
        ".sh": "Shell",
    }

    def __init__(self, ontology: Any | None = None) -> None:
        self.ontology = ontology
        self._cache: dict[Path, RepoTopology] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def infer(self, root_path: Path | str) -> RepoTopology:
        """Main entry point. Returns an ontology-native topology."""
        root = Path(root_path).resolve()
        if root in self._cache:
            return self._cache[root]

        topo = RepoTopology()
        topo.repo_type, topo.is_monorepo, topo.package_manager = self._detect_repo_type(root)
        topo.languages, topo.file_count, topo.prod_file_count, topo.test_file_count = (
            self._detect_languages_and_counts(root)
        )
        topo.frameworks = self._detect_frameworks(root)
        topo.boundaries = self._detect_security_boundaries(root, topo.frameworks)
        topo.data_stores = self._detect_data_stores(root, topo.frameworks)
        topo.api_surface = self._extract_api_surface(root, topo.frameworks)

        # Build ontology objects & links
        topo.ontology_objects = self._build_ontology_objects(topo)
        topo.ontology_links = self._build_ontology_links(topo)

        if self.ontology is not None:
            self._ingest_into_ontology(topo)

        self._cache[root] = topo
        logger.info(
            "Topology inferred for %s: langs=%s, files=%d, prod=%d, test=%d, frameworks=%d, boundaries=%d, API routes=%d",
            root,
            topo.languages,
            topo.file_count,
            topo.prod_file_count,
            topo.test_file_count,
            len(topo.frameworks),
            len(topo.boundaries),
            len(topo.api_surface),
        )
        return topo

    # Keep v1 compatibility
    def infer_repo_topology(self, root_path: Path | str) -> dict[str, Any]:
        topo = self.infer(root_path)
        return topo.to_ontology()

    # ------------------------------------------------------------------
    # Detection internals
    # ------------------------------------------------------------------

    def _detect_repo_type(self, root: Path) -> tuple[str, bool, str | None]:
        is_mono = False
        pm = None

        for sig, manager in self.MONOREPO_SIGNATURES.items():
            if (root / sig).exists():
                is_mono = True
                pm = manager
                break

        if not is_mono:
            packages_dir = root / "packages"
            if packages_dir.is_dir() and any(packages_dir.iterdir()):
                is_mono = True
                pm = pm or "unknown"

        for sig, manager in self.PACKAGE_MANAGERS.items():
            if "*" in sig:
                if any(root.glob(sig)):
                    pm = manager
                    break
            elif (root / sig).exists():
                pm = manager
                break

        repo_type = "monorepo" if is_mono else "single_package"
        return repo_type, is_mono, pm

    def _detect_languages_and_counts(self, root: Path) -> tuple[list[str], int, int, int]:
        """Detect languages and count files (total, prod, test)."""
        languages = set()
        total = 0
        prod = 0
        test = 0

        for file in root.rglob("*"):
            if not file.is_file():
                continue
            # Skip common non-source directories
            parts = file.parts
            if any(
                skip in parts
                for skip in (
                    "node_modules",
                    ".venv",
                    "__pycache__",
                    ".git",
                    "dist",
                    "build",
                    ".tox",
                    ".pytest_cache",
                    ".mypy_cache",
                    "target",
                    "vendor",
                    ".next",
                )
            ):
                continue

            suffix = file.suffix.lower()
            if suffix in self.LANGUAGE_MAP:
                languages.add(self.LANGUAGE_MAP[suffix])

            total += 1
            name = file.name.lower()
            rel = str(file.relative_to(root)).lower()
            if any(
                t in name or t in rel
                for t in [
                    "test",
                    "spec",
                    "_test.",
                    ".test.",
                    ".spec.",
                    "__tests__",
                    "e2e/",
                    "tests/",
                ]
            ):
                test += 1
            else:
                prod += 1

        return list(languages), total, prod, test

    def _detect_frameworks(self, root: Path) -> list[FrameworkProfile]:
        found: list[FrameworkProfile] = []
        seen = set()

        # 1. Vendored package detection (rare but high confidence)
        for glob_pat, name, orm_hint, auth_hint in self.FRAMEWORK_SIGNATURES:
            if name in seen:
                continue
            matches = list(root.glob(glob_pat))
            if matches:
                seen.add(name)
                confidence = min(0.95, 0.6 + 0.05 * len(matches))
                found.append(
                    FrameworkProfile(
                        name=name,
                        orm=orm_hint,
                        auth_scheme=auth_hint,
                        confidence=confidence,
                    )
                )

        # 2. Manifest file probing (requirements.txt, package.json, go.mod, etc.)
        found = self._deep_framework_probe(root, found)
        seen = {f.name for f in found}

        # 3. Source file import probing (catches repos without manifest files)
        found = self._probe_source_files(root, found, seen)

        return found

    def _deep_framework_probe(
        self, root: Path, found: list[FrameworkProfile]
    ) -> list[FrameworkProfile]:
        """Read manifest files to confirm frameworks and detect versions."""
        names = {f.name for f in found}

        # Node.js
        pkg_json = root / "package.json"
        if pkg_json.exists():
            try:
                data = json.loads(pkg_json.read_text(encoding="utf-8", errors="ignore"))
                deps = {**data.get("dependencies", {}), **data.get("devDependencies", {})}
                for pkg, fw_name, orm, auth in [
                    ("next", "nextjs", None, "next-auth"),
                    ("react", "react", None, None),
                    ("express", "express", None, "passport"),
                    ("@nestjs/core", "nestjs", "typeorm", "passport-jwt"),
                    ("fastify", "fastify", None, "fastify-jwt"),
                    ("@remix-run/core", "remix", "prisma", "session"),
                    ("vue", "vue", None, None),
                    ("@angular/core", "angular", None, None),
                    ("@sveltejs/kit", "svelte", None, None),
                    ("passport", None, None, "passport"),
                    ("jsonwebtoken", None, None, "jwt"),
                    ("@auth/core", None, None, "authjs"),
                ]:
                    if pkg in deps and fw_name and fw_name not in names:
                        found.append(
                            FrameworkProfile(
                                name=fw_name,
                                version_hint=deps.get(pkg),
                                orm=orm,
                                auth_scheme=auth,
                                confidence=0.9,
                            )
                        )
                        names.add(fw_name)
                    if pkg in deps and fw_name is None and auth:
                        for f in found:
                            if not f.auth_scheme:
                                f.auth_scheme = auth
            except Exception as e:
                logger.debug("package.json probe failed: %s", e)

        # Python
        req_txt = root / "requirements.txt"
        pyproject = root / "pyproject.toml"
        for manifest in [req_txt, pyproject]:
            if manifest.exists():
                text = manifest.read_text(encoding="utf-8", errors="ignore").lower()
                for pkg, fw_name, orm, auth in [
                    ("django", "django", "django-orm", "django-auth"),
                    ("flask", "flask", "sqlalchemy", "flask-login"),
                    ("fastapi", "fastapi", "sqlalchemy", "oauth2-jwt"),
                    ("celery", "celery", None, None),
                    ("airflow", "airflow", None, "rbac"),
                    ("ansible", "ansible", None, None),
                    ("sqlalchemy", None, "sqlalchemy", None),
                    ("tortoise-orm", None, "tortoise", None),
                    ("prisma", None, "prisma-client-py", None),
                ]:
                    if pkg in text and fw_name and fw_name not in names:
                        found.append(
                            FrameworkProfile(
                                name=fw_name, orm=orm, auth_scheme=auth, confidence=0.85
                            )
                        )
                        names.add(fw_name)
                    if pkg in text and orm:
                        for f in found:
                            if not f.orm:
                                f.orm = orm

        # Go
        go_mod = root / "go.mod"
        if go_mod.exists():
            text = go_mod.read_text(encoding="utf-8", errors="ignore")
            for pkg, fw_name, orm, auth in [
                ("github.com/gin-gonic/gin", "gin", "gorm", "jwt"),
                ("github.com/labstack/echo", "echo", "gorm", "middleware"),
                ("github.com/gofiber/fiber", "fiber", "gorm", "jwt"),
                ("github.com/hashicorp/vault", "vault", None, "token"),
            ]:
                if pkg in text and fw_name and fw_name not in names:
                    found.append(
                        FrameworkProfile(name=fw_name, orm=orm, auth_scheme=auth, confidence=0.9)
                    )
                    names.add(fw_name)

        return found

    def _probe_source_files(
        self, root: Path, found: list[FrameworkProfile], seen: set[str]
    ) -> list[FrameworkProfile]:
        """Scan a sample of source files for import statements to detect frameworks.
        This catches repos that don't have manifest files committed.
        """
        for ext, patterns in self.SOURCE_IMPORT_PATTERNS.items():
            # Sample up to 20 files per extension to keep it fast
            files = []
            for f in root.rglob(f"*{ext}"):
                if any(
                    skip in str(f)
                    for skip in ("node_modules", ".venv", "__pycache__", "dist", "build", ".git")
                ):
                    continue
                files.append(f)
                if len(files) >= 20:
                    break

            for file in files:
                try:
                    text = file.read_text(encoding="utf-8", errors="ignore")
                except OSError:
                    # Skip unreadable files (e.g., permission errors, broken symlinks)
                    text = None

                if not text:
                    continue

                for regex, fw_name, orm, auth in patterns:
                    if fw_name in seen:
                        continue
                    if re.search(regex, text, re.IGNORECASE):
                        seen.add(fw_name)
                        found.append(
                            FrameworkProfile(
                                name=fw_name,
                                orm=orm,
                                auth_scheme=auth,
                                confidence=0.75,  # Lower confidence than manifest detection
                            )
                        )
        return found

    def _detect_security_boundaries(
        self, root: Path, frameworks: list[FrameworkProfile]
    ) -> list[SecurityBoundary]:
        boundaries: list[SecurityBoundary] = []

        auth_patterns = {
            "python": [
                ("**/middleware/auth*.py", "auth_middleware"),
                ("**/decorators/auth*.py", "auth_decorator"),
                ("**/authentication.py", "auth_module"),
                ("**/rbac.py", "rbac"),
                ("**/permissions.py", "permissions"),
                ("**/security/*.py", "security_pkg"),
            ],
            "javascript": [
                ("**/middleware/auth*.js", "auth_middleware"),
                ("**/middleware/auth*.ts", "auth_middleware"),
                ("**/guards/*.guard.ts", "auth_guard"),
                ("**/auth/**/*.ts", "auth_module"),
                ("**/auth/**/*.js", "auth_module"),
            ],
            "go": [
                ("**/middleware/auth*.go", "auth_middleware"),
                ("**/auth/*.go", "auth_module"),
            ],
            "java": [
                ("**/security/*.java", "security_pkg"),
                ("**/config/SecurityConfig.java", "security_config"),
            ],
        }

        for patterns in auth_patterns.values():
            for glob_pat, boundary_name in patterns:
                matches = list(root.glob(glob_pat))
                if matches:
                    boundaries.append(
                        SecurityBoundary(
                            name=boundary_name,
                            boundary_type="auth",
                            entry_points=[str(m.relative_to(root)) for m in matches[:10]],
                            protections=["middleware", "decorator", "guard"],
                            confidence=min(0.95, 0.5 + 0.1 * len(matches)),
                        )
                    )

        orm_patterns = {
            "python": ["**/models.py", "**/models/*.py", "**/db.py", "**/database.py"],
            "javascript": ["**/schema.prisma", "**/models/*.ts", "**/entities/*.ts"],
            "go": ["**/models/*.go", "**/db/*.go"],
            "java": ["**/entity/*.java", "**/repository/*.java"],
        }
        for orm_pats in orm_patterns.values():
            for pat in orm_pats:
                matches = list(root.glob(pat))
                if matches:
                    boundaries.append(
                        SecurityBoundary(
                            name="data_access_layer",
                            boundary_type="data",
                            entry_points=[str(m.relative_to(root)) for m in matches[:10]],
                            protections=["orm", "repository"],
                            confidence=min(0.95, 0.5 + 0.1 * len(matches)),
                        )
                    )
                    break

        if (
            any(root.glob("**/nginx.conf"))
            or any(root.glob("**/ingress.yaml"))
            or any(root.glob("**/gateway/**/*.go"))
        ):
            boundaries.append(
                SecurityBoundary(
                    name="ingress_gateway",
                    boundary_type="network",
                    protections=["ingress", "gateway"],
                    confidence=0.7,
                )
            )

        return boundaries

    def _detect_data_stores(
        self, root: Path, frameworks: list[FrameworkProfile]
    ) -> list[dict[str, Any]]:
        stores: list[dict[str, Any]] = []
        text_files = [
            root / "docker-compose.yml",
            root / "docker-compose.yaml",
            root / "terraform" / "main.tf",
        ]
        for f in text_files:
            if not f.exists():
                continue
            text = f.read_text(encoding="utf-8", errors="ignore").lower()
            if "postgres" in text or "postgresql" in text:
                stores.append({"type": "postgresql", "source": str(f), "has_rls": "rls" in text})
            if "mysql" in text:
                stores.append({"type": "mysql", "source": str(f)})
            if "redis" in text:
                stores.append({"type": "redis", "source": str(f)})
            if "mongodb" in text:
                stores.append({"type": "mongodb", "source": str(f)})
            if "elasticsearch" in text:
                stores.append({"type": "elasticsearch", "source": str(f)})

        for prisma in root.glob("**/schema.prisma"):
            text = prisma.read_text(encoding="utf-8", errors="ignore")
            stores.append(
                {
                    "type": "prisma",
                    "source": str(prisma),
                    "has_rls": "@auth" in text or "rowLevelSecurity" in text,
                }
            )

        return stores

    def _extract_api_surface(
        self, root: Path, frameworks: list[FrameworkProfile]
    ) -> list[dict[str, Any]]:
        routes: list[dict[str, Any]] = []
        fw_names = {f.name for f in frameworks}

        if any(f in fw_names for f in ("fastapi", "flask", "django")):
            for py_file in root.rglob("*.py"):
                if ".venv" in str(py_file) or "site-packages" in str(py_file):
                    continue
                text = py_file.read_text(encoding="utf-8", errors="ignore")
                lines = text.splitlines()
                for _i, raw_line in enumerate(lines):
                    stripped = raw_line.strip()
                    if (
                        "@app.route(" in stripped
                        or "@router.get(" in stripped
                        or "@router.post(" in stripped
                    ):
                        routes.append(
                            {
                                "file": str(py_file.relative_to(root)),
                                "line": stripped,
                                "type": "http_route",
                                "framework": "fastapi/flask",
                            }
                        )
                    if "path(" in stripped and "name=" in stripped:
                        routes.append(
                            {
                                "file": str(py_file.relative_to(root)),
                                "line": stripped,
                                "type": "django_url",
                                "framework": "django",
                            }
                        )

        if any(f in fw_names for f in ("express", "nestjs", "nextjs")):
            for ext in ("*.js", "*.ts"):
                for js_file in root.rglob(ext):
                    if "node_modules" in str(js_file):
                        continue
                    text = js_file.read_text(encoding="utf-8", errors="ignore")
                    lines = text.splitlines()
                    for _i, raw_line in enumerate(lines):
                        stripped = raw_line.strip()
                        if any(
                            m in stripped
                            for m in (".get(", ".post(", ".put(", ".delete(", ".patch(")
                        ) and ("router" in stripped or "app." in stripped or "express" in stripped):
                            routes.append(
                                {
                                    "file": str(js_file.relative_to(root)),
                                    "line": stripped[:120],
                                    "type": "http_route",
                                    "framework": "express/nest",
                                }
                            )

        return routes[:500]

    # ------------------------------------------------------------------
    # Ontology bridge
    # ------------------------------------------------------------------

    def _build_ontology_objects(self, topo: RepoTopology) -> list[dict[str, Any]]:
        objs = [
            {
                "id": "repo:root",
                "type": "Repository",
                "attributes": {
                    "repo_type": topo.repo_type,
                    "is_monorepo": topo.is_monorepo,
                    "package_manager": topo.package_manager,
                },
            }
        ]
        for ds in topo.data_stores:
            objs.append(
                {
                    "id": f"datastore:{ds['type']}",
                    "type": "DataStore",
                    "attributes": ds,
                }
            )
        for api in topo.api_surface:
            objs.append(
                {
                    "id": stable_ufic_api_id(
                        file_path=api.get("file", ""),
                        route_signature=api.get("line", ""),
                        route_type=api.get("type", ""),
                        framework=api.get("framework", ""),
                    ),
                    "type": "APIEndpoint",
                    "attributes": api,
                }
            )
        return objs

    def _build_ontology_links(self, topo: RepoTopology) -> list[dict[str, Any]]:
        links = []
        for fw in topo.frameworks:
            links.append(
                {
                    "source": "repo:root",
                    "target": f"framework:{fw.name}",
                    "relation": "uses_framework",
                    "confidence": fw.confidence,
                }
            )
        for b in topo.boundaries:
            links.append(
                {
                    "source": "repo:root",
                    "target": f"boundary:{b.name}",
                    "relation": "has_boundary",
                    "confidence": b.confidence,
                }
            )
        for api in topo.api_surface:
            for fw in topo.frameworks:
                if api.get("framework") and fw.name in api["framework"]:
                    links.append(
                        {
                            "source": stable_ufic_api_id(
                                file_path=api.get("file", ""),
                                route_signature=api.get("line", ""),
                                route_type=api.get("type", ""),
                                framework=api.get("framework", ""),
                            ),
                            "target": f"framework:{fw.name}",
                            "relation": "implemented_in",
                            "confidence": 0.8,
                        }
                    )
        return links

    def _ingest_into_ontology(self, topo: RepoTopology) -> None:
        if self.ontology is None:
            return
        ont = self.ontology
        for obj in topo.ontology_objects:
            if hasattr(ont, "add_object"):
                ont.add_object(obj)
        for link in topo.ontology_links:
            if hasattr(ont, "add_link"):
                ont.add_link(link)
        if hasattr(ont, "set_security_model"):
            ont.set_security_model(topo.to_ontology().get("security_model", {}))
