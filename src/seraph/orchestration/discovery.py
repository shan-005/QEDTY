"""seraph/core/discovery.py — Repository Discovery & Profiling Engine (v2.0.1)

Analyzes the filesystem to detect languages, frameworks, monorepos, and
container rootfs artifacts — then feeds everything into the Seraph Ontology.

v2.0.1 Fixes:
- Language detection threshold fixed for small repos (was requiring 3+ files).
- Framework detection now falls back to language-only for repos with source files.
- Empty language list no longer possible if source files exist.
"""

from __future__ import annotations

import json
import logging
import os
import re

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from seraph.sources.repository.scanners.base import (
    OntologyLink,
    OntologyObject,
    OntologyType,
)


logger = logging.getLogger(__name__)


@dataclass
class RepoProfile:
    root: str = ""
    is_git_repo: bool = False
    file_count: int = 0
    prod_file_count: int = 0
    test_file_count: int = 0
    non_prod_file_count: int = 0
    total_size_bytes: int = 0
    languages: list[str] = field(default_factory=list)
    frameworks: list[str] = field(default_factory=list)
    is_framework: bool = False
    framework_name: str = ""
    framework_key: str = ""
    safe_patterns: list[tuple[str, str]] = field(default_factory=list)
    framework_paths: list[str] = field(default_factory=list)
    is_monorepo: bool = False
    monorepo_tool: str = ""
    is_container_rootfs: bool = False
    binary_paths: list[str] = field(default_factory=list)
    embedded_scripts: list[str] = field(default_factory=list)
    env_vars: list[str] = field(default_factory=list)
    has_dockerfile: bool = False
    has_docker_compose: bool = False
    has_kubernetes: bool = False
    has_helm: bool = False
    has_terraform: bool = False
    has_github_actions: bool = False
    services: list[dict[str, Any]] = field(default_factory=list)
    has_auth_config: bool = False
    has_rls_config: bool = False
    auth_boundaries: list[dict[str, Any]] = field(default_factory=list)
    missing_auth_patterns: list[str] = field(default_factory=list)

    @property
    def resolved_path(self) -> Path:
        return Path(self.root)

    def is_framework_safe_pattern(self, pattern: str, file_path: str) -> bool:
        if not self.safe_patterns:
            return False
        return any(
            pattern == safe_pattern and safe_path in file_path
            for safe_pattern, safe_path in self.safe_patterns
        )

    def is_framework_path(self, file_path: str) -> bool:
        if not self.framework_paths:
            return False
        return any(fp in file_path for fp in self.framework_paths)

    def to_ontology_objects(self) -> list[OntologyObject]:
        objects: list[OntologyObject] = []
        objects.append(
            OntologyObject(
                type=OntologyType.FILE,
                name="repository_root",
                path=self.root,
                properties={
                    "is_git_repo": self.is_git_repo,
                    "is_monorepo": self.is_monorepo,
                    "monorepo_tool": self.monorepo_tool,
                    "is_container_rootfs": self.is_container_rootfs,
                    "file_count": self.file_count,
                    "prod_file_count": self.prod_file_count,
                    "test_file_count": self.test_file_count,
                    "total_size_bytes": self.total_size_bytes,
                    "languages": self.languages,
                    "frameworks": self.frameworks,
                    "has_dockerfile": self.has_dockerfile,
                    "has_docker_compose": self.has_docker_compose,
                    "has_kubernetes": self.has_kubernetes,
                    "has_helm": self.has_helm,
                    "has_terraform": self.has_terraform,
                    "has_github_actions": self.has_github_actions,
                    "has_auth_config": self.has_auth_config,
                    "has_rls_config": self.has_rls_config,
                },
                scanner="RepoDiscovery",
                confidence=1.0,
            )
        )
        for lang in self.languages:
            objects.append(
                OntologyObject(
                    type=OntologyType.FILE,
                    name=f"lang:{lang}",
                    path=self.root,
                    properties={"language": lang, "category": "language"},
                    scanner="RepoDiscovery",
                    confidence=1.0,
                )
            )
        if self.framework_name:
            objects.append(
                OntologyObject(
                    type=OntologyType.FILE,
                    name=f"framework:{self.framework_name}",
                    path=self.root,
                    properties={
                        "framework_name": self.framework_name,
                        "framework_key": self.framework_key,
                        "safe_patterns": self.safe_patterns,
                        "framework_paths": self.framework_paths,
                    },
                    scanner="RepoDiscovery",
                    confidence=1.0,
                )
            )
        if self.is_container_rootfs:
            for binary in self.binary_paths[:50]:
                objects.append(
                    OntologyObject(
                        type=OntologyType.FILE,
                        name=Path(binary).name,
                        path=binary,
                        properties={"artifact_type": "binary", "container": True},
                        scanner="RepoDiscovery",
                        confidence=0.9,
                    )
                )
            for script in self.embedded_scripts[:50]:
                objects.append(
                    OntologyObject(
                        type=OntologyType.FILE,
                        name=Path(script).name,
                        path=script,
                        properties={"artifact_type": "script", "container": True},
                        scanner="RepoDiscovery",
                        confidence=0.9,
                    )
                )
            for env_var in self.env_vars[:50]:
                objects.append(
                    OntologyObject(
                        type=OntologyType.CONFIG,
                        name=env_var,
                        path=self.root,
                        properties={
                            "artifact_type": "env_var",
                            "container": True,
                            "key": env_var,
                        },
                        scanner="RepoDiscovery",
                        confidence=0.8,
                    )
                )
        for svc in self.services:
            objects.append(
                OntologyObject(
                    type=OntologyType.SERVICE,
                    name=svc.get("name", "unknown_service"),
                    path=svc.get("file", self.root),
                    properties=svc,
                    scanner="RepoDiscovery",
                    confidence=0.85,
                )
            )
        for boundary in self.auth_boundaries:
            objects.append(
                OntologyObject(
                    type=OntologyType.AUTH_BOUNDARY,
                    name=boundary.get("name", "auth_boundary"),
                    path=boundary.get("file", self.root),
                    properties=boundary,
                    scanner="RepoDiscovery",
                    confidence=boundary.get("confidence", 0.7),
                )
            )
        return objects

    def to_ontology_links(self) -> list[OntologyLink]:
        return []


SOURCE_EXTENSIONS: frozenset[str] = frozenset(
    {
        ".py",
        ".pyx",
        ".pyd",
        ".pyi",
        ".js",
        ".jsx",
        ".mjs",
        ".cjs",
        ".ts",
        ".tsx",
        ".mts",
        ".cts",
        ".go",
        ".java",
        ".kt",
        ".kts",
        ".scala",
        ".c",
        ".cpp",
        ".cc",
        ".cxx",
        ".h",
        ".hpp",
        ".hxx",
        ".m",
        ".mm",
        ".cs",
        ".vb",
        ".rb",
        ".erb",
        ".php",
        ".sh",
        ".bash",
        ".zsh",
        ".fish",
        ".ps1",
        ".rs",
        ".swift",
        ".dart",
        ".lua",
        ".zig",
        ".nim",
        ".ex",
        ".exs",
        ".erl",
        ".hrl",
        ".r",
        ".R",
        ".pl",
        ".pm",
        ".tf",
        ".tfvars",
        ".hcl",
        ".yaml",
        ".yml",
        ".toml",
        ".json",
        ".json5",
        ".jsonc",
        ".html",
        ".htm",
        ".xhtml",
        ".css",
        ".scss",
        ".sass",
        ".less",
        ".styl",
        ".vue",
        ".svelte",
        ".graphql",
        ".gql",
        ".asm",
        ".s",
        ".clj",
        ".cljs",
        ".hs",
        ".sc",
        ".jl",
    }
)

BINARY_SKIP_EXTENSIONS: frozenset[str] = frozenset(
    {
        ".o",
        ".so",
        ".a",
        ".lib",
        ".dll",
        ".dylib",
        ".exe",
        ".bin",
        ".com",
        ".class",
        ".pyc",
        ".pyo",
        ".pyd",
        ".wasm",
        ".rlib",
        ".tar",
        ".gz",
        ".bz2",
        ".xz",
        ".zst",
        ".zip",
        ".rar",
        ".7z",
        ".deb",
        ".rpm",
        ".gem",
        ".whl",
        ".egg",
        ".nupkg",
        ".jar",
        ".war",
        ".ear",
        ".png",
        ".jpg",
        ".jpeg",
        ".gif",
        ".svg",
        ".ico",
        ".webp",
        ".bmp",
        ".avif",
        ".heic",
        ".tiff",
        ".tif",
        ".mp4",
        ".mp3",
        ".wav",
        ".avi",
        ".mov",
        ".flv",
        ".mkv",
        ".webm",
        ".ogg",
        ".flac",
        ".aac",
        ".m4a",
        ".ttf",
        ".otf",
        ".woff",
        ".woff2",
        ".eot",
        ".pdf",
        ".doc",
        ".docx",
        ".xls",
        ".xlsx",
        ".ppt",
        ".pptx",
        ".odt",
        ".ods",
        ".odp",
        ".csv",
        ".tsv",
        ".sqlite",
        ".db",
        ".sqlite3",
        ".parquet",
        ".arrow",
        ".feather",
        ".hdf5",
        ".h5",
        ".shp",
        ".geojson",
        ".kml",
        ".gpx",
        ".osm",
        ".pkl",
        ".pickle",
        ".marshal",
        ".msgpack",
        ".cbor",
        ".min.js",
        ".min.css",
        ".map",
        ".bundle.js",
        ".chunk.js",
        ".dvi",
        ".aux",
    }
)

WALK_SKIP_DIRS: frozenset[str] = frozenset(
    {
        ".git",
        "node_modules",
        "__pycache__",
        ".venv",
        "venv",
        "env",
        ".env",
        ".tox",
        ".nox",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        "dist",
        "build",
        ".eggs",
        ".seraph-cache",
        ".seraph-learn",
        "site-packages",
        ".idea",
        ".vscode",
        "vendor",
        "vendors",
        "third_party",
        "third-party",
        "bower_components",
        "app/assets/vendor",
        ".next",
        ".nuxt",
        ".turbo",
        "coverage",
        ".cache",
        "__snapshots__",
        "out",
        "target",
        "obj",
        "playground",
        "playgrounds",
        ".storybook",
        ".docusaurus",
        "man",
        "info",
        "locale",
        "locales",
        "cache",
        "apt",
        "dpkg",
        "yum",
        "dnf",
        "pacman",
        "share/doc",
        "share/man",
        "lib/python*",
        "lib/go",
        "usr/lib",
        "usr/share",
        "usr/include",
        "var/cache",
        "var/lib",
    }
)

TEST_PATH_SEGMENTS: frozenset[str] = frozenset(
    {
        "test",
        "tests",
        "spec",
        "specs",
        "e2e",
        "__tests__",
        "__mocks__",
        "mock",
        "mocks",
        "fixture",
        "fixtures",
        "testdata",
        "test_data",
        "testcluster",
        "testhelpers",
        "testutil",
        "testutils",
        "testing",
        "cypress",
        "playwright",
        "__testfixtures__",
        "smoke",
        "smoke-test",
        "smoketest",
        "smoke_test",
        "integration-test",
        "integtest",
        "acceptance-test",
        "system-test",
        "performance-test",
        "performance_test",
        "perf-test",
    }
)

TEST_FILENAME_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\.(test|spec)\.(js|ts|jsx|tsx|py|go|java|rb|php|cs|swift|kt|ex|exs|rs)$"),
    re.compile(r"[_-]test\.(go|java|cs|py|swift|kt|rb|php|ex|exs|rs)$"),
    re.compile(r"[Tt]est_[^/]+\.py$"),
    re.compile(r"^[Tt]est[^/]*\.(java|kt|swift)$"),
    re.compile(r"[Ss]pec[^/]*\.(java|kt|swift|rb|php)$"),
    re.compile(r"\.feature$"),
    re.compile(r"\.steps\.js$"),
    re.compile(r"\.stories\.(js|ts|jsx|tsx)$"),
    re.compile(r"_spec\.rb$"),
]

NON_PROD_PATH_SEGMENTS: frozenset[str] = frozenset(
    {
        "example",
        "examples",
        "demo",
        "demos",
        "playground",
        "playgrounds",
        "sample",
        "samples",
        "how-to",
        "howto",
        "recipes",
        "docs",
        "doc",
        "documentation",
        "guides",
        "tutorials",
        "docs-site",
        "website",
        "www",
        "blog",
        "changelog",
        "changes",
        "news",
        "contributing",
        "authors",
        "credits",
        "readme",
    }
)

EXT_TO_LANGUAGE: dict[str, str] = {
    ".py": "python",
    ".pyx": "python",
    ".pyi": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".mjs": "javascript",
    ".cjs": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".mts": "typescript",
    ".cts": "typescript",
    ".go": "go",
    ".java": "java",
    ".kt": "kotlin",
    ".kts": "kotlin",
    ".scala": "scala",
    ".c": "c",
    ".cpp": "cpp",
    ".cc": "cpp",
    ".cxx": "cpp",
    ".h": "c",
    ".hpp": "cpp",
    ".hxx": "cpp",
    ".m": "objectivec",
    ".mm": "objectivec",
    ".cs": "csharp",
    ".vb": "visualbasic",
    ".rb": "ruby",
    ".erb": "ruby",
    ".php": "php",
    ".sh": "shell",
    ".bash": "shell",
    ".zsh": "shell",
    ".fish": "shell",
    ".ps1": "powershell",
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
    ".R": "r",
    ".pl": "perl",
    ".pm": "perl",
    ".tf": "hcl",
    ".tfvars": "hcl",
    ".hcl": "hcl",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".toml": "toml",
    ".json": "json",
    ".json5": "json",
    ".jsonc": "json",
    ".html": "html",
    ".css": "css",
    ".scss": "css",
    ".vue": "vue",
    ".svelte": "svelte",
    ".graphql": "graphql",
    ".gql": "graphql",
    ".asm": "assembly",
    ".s": "assembly",
    ".clj": "clojure",
    ".cljs": "clojure",
    ".hs": "haskell",
    ".sc": "scala",
    ".jl": "julia",
}


class RepoDiscovery:
    FRAMEWORK_PATTERNS: dict[str, dict[str, Any]] = {
        "python_web": {
            "display_name": "Python Web Framework",
            "safe_patterns": [
                ("eval(", "/cli/"),
                ("pickle.loads", "/management/"),
                ("exec(", "/commands/"),
                ("subprocess.call", "/scripts/"),
            ],
            "framework_paths": ["django/", "flask/", "fastapi/", "tests/", "scripts/"],
        },
        "js_web": {
            "display_name": "JavaScript Web Framework",
            "safe_patterns": [
                ("eval(", "/webpack/"),
                ("eval(", "/vite/"),
                ("innerHTML", "/react-dom/"),
                ("dangerouslySetInnerHTML", "/react-dom/"),
                ("child_process", "/scripts/"),
            ],
            "framework_paths": [
                "packages/",
                "node_modules/",
                "test/",
                "tests/",
                "examples/",
                "devenv/",
            ],
        },
        "go": {
            "display_name": "Go Application",
            "safe_patterns": [
                ("hardcoded", "testing.go"),
                ("hardcoded", "testhelpers/"),
                ("hardcoded", "testdata/"),
                ("hardcoded", "mock/"),
            ],
            "framework_paths": ["cmd/", "pkg/", "internal/", "test/", "testdata/"],
        },
        "java": {
            "display_name": "Java Application",
            "safe_patterns": [("eval(", "test/"), ("exec(", "test/")],
            "framework_paths": ["src/main/", "src/test/", "test/", "examples/"],
        },
        "ruby": {
            "display_name": "Ruby Application",
            "safe_patterns": [("eval ", "test/"), ("eval ", "spec/")],
            "framework_paths": ["app/", "lib/", "test/", "spec/", "examples/"],
        },
        "rust": {
            "display_name": "Rust Application",
            "safe_patterns": [("eval(", "tests/")],
            "framework_paths": ["src/", "tests/", "examples/"],
        },
        "php": {
            "display_name": "PHP Application",
            "safe_patterns": [("eval(", "tests/"), ("exec(", "tests/")],
            "framework_paths": ["app/", "tests/", "database/"],
        },
        "iac": {
            "display_name": "Infrastructure as Code",
            "safe_patterns": [],
            "framework_paths": ["modules/", "environments/", "terraform/", "helm/"],
        },
    }

    NON_PRODUCTION_DIRS: set[str] = {
        ".git",
        "node_modules",
        "__pycache__",
        ".venv",
        "venv",
        "env",
        ".env",
        ".tox",
        ".nox",
        ".mypy_cache",
        ".pytest_cache",
        "dist",
        "build",
        ".eggs",
        ".seraph-cache",
        ".seraph-learn",
        "site-packages",
        ".idea",
        ".vscode",
        "vendor",
        "vendors",
        "third_party",
        "third-party",
        "bower_components",
        "app/assets/vendor",
        ".next",
        ".nuxt",
        "coverage",
        ".cache",
        "__snapshots__",
        "out",
        "target",
        "playground",
        "playgrounds",
        "benchmarks",
        "perf",
        "performance",
        "e2e",
        "cypress",
        "storybook",
        ".storybook",
        ".docusaurus",
        "website",
        "docs",
        "doc",
        "documentation",
        "example",
        "examples",
        "demo",
        "demos",
        "scripts",
        "tools",
        "tooling",
        ".github",
        ".circleci",
        ".gitlab-ci",
        "fixtures",
        "fixture",
        "testdata",
        "test_data",
        "__mocks__",
        "mocks",
        "testcluster",
        "testhelpers",
        "testutil",
        "testutils",
        "testing",
        "changelog",
        "changes",
        "news",
        "contributing",
        "license",
        "readme",
        "devenv",
        "dev-env",
        "docker",
        "compose",
        "k8s",
        "kubernetes",
        "helm",
        "terraform",
        "cdktf",
        "pulumi",
        "man",
        "info",
        "locale",
        "locales",
        "cache",
        "apt",
        "dpkg",
        "yum",
        "dnf",
        "pacman",
    }

    TEST_FILE_PATTERNS: list[str] = [
        r"\.(test|spec)\.(js|ts|jsx|tsx|py|go|java|rb|php|cs|sh|bash)$",
        r"_[tT]est\.(go|java|cs|py|rb)$",
        r"[tT]est_[^/]+\.py$",
        r"^test[s]?/",
        r"/__tests__/",
        r"/spec[s]?/",
        r"_spec\.rb$",
        r"\.feature$",
        r"\.steps\.js$",
        r"\.stories\.(js|ts|jsx|tsx)$",
    ]

    def __init__(self, path: Path | str):
        self.path = Path(path).resolve()
        self.profile = RepoProfile(root=str(self.path))

    def discover(self) -> RepoProfile:
        self.profile.root = str(self.path)
        self._detect_git()
        self._detect_container_rootfs()
        self._count_files()
        self._detect_languages()
        self._detect_framework()
        self._detect_monorepo()
        self._detect_services()
        self._detect_auth_boundaries()
        if self.profile.is_container_rootfs:
            self._analyze_container_artifacts()
        return self.profile

    def _detect_git(self) -> None:
        self.profile.is_git_repo = (self.path / ".git").exists() or (self.path / ".repo").exists()

    def _detect_container_rootfs(self) -> None:
        indicators = [
            self.path / "etc" / "os-release",
            self.path / "bin" / "sh",
            self.path / "usr" / "lib",
            self.path / "var" / "log",
        ]
        if any(ind.exists() for ind in indicators):
            self.profile.is_container_rootfs = True

    def _analyze_container_artifacts(self) -> None:
        bin_dirs = [
            self.path / "bin",
            self.path / "sbin",
            self.path / "usr" / "bin",
            self.path / "usr" / "sbin",
            self.path / "usr" / "local" / "bin",
        ]
        for d in bin_dirs:
            if d.exists():
                for item in d.iterdir():
                    if item.is_file():
                        try:
                            self.profile.binary_paths.append(str(item.relative_to(self.path)))
                        except ValueError:
                            pass

        script_exts = {".sh", ".bash", ".py", ".pl", ".rb"}
        script_count = 0
        for item in self.path.rglob("*"):
            if item.is_symlink() or not item.is_file():
                continue
            if item.suffix in script_exts:
                try:
                    rel = str(item.relative_to(self.path))
                    if script_count < 100:
                        self.profile.embedded_scripts.append(rel)
                        script_count += 1
                except ValueError:
                    pass

        for env_file in self.path.rglob(".env*"):
            if env_file.is_file():
                try:
                    content = env_file.read_text(errors="ignore")
                    for line in content.splitlines():
                        if "=" in line and not line.startswith("#"):
                            key = line.split("=", 1)[0].strip()
                            if key and key not in self.profile.env_vars:
                                self.profile.env_vars.append(key)
                except OSError:
                    pass

    def _count_files(self) -> None:
        count = prod = test = non_prod = total_size = 0
        try:
            for dirpath, dirnames, filenames in os.walk(
                self.path, followlinks=False, onerror=lambda _: None
            ):
                dirnames[:] = [d for d in dirnames if d not in WALK_SKIP_DIRS]
                for filename in filenames:
                    ext = Path(filename).suffix.lower()
                    if ext in BINARY_SKIP_EXTENSIONS:
                        continue
                    if ext not in SOURCE_EXTENSIONS:
                        continue
                    try:
                        rel_path = str(Path(dirpath).relative_to(self.path))
                    except ValueError:
                        continue
                    path_parts = Path(rel_path).parts
                    count += 1
                    try:
                        total_size += (Path(dirpath) / filename).stat().st_size
                    except OSError:
                        pass
                    if self._is_test_path(path_parts, filename):
                        test += 1
                    elif self._is_non_prod_path(path_parts):
                        non_prod += 1
                    else:
                        prod += 1
        except (PermissionError, OSError) as e:
            logger.warning("Discovery walk error: %s", e)

        self.profile.file_count = count
        self.profile.prod_file_count = prod
        self.profile.test_file_count = test
        self.profile.non_prod_file_count = non_prod
        self.profile.total_size_bytes = total_size

    def _is_test_path(self, parts: tuple[str, ...], filename: str) -> bool:
        if any(part in TEST_PATH_SEGMENTS for part in parts):
            return True
        name_lower = filename.lower()
        return any(pat.search(name_lower) for pat in TEST_FILENAME_PATTERNS)

    @staticmethod
    def _is_non_prod_path(parts: tuple[str, ...]) -> bool:
        return any(part.lower() in NON_PROD_PATH_SEGMENTS for part in parts)

    def _detect_languages(self) -> None:
        """Detect languages from source file extensions.

        v2.0.1 FIX: For small repos (<=10 files), threshold is 1 file.
        For larger repos, use dynamic threshold but never require more than 3.
        This ensures 'app.py' alone triggers 'Python' detection.
        """
        langs: dict[str, int] = {}
        try:
            for _dirpath, dirnames, filenames in os.walk(
                self.path, followlinks=False, onerror=lambda _: None
            ):
                dirnames[:] = [d for d in dirnames if d not in WALK_SKIP_DIRS]
                for filename in filenames:
                    ext = Path(filename).suffix.lower()
                    if ext in EXT_TO_LANGUAGE:
                        lang = EXT_TO_LANGUAGE[ext]
                        langs[lang] = langs.get(lang, 0) + 1
        except (PermissionError, OSError):
            pass

        # v2.0.1 FIX: adaptive threshold that works for repos of any size
        if self.profile.file_count <= 10:
            threshold = 1
        else:
            threshold = max(1, min(3, self.profile.file_count // 100))

        detected = sorted(lang for lang, cnt in langs.items() if cnt >= threshold)

        # v2.0.1 FIX: If we found source files but no languages passed threshold,
        # include all languages with at least 1 file (safety net)
        if not detected and langs:
            detected = sorted(langs.keys())

        self.profile.languages = detected

    def _set_framework(self, key: str) -> None:
        info = self.FRAMEWORK_PATTERNS[key]
        self.profile.is_framework = True
        self.profile.framework_name = info["display_name"]
        self.profile.framework_key = key
        self.profile.safe_patterns = info["safe_patterns"]
        self.profile.framework_paths = info["framework_paths"]
        self.profile.frameworks.append(info["display_name"])

    def _detect_framework(self) -> None:
        pkg_json = self.path / "package.json"
        if pkg_json.exists():
            try:
                content = pkg_json.read_text(errors="ignore")[:10000].lower()
                if any(fw in content for fw in ["next", "react", "vue", "angular", "svelte"]):
                    self._set_framework("js_web")
                    return
            except OSError:
                pass

        if (self.path / "go.mod").exists() or (self.path / "go.work").exists():
            self._set_framework("go")
            return

        for py_indicator in ("setup.py", "pyproject.toml", "requirements.txt"):
            if (self.path / py_indicator).exists():
                self._set_framework("python_web")
                return

        if (self.path / "Cargo.toml").exists():
            self._set_framework("rust")
            return

        if (self.path / "pom.xml").exists() or (self.path / "build.gradle").exists():
            self._set_framework("java")
            return

        if (self.path / "Gemfile").exists():
            self._set_framework("ruby")
            return

        if (self.path / "composer.json").exists():
            self._set_framework("php")
            return

        for iac_file in ("main.tf", "terraform.tf", "Chart.yaml", "Pulumi.yaml"):
            if (self.path / iac_file).exists():
                self._set_framework("iac")
                return

    def _detect_monorepo(self) -> None:
        monorepo_indicators = {
            "lerna.json": "lerna",
            "pnpm-workspace.yaml": "pnpm",
            "nx.json": "nx",
            "turbo.json": "turbo",
            "rush.json": "rush",
            "workspace.json": "nx",
            "go.work": "go-workspace",
        }
        for indicator_file, tool in monorepo_indicators.items():
            if (self.path / indicator_file).exists():
                self.profile.is_monorepo = True
                self.profile.monorepo_tool = tool
                return
        pkg_json = self.path / "package.json"
        if pkg_json.exists():
            try:
                data = json.loads(pkg_json.read_text(encoding="utf-8"))
                if "workspaces" in data:
                    self.profile.is_monorepo = True
                    self.profile.monorepo_tool = "npm-workspaces"
            except (json.JSONDecodeError, OSError):
                pass

    def _detect_services(self) -> None:
        dockerfile = self.path / "Dockerfile"
        self.profile.has_dockerfile = dockerfile.exists()

        dc_files = ["docker-compose.yml", "docker-compose.yaml", "compose.yml", "compose.yaml"]
        for f in dc_files:
            if (self.path / f).exists():
                self.profile.has_docker_compose = True
                try:
                    content = (self.path / f).read_text(errors="ignore")
                    for line in content.splitlines():
                        if line.strip().endswith(":") and not line.strip().startswith(
                            ("version", "services", "networks", "volumes")
                        ):
                            svc_name = line.strip().rstrip(":").strip()
                            if svc_name and svc_name not in [
                                s["name"] for s in self.profile.services
                            ]:
                                self.profile.services.append(
                                    {"name": svc_name, "type": "docker", "file": f}
                                )
                except OSError:
                    pass
                break

        k8s_dir = self.path / "k8s"
        if not k8s_dir.exists():
            k8s_dir = self.path / "kubernetes"
        if k8s_dir.exists() and k8s_dir.is_dir():
            self.profile.has_kubernetes = True
            for manifest in k8s_dir.rglob("*.yaml"):
                try:
                    content = manifest.read_text(errors="ignore")
                    if "kind: Deployment" in content or "kind: Service" in content:
                        name = "unknown"
                        for line in content.splitlines():
                            if line.strip().startswith("name:"):
                                name = line.split(":", 1)[1].strip()
                                break
                        self.profile.services.append(
                            {
                                "name": name,
                                "type": "kubernetes",
                                "file": str(manifest.relative_to(self.path)),
                            }
                        )
                except OSError:
                    pass

        charts_dir = self.path / "charts"
        if charts_dir.exists() and charts_dir.is_dir():
            self.profile.has_helm = True
            for chart in charts_dir.iterdir():
                if chart.is_dir() and (chart / "Chart.yaml").exists():
                    self.profile.services.append(
                        {
                            "name": chart.name,
                            "type": "helm",
                            "file": str(chart.relative_to(self.path)),
                        }
                    )

        tf_files = list(self.path.rglob("*.tf"))
        if tf_files:
            self.profile.has_terraform = True

        gh_dir = self.path / ".github" / "workflows"
        if gh_dir.exists() and gh_dir.is_dir():
            self.profile.has_github_actions = True

    def _detect_auth_boundaries(self) -> None:
        auth_files = [
            "auth.py",
            "authentication.py",
            "authorization.py",
            "permissions.py",
            "middleware.py",
            "decorators.py",
            "rbac.py",
            "acl.py",
            "oauth.py",
            "oidc.py",
            "jwt.py",
            "session.py",
            "security.py",
            "guard.py",
            "policy.py",
        ]
        rls_files = [
            "rls.py",
            "row_level_security.py",
            "tenant.py",
            "multitenant.py",
            "shard.py",
            "sharding.py",
        ]

        found_auth = False
        found_rls = False

        for root, _dirs, files in os.walk(self.path, followlinks=False):
            for f in files:
                if f.lower() in [a.lower() for a in auth_files]:
                    found_auth = True
                    self.profile.auth_boundaries.append(
                        {
                            "name": f"auth:{f}",
                            "file": str(Path(root).relative_to(self.path) / f),
                            "type": "auth_config",
                            "confidence": 0.9,
                        }
                    )
                if f.lower() in [r.lower() for r in rls_files]:
                    found_rls = True
                    self.profile.auth_boundaries.append(
                        {
                            "name": f"rls:{f}",
                            "file": str(Path(root).relative_to(self.path) / f),
                            "type": "rls_config",
                            "confidence": 0.85,
                        }
                    )

        self.profile.has_auth_config = found_auth
        self.profile.has_rls_config = found_rls

        db_indicators = [".sql", "models.py", "schema.py", "migrations"]
        has_db = False
        for _root, _dirs, files in os.walk(self.path, followlinks=False):
            for f in files:
                if any(ind in f.lower() for ind in db_indicators):
                    has_db = True
                    break
            if has_db:
                break

        if has_db and not found_auth:
            self.profile.missing_auth_patterns.append("database_without_auth")
        if has_db and not found_rls:
            self.profile.missing_auth_patterns.append("database_without_rls")
