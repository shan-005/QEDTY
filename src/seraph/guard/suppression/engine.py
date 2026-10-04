import fnmatch
import re

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any


# ═══════════════════════════════════════════════════════════════════════════════
# LAYER 0: EXACT FILENAME BLOCKLIST
# ═══════════════════════════════════════════════════════════════════════════════

EXACT_FILENAME_BLOCKLIST: set[str] = {
    "ltmain.sh",
    "configure",
    "configure.ac",
    "configure.in",
    "config.sub",
    "config.guess",
    "aclocal.m4",
    "acinclude.m4",
    "compile",
    "depcomp",
    "install-sh",
    "missing",
    "ylwrap",
    "test-driver",
    "ar-lib",
    "mkinstalldirs",
    "libtool.m4",
    "ltversion.m4",
    "ltsugar.m4",
    "lt~obsolete.m4",
    "ltclin.m4",
    "cmakelists.txt",
    "config.h.in",
    "stamp-h1",
    "makefile.in",
    "makefile.am",
    "gnu-makefile",
    "meson.build",
    "meson_options.txt",
    "webpack.config.js",
    "webpack.config.ts",
    "rollup.config.js",
    "rollup.config.ts",
    "vite.config.ts",
    "vite.config.js",
    "babel.config.js",
    "babel.config.ts",
    "babel.config.mjs",
    "babel.config.cjs",
    "jest.config.js",
    "jest.config.ts",
    "jest.config.mjs",
    "vitest.config.ts",
    "vitest.config.js",
    "cypress.config.ts",
    "cypress.config.js",
    "playwright.config.ts",
    "playwright.config.js",
    "taskfile.js",
    "taskfile.ts",
    "taskfile.yml",
    "taskfile.yaml",
    "gulpfile.js",
    "gruntfile.js",
    ".eslintrc.js",
    ".eslintrc.ts",
    ".eslintrc.json",
    ".eslintrc.yml",
    ".eslintrc.cjs",
    ".prettierrc.js",
    ".prettierrc.json",
    ".prettierrc.yml",
    ".prettierrc.cjs",
    ".stylelintrc.js",
    ".stylelintrc.json",
    ".stylelintrc.yml",
    ".pylintrc",
    ".flake8",
    "mypy.ini",
    ".ruff.toml",
    "ruff.toml",
    "black.toml",
    "isort.cfg",
    ".isort.cfg",
    "build.gradle",
    "build.gradle.kts",
    "settings.gradle",
    "settings.gradle.kts",
    "gradle.properties",
    "gradlew",
    "gradlew.bat",
    "pom.xml",
    "*.csproj",
    "*.fsproj",
    "*.vbproj",
    "*.props",
    "*.targets",
    "nuget.config",
    "directory.build.props",
    "directory.build.targets",
    "package.swift",
    "project.pbxproj",
    "*.xcworkspacedata",
    "*.xccheckout",
    "gemfile",
    "rakefile",
    "gemspec",
    ".ruby-version",
    "composer.json",
    "composer.lock",
    "phpunit.xml",
    "phpstan.neon",
    "mix.exs",
    "mix.lock",
    "docker-compose.yml",
    "docker-compose.yaml",
    "docker-compose.override.yml",
    "docker-compose.dev.yml",
    "docker-compose.prod.yml",
    "docker-compose.test.yml",
    "dockerfile",
    "dockerfile.prod",
    "dockerfile.dev",
    ".dockerignore",
    ".gitignore",
    ".gitattributes",
    ".gitmodules",
    ".mailmap",
    ".npmrc",
    ".nvmrc",
    ".python-version",
    ".node-version",
    ".go-version",
    ".java-version",
    ".tool-versions",
    "Makefile",
    "gnumakefile",
    "package-lock.json",
    "yarn.lock",
    "pnpm-lock.yaml",
    "poetry.lock",
    "go.sum",
    "Cargo.lock",
    "Pipfile.lock",
    "uv.lock",
    "gradle.lockfile",
    "pubspec.lock",
    "flake.lock",
    "conda-lock.yml",
    "manifest.json",
    "asset-manifest.json",
    "build-manifest.json",
    "react-loadable-manifest.json",
    "sourcemapping-loader-manifest.json",
    "*_tfplan.json",
    "*.tfstate",
    "*.tfstate.backup",
}

BLOCKED_EXTENSIONS: set[str] = {
    ".m4",
    ".cmake",
    ".in",
    ".inc",
    ".l",
    ".y",
    ".o",
    ".so",
    ".a",
    ".lib",
    ".dll",
    ".dylib",
    ".exe",
    ".bin",
    ".class",
    ".pyc",
    ".pyo",
    ".wasm",
    ".rlib",
    ".dvi",
    ".aux",
    ".lock",
    ".tar",
    ".gz",
    ".bz2",
    ".xz",
    ".zst",
    ".zip",
    ".rar",
    ".7z",
    ".rpm",
    ".deb",
    ".gem",
    ".whl",
    ".egg",
    ".nupkg",
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
    ".p12",
    ".pfx",
    ".jks",
    ".keystore",
    ".pkl",
    ".pickle",
    ".marshal",
    ".msgpack",
    ".cbor",
    ".pyd",
    ".min.js",
    ".min.css",
    ".map",
    ".bundle.js",
    ".chunk.js",
}

GENERATED_BASENAME_PATTERNS: list[str] = [
    "*.pb.go",
    "*.pb.gw.go",
    "*_grpc.pb.go",
    "*_gen.go",
    "*_generated.go",
    "zz_generated*.go",
    "deepcopy*.go",
    "conversion*.go",
    "*_string.go",
    "*_mock.go",
    "*_fixture.go",
    "*_testmain.go",
    "*_embed.go",
    "doc.go",
    "register.go",
    "defaults.go",
    "*_pb2.py",
    "*_pb2_grpc.py",
    "*_pb2.pyi",
    "*_grpc.py",
    "*_types.py",
    "*_generated.py",
    "*_pb2_grpc.pyi",
    "*_async_pb2.py",
    "*_async_pb2_grpc.py",
    "schema.py",
    "models.py",
    "*.d.ts",
    "*.generated.ts",
    "*.generated.tsx",
    "*.generated.js",
    "*.generated.jsx",
    "*.graphql.ts",
    "*.graphql.tsx",
    "*.res.ts",
    "*.g.ts",
    "*.g.js",
    "*_generated.java",
    "*gen.java",
    "*Generated.java",
    "*.generated.kt",
    "R.java",
    "R2.java",
    "BuildConfig.java",
    "*_Binding.java",
    "*BindingImpl.java",
    "*_HiltModules.java",
    "Hilt_*.java",
    "*.generated.rs",
    "*_generated.rs",
    "*_proto.rs",
    "ffi.rs",
    "*_bindings.rs",
    "*_mock.rs",
    "*_test.rs",
    "*.generated.swift",
    "*.g.dart",
    "*.freezed.dart",
    "*.gr.dart",
    "*_generated.h",
    "*_generated.c",
    "*_generated.cc",
    "*_generated.cpp",
    "*_pb.h",
    "*_pb.cc",
    "*_grpc.pb.h",
    "*_grpc.pb.cc",
    "*_pb.rpc.h",
    "*_pb.rpc.cc",
    "*_table.pb.h",
    "*_table.pb.cc",
    "ffi.h",
    "*.Designer.cs",
    "*.g.cs",
    "*.g.i.cs",
    "*Generated.cs",
    "*ViewModel.g.cs",
    "*_generated.ex",
    "*_impl.ex",
    "*_web.ex",
    "*.scala-2.13",
    "*.scala-2.12",
    "*.scala-3",
    "*.proto",
    "*.openapi.yaml",
    "*.openapi.yml",
    "*.openapi.json",
    "swagger.yaml",
    "swagger.yml",
    "swagger.json",
    "*.graphql",
    "*.gql",
    "*.thrift",
    "*.fbs",
    "manifest.json",
    "asset-manifest.json",
    "build-manifest.json",
    "react-loadable-manifest.json",
    "sourcemap-loader-manifest.json",
    "*_tfplan.json",
    "*.tfstate",
    "*.tfstate.backup",
    "*_migration.*",
    "*_schema.*",
]

GENERATED_DIR_SEGMENTS: frozenset[str] = frozenset(
    {
        "generated",
        "gen",
        "codegen",
        "code-gen",
        "code_generation",
        "auto_generated",
        ".dart_tool",
        "codegen-output",
        "_codegen_output",
        "proto",
        "protobuf",
        "grpc",
        "wire",
        "wire_gen",
        "mockgen",
        "stringer",
        "go-gen",
        "deepcopy-gen",
        "conversion-gen",
        "register-gen",
        "defaults-gen",
        "client-go-gen",
        "informers-gen",
        "listers-gen",
        "applyconfiguration-gen",
        "helpers-gen",
        "types-gen",
        "fake-gen",
        "informer-gen",
        "k8s.io/code-generator",
        "kubernetes/code-generator",
        "tensorflow/compiler",
        "tensorflow/python/compiler",
        "tensorflow/core/framework",
        "llvm/test",
        "llvm/utils",
        "clang/test",
        "clang/utils",
        "spring-boot-project/spring-boot-tools",
        "spring-boot-autoconfigure/src/main/resources",
        "k8s.io/api",
        "k8s.io/apiextensions-apiserver",
        "k8s.io/apimachinery",
        "k8s.io/client-go",
        "k8s.io/kube-openapi-gen",
        "k8s.io/kube-openapi-gen/testdata",
    }
)

GLOB_SKIP_PATTERNS: list[str] = [
    "**/node_modules/**",
    "**/vendor/**",
    "**/vendors/**",
    "**/bower_components/**",
    "**/.next/**",
    "**/.nuxt/**",
    "**/.gradle/**",
    "**/.m2/**",
    "**/.cargo/registry/**",
    "**/go/pkg/mod/**",
    "**/gomodcache/**",
    "**/site-packages/**",
    "**/.venv/**",
    "**/venv/**",
    "**/env/**",
    "**/.eggs/**",
    "**/*.egg-info/**",
    "**/Pods/**",
    "**/Carthage/**",
    "**/third_party/**",
    "**/third-party/**",
    "**/external/**",
    "**/.dart_tool/**",
    "**/_build/**",
    "**/dist/**",
    "**/build/**",
    "**/out/**",
    "**/target/**",
    "**/.build/**",
    "**/bin/**",
    "**/obj/**",
    "**/gen/**",
    "**/generated/**",
    "**/auto_generated/**",
    "**/codegen/**",
    "**/code-gen/**",
    "**/.turbo/**",
    "**/.cache/**",
    "**/*.min.js",
    "**/*.min.css",
    "**/*.bundle.js",
    "**/*.map",
    "**/__pycache__/**",
    "**/.pytest_cache/**",
    "**/.mypy_cache/**",
    "**/.ruff_cache/**",
    "**/.tox/**",
    "**/.nox/**",
    "**/coverage/**",
    "**/.coverage/**",
    "**/htmlcov/**",
    "**/.eslintcache",
    "**/.parcel-cache/**",
    "**/.tsbuildinfo",
    "**/.next/cache/**",
    "**/target/debug/**",
    "**/target/release/**",
    "**/test/**",
    "**/tests/**",
    "**/spec/**",
    "**/specs/**",
    "**/e2e/**",
    "**/e2e-tests/**",
    "**/__tests__/**",
    "**/__mocks__/**",
    "**/mock/**",
    "**/mocks/**",
    "**/fixture/**",
    "**/fixtures/**",
    "**/testdata/**",
    "**/test_data/**",
    "**/testcluster/**",
    "**/testhelpers/**",
    "**/testutil/**",
    "**/testutils/**",
    "**/testing/**",
    "**/cypress/**",
    "**/playwright/**",
    "**/__testfixtures__/**",
    "**/smoke/**",
    "**/smoke-test/**",
    "**/smoketest/**",
    "**/smoke_tests/**",
    "**/integration-test/**",
    "**/integration-tests/**",
    "**/integtest/**",
    "**/integ tests/**",
    "**/acceptance/**",
    "**/acceptance-test/**",
    "**/system-test/**",
    "**/example/**",
    "**/examples/**",
    "**/demo/**",
    "**/demos/**",
    "**/docs/**",
    "**/doc/**",
    "**/documentation/**",
    "**/guides/**",
    "**/tutorials/**",
    "**/samples/**",
    "**/sample/**",
    "**/how-to/**",
    "**/howto/**",
    "**/recipes/**",
    "**/*.md",
    "**/*.mdx",
    "**/*.rst",
    "**/*.txt",
    "**/*.adoc",
    "**/*.asciidoc",
    "**/README*",
    "**/CHANGELOG*",
    "**/RELEASE*",
    "**/LICENSE*",
    "**/LICENCE*",
    "**/CONTRIBUTING*",
    "**/CODE_OF_CONDUCT*",
    "**/SECURITY*",
    "**/MAINTAINERS*",
    "**/AUTHORS*",
    "**/ROADMAP*",
    "**/.github/**",
    "**/.circleci/**",
    "**/.travis/**",
    "**/.gitlab-ci/**",
    "**/.azure-pipelines/**",
    "**/.gitlab/**",
    "**/scripts/**",
    "**/tools/**",
    "**/tooling/**",
    "**/ci/**",
    "**/jenkins/**",
    "**/ansible/**",
    "**/.ci/**",
    "**/.githooks/**",
    "**/bench/**",
    "**/benchmark/**",
    "**/benchmarks/**",
    "**/perf/**",
    "**/performance/**",
    "**/playground/**",
    "**/playgrounds/**",
    "**/website/**",
    "**/www/**",
    "**/blog/**",
    "**/docs-site/**",
    "**/devenv/**",
    "**/dev-env/**",
    "**/.vscode/**",
    "**/.idea/**",
    "**/.editorconfig",
    "**/*.prettierrc*",
    "**/*.eslintrc*",
    "**/*.babelrc*",
    "**/*.stylelintrc*",
    "**/*.pylintrc*",
    "**/*.flake8*",
    "**/mypy.ini",
    "**/.ruff.toml",
    "**/ruff.toml",
    "**/black.toml",
    "**/isort.cfg",
    "**/.isort.cfg",
    "**/test*/**/*.pem",
    "**/test*/**/*.key",
    "**/test*/**/*.crt",
    "**/test*/**/*.cer",
    "**/fixture*/**/*.pem",
    "**/fixture*/**/*.key",
    "**/fixture*/**/*.cer",
    "**/*.json5",
    "**/*.toml.template",
    "**/*.yaml.template",
    "**/*.yml.template",
    "**/*.hbs",
    "*.mustache",
    "**/*.jinja",
    "**/*.j2",
    "**/*.erb",
    "**/*.haml",
    "**/*.slim",
]

COMPILED_SKIP_PATTERNS: list[re.Pattern[str]] = [
    re.compile(
        r"(?:^|[/\\])("
        r"test|tests|spec|specs|e2e|__tests__|__mocks__|mock|mocks|"
        r"fixture|fixtures|testdata|test_data|testcluster|testhelpers|"
        r"testutil|testutils|testing|cypress|playwright|__testfixtures__|"
        r"smoke|smoke-test|smoketest|smoke_test|"
        r"integration.test|integration-test|integration_test|integtest|"
        r"acceptance.test|acceptance-test|acceptance_test|"
        r"system.test|system-test"
        r")(?:[/\\]|$)"
    ),
    re.compile(
        r"(?:^|[/\\])("
        r"example|examples|demo|demos|playground|playgrounds|sample|samples|"
        r"how-to|howto|recipes"
        r")(?:[/\\]|$)"
    ),
    re.compile(
        r"(?:^|[/\\])("
        r"docs|doc|documentation|website|www|blog|guides|tutorials|docs-site"
        r")(?:[/\\]|$)"
    ),
    re.compile(r"\.(md|mdx|rst|txt|adoc|asciidoc)$"),
    re.compile(
        r"(?:^|[/\\])("
        r"build|dist|out|target|compiled|\.next|\.nuxt|\.build|"
        r"bin|obj|gen|generated|auto_generated|codegen|code-gen|"
        r"\.turbo|\.cache|_build|_output"
        r")(?:[/\\]|$)"
    ),
    re.compile(
        r"(?:^|[/\\])("
        r"scripts|tools|tooling|ci|jenkins|ansible|\.github|\.circleci|"
        r"\.travis|\.gitlab-ci|\.gitlab|\.azure-pipelines|\.githooks|"
        r"devenv|dev-env"
        r")(?:[/\\]|$)"
    ),
    re.compile(r"(?:^|[/\\])(bench|benchmark|benchmarks|perf|performance)(?:[/\\]|$)"),
    re.compile(
        r"(?:^|[/\\])("
        r"node_modules|vendor|bower_components|site-packages|"
        r"third_party|third-party|external|pod|carthage|\.dart_tool"
        r")(?:[/\\]|$)"
    ),
    re.compile(
        r"(?:^|[/\\])("
        r"__pycache__|\.pytest_cache|\.mypy_cache|\.ruff_cache|\.tox|\.nox|"
        r"coverage|htmlcov|\.eslintcache|\.parcel-cache|\.turbo|\.cache"
        r")(?:[/\\]|$)"
    ),
    re.compile(r"\.(test|spec)\.(js|ts|jsx|tsx|py|go|java|rb|php|cs|swift|kt|ex|exs|rs)$"),
    re.compile(r"[_-]test\.(go|java|cs|py|swift|kt|rb|php|ex|exs|rs)$"),
]


class FileCategory(Enum):
    PRODUCTION = "production"
    TEST = "test"
    EXAMPLE = "example"
    DOCUMENTATION = "documentation"
    BUILD = "build"
    FRAMEWORK = "framework"
    GENERATED = "generated"
    DEV_TOOLING = "dev_tooling"
    NON_PRODUCTION = "non_production"


@dataclass
class FileClassification:
    category: FileCategory
    reason: str


_DIR_CATEGORY_MAP: list[tuple[list[str], FileCategory, str]] = [
    (
        [
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
        ],
        FileCategory.TEST,
        "test infrastructure",
    ),
    (
        [
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
        ],
        FileCategory.EXAMPLE,
        "example/demo code",
    ),
    (
        [
            "docs",
            "doc",
            "documentation",
            "website",
            "www",
            "blog",
            "guides",
            "tutorials",
            "docs-site",
        ],
        FileCategory.DOCUMENTATION,
        "documentation",
    ),
    (
        [
            "build",
            "dist",
            "out",
            "target",
            "compiled",
            ".next",
            ".nuxt",
            ".build",
            "bin",
            "obj",
            "gen",
            "generated",
            "auto_generated",
            "codegen",
            "code-gen",
            "_build",
            "_output",
        ],
        FileCategory.BUILD,
        "build output",
    ),
    (
        [
            "scripts",
            "tools",
            "tooling",
            "ci",
            "jenkins",
            "ansible",
            ".github",
            ".circleci",
            ".travis",
            ".gitlab-ci",
            ".gitlab",
            ".azure-pipelines",
            ".githooks",
            "devenv",
            "dev-env",
        ],
        FileCategory.DEV_TOOLING,
        "dev tooling / CI",
    ),
    (
        ["bench", "benchmark", "benchmarks", "perf", "performance"],
        FileCategory.NON_PRODUCTION,
        "benchmark",
    ),
    (
        [
            "node_modules",
            "vendor",
            "vendors",
            "bower_components",
            "site-packages",
            "third_party",
            "third-party",
            "external",
            "pod",
            "carthage",
            ".dart_tool",
        ],
        FileCategory.NON_PRODUCTION,
        "dependencies",
    ),
    (
        [
            "__pycache__",
            ".pytest_cache",
            ".mypy_cache",
            ".ruff_cache",
            ".tox",
            ".nox",
            "coverage",
            "htmlcov",
            ".eslintcache",
            ".parcel-cache",
            ".turbo",
            ".cache",
        ],
        FileCategory.NON_PRODUCTION,
        "cache / tooling artifacts",
    ),
]


_TEST_FILE_SUFFIXES: tuple[str, ...] = (
    ".py",
    ".pyi",
    ".js",
    ".jsx",
    ".ts",
    ".tsx",
    ".mjs",
    ".cjs",
    ".go",
    ".java",
    ".kt",
    ".kts",
    ".rb",
    ".php",
    ".cs",
    ".swift",
    ".rs",
    ".ex",
    ".exs",
    ".scala",
)


def _classify_dir_segment(segment: str) -> tuple[FileCategory | None, str]:
    seg_lower = segment.lower().strip("/").strip("\\")
    for dir_names, cat, reason in _DIR_CATEGORY_MAP:
        if seg_lower in dir_names:
            return cat, reason
    return None, ""


# ═══════════════════════════════════════════════════════════════════════════════
# SEVERITY EXCEPTIONS — findings that must NEVER be suppressed
# ═══════════════════════════════════════════════════════════════════════════════

_SECRET_RULE_KEYWORDS: frozenset[str] = frozenset(
    {
        "secret",
        "password",
        "token",
        "api_key",
        "apikey",
        "credential",
        "private_key",
        "privatekey",
        "pem",
        "certificate",
        "hardcoded",
        "env_var",
        "envvar",
        "aws_key",
        "github_token",
        "slack_token",
        "jwt",
        "bearer",
        "auth",
        "basic_auth",
    }
)

# Categories that are typically suppressed (non-production).
# DEV_TOOLING is deliberately excluded: CI/CD and developer automation are
# supply-chain-sensitive surfaces and must remain visible to the security gate.
_SUPPRESSIBLE_CATEGORIES: set[FileCategory] = {
    FileCategory.TEST,
    FileCategory.EXAMPLE,
    FileCategory.DOCUMENTATION,
    FileCategory.BUILD,
    FileCategory.FRAMEWORK,
    FileCategory.GENERATED,
    FileCategory.NON_PRODUCTION,
}

# Package manifest files where SBOM findings are EXPECTED
_MANIFEST_FILES: set[str] = {
    "package.json",
    "package-lock.json",
    "yarn.lock",
    "pnpm-lock.yaml",
    "requirements.txt",
    "requirements-dev.txt",
    "pyproject.toml",
    "poetry.lock",
    "pipfile.lock",
    "go.mod",
    "go.sum",
    "pom.xml",
    "build.gradle",
    "build.gradle.kts",
    "cargo.toml",
    "cargo.lock",
    "gemfile",
    "gemfile.lock",
    "composer.json",
    "composer.lock",
    "pubspec.yaml",
    "pubspec.lock",
    "packages.lock.json",
}


class SuppressionEngine:
    """Universal file classifier. Works on any repo, any language.

    v2.0.2: Fixed over-aggressive suppression.
    - SBOM/vulnerability findings in package manifests are no longer suppressed.
    - Critical/high/secret findings always bypass file-category suppression.
    - Blast-radius score >= 70 prevents suppression, with documented 0-1 scores
      normalized to percentages.
    - DEV_TOOLING remains gate-visible rather than being file-category suppressed.
    """

    def __init__(self, repo_root: str = ".", learning_engine: Any | None = None):
        self.repo_root = Path(repo_root).resolve()
        # Kept only for constructor compatibility with older callers.
        # Automatic suppression is never written back into adaptive learning.
        self.learning = learning_engine
        self._classification_cache: dict[str, FileClassification] = {}
        self._suppression_stats: dict[str, int] = {
            "test_suppressed": 0,
            "example_suppressed": 0,
            "doc_suppressed": 0,
            "build_suppressed": 0,
            "framework_suppressed": 0,
            "generated_suppressed": 0,
            "dev_tooling_suppressed": 0,
            "rule_override_suppressed": 0,
            "rule_override_downgraded": 0,
            "severity_exception_allowed": 0,
            "manifest_exception_allowed": 0,
        }

    @staticmethod
    def _normalize_path(file_path: str) -> str:
        clean = file_path.replace("\\", "/")
        clean = re.sub(r"^\./", "", clean)
        return clean.lower()

    def _match_glob(self, norm_path: str, patterns: list[str]) -> bool:
        for pattern in patterns:
            if fnmatch.fnmatch(norm_path, pattern):
                return True
            path_obj = Path(norm_path)
            for parent in path_obj.parents:
                parent_str = str(parent).replace("\\", "/")
                if fnmatch.fnmatch(parent_str + "/", pattern) or fnmatch.fnmatch(
                    parent_str, pattern.removesuffix("/**")
                ):
                    return True
        return False

    def classify_file(self, file_path: str) -> FileClassification:
        if file_path in self._classification_cache:
            return self._classification_cache[file_path]

        if not file_path or not file_path.strip():
            res = FileClassification(category=FileCategory.NON_PRODUCTION, reason="empty path")
            self._classification_cache[file_path] = res
            return res

        norm_path = self._normalize_path(file_path)
        name = Path(file_path).name.lower()
        ext = Path(file_path).suffix.lower()

        # CI workflows are production supply-chain surfaces. They must not be
        # downgraded to dev tooling merely because they live under .github/.
        if norm_path.startswith(".github/workflows/") or "/.github/workflows/" in norm_path:
            res = FileClassification(FileCategory.PRODUCTION, "CI workflow (supply-chain surface)")
            self._classification_cache[file_path] = res
            return res

        # Generated directories take precedence over filename-based rules.
        # A generated/test/example manifest must retain that contextual class.
        path_parts = Path(norm_path).parts
        if len(path_parts) > 1:
            for part in path_parts[:-1]:
                part_clean = part.strip("/").strip("\\").lower()
                if part_clean in GENERATED_DIR_SEGMENTS:
                    res = FileClassification(
                        category=FileCategory.GENERATED,
                        reason=f"inside generated directory: {part_clean}/",
                    )
                    self._classification_cache[file_path] = res
                    return res

        # Repository-context patterns must run before filename exceptions so
        # paths such as examples/*/package.json and tests/package.json remain
        # non-production.
        for pat in COMPILED_SKIP_PATTERNS:
            if pat.search(norm_path):
                cat, reason = self._classify_regex_match(pat.pattern)
                res = FileClassification(category=cat, reason=reason)
                self._classification_cache[file_path] = res
                return res

        # Dependency manifests/lockfiles are production security surfaces when
        # they are not already classified as test/example/docs/build/generated
        # context. This prevents go.sum/package.json from being treated as
        # generic build files while preserving contextual exclusions.
        if name in _MANIFEST_FILES:
            res = FileClassification(
                category=FileCategory.PRODUCTION,
                reason="production dependency manifest",
            )
            self._classification_cache[file_path] = res
            return res

        if name in EXACT_FILENAME_BLOCKLIST or any(
            fnmatch.fnmatch(name, pat) for pat in EXACT_FILENAME_BLOCKLIST
        ):
            res = FileClassification(
                category=FileCategory.BUILD, reason=f"build system file: {name}"
            )
            self._classification_cache[file_path] = res
            return res

        if ext in BLOCKED_EXTENSIONS:
            if ext in (".m4", ".cmake", ".in", ".inc", ".l", ".y"):
                reason = "build system macro / template"
            elif ext in (
                ".o",
                ".so",
                ".a",
                ".lib",
                ".dll",
                ".dylib",
                ".exe",
                ".bin",
                ".class",
                ".pyc",
                ".pyo",
                ".wasm",
                ".rlib",
                ".pyd",
            ):
                reason = "compiled binary"
            elif ext == ".lock":
                reason = "lock file"
            elif ext in (".hbs", ".mustache", ".jinja", ".j2", ".erb", ".haml", ".slim"):
                reason = "template file"
            else:
                reason = f"non-source extension: {ext}"
            res = FileClassification(category=FileCategory.NON_PRODUCTION, reason=reason)
            self._classification_cache[file_path] = res
            return res

        for pattern in GENERATED_BASENAME_PATTERNS:
            if fnmatch.fnmatch(name, pattern):
                res = FileClassification(
                    category=FileCategory.GENERATED, reason=f"generated code: {name}"
                )
                self._classification_cache[file_path] = res
                return res

        if self._match_glob(norm_path, GLOB_SKIP_PATTERNS):
            segments = Path(norm_path).parts
            for seg in segments:
                seg_cat, seg_reason = _classify_dir_segment(seg)
                if seg_cat is not None:
                    res = FileClassification(category=seg_cat, reason=f"{seg_reason} (glob)")
                    self._classification_cache[file_path] = res
                    return res

            if name.endswith((".md", ".mdx", ".rst", ".txt", ".adoc", ".asciidoc")):
                res = FileClassification(
                    category=FileCategory.DOCUMENTATION, reason="documentation (glob)"
                )
            else:
                res = FileClassification(category=FileCategory.NON_PRODUCTION, reason="glob match")
            self._classification_cache[file_path] = res
            return res

        result = self._classify_heuristic(name, norm_path)
        if result is not None:
            self._classification_cache[file_path] = result
            return result

        res = FileClassification(
            category=FileCategory.PRODUCTION, reason="default production classification"
        )
        self._classification_cache[file_path] = res
        return res

    def _classify_regex_match(self, pattern_text: str) -> tuple[FileCategory, str]:
        """Determine the file category from the regex that matched the path."""
        text = pattern_text.lower()
        if any(
            kw in text
            for kw in (
                "test",
                "spec",
                "mock",
                "fixture",
                "__tests__",
                "e2e",
                "cypress",
                "playwright",
                "smoke",
                "integration.test",
                "acceptance.test",
                "system.test",
            )
        ):
            return FileCategory.TEST, "test infrastructure (regex)"
        if any(
            kw in text for kw in ("example", "demo", "playground", "sample", "how-to", "recipes")
        ):
            return FileCategory.EXAMPLE, "example/demo code (regex)"
        if any(
            kw in text
            for kw in (
                "docs",
                "documentation",
                ".md",
                ".mdx",
                ".rst",
                "website",
                "www",
                "blog",
                "guides",
                "tutorials",
                "docs-site",
            )
        ):
            return FileCategory.DOCUMENTATION, "documentation (regex)"
        if any(
            kw in text
            for kw in (
                "build",
                "dist",
                "out",
                "target",
                "compiled",
                ".next",
                ".nuxt",
                "bin",
                "obj",
                "gen",
                "generated",
                "codegen",
                "code-gen",
                ".turbo",
                ".cache",
                "_build",
                "_output",
            )
        ):
            return FileCategory.BUILD, "build output (regex)"
        if any(
            kw in text
            for kw in (
                "scripts",
                "tools",
                "tooling",
                "ci",
                "jenkins",
                ".github",
                ".circleci",
                ".travis",
                ".gitlab-ci",
                ".gitlab",
                ".azure-pipelines",
                ".githooks",
                "devenv",
                "dev-env",
            )
        ):
            return FileCategory.DEV_TOOLING, "dev tooling / CI (regex)"
        if any(kw in text for kw in ("bench", "benchmark", "perf", "performance")):
            return FileCategory.NON_PRODUCTION, "benchmark (regex)"
        if any(
            kw in text
            for kw in (
                "node_modules",
                "vendor",
                "bower",
                "site-packages",
                "third_party",
                "third-party",
                "external",
                "pod",
                "carthage",
                ".dart_tool",
            )
        ):
            return FileCategory.NON_PRODUCTION, "dependencies (regex)"
        if any(
            kw in text
            for kw in (
                "__pycache__",
                ".pytest",
                ".mypy",
                ".ruff",
                ".tox",
                ".eslint",
                ".parcel",
                ".turbo",
                ".cache",
            )
        ):
            return FileCategory.NON_PRODUCTION, "cache / tooling artifacts (regex)"
        return FileCategory.NON_PRODUCTION, f"regex match: {pattern_text[:50]}"

    def _classify_heuristic(self, name: str, norm_path: str) -> FileClassification | None:
        # Root-level files such as tests/test_ufic.py become simply
        # test_ufic.py when the scan root itself is the tests directory.
        # Classify them as tests even when no test directory segment remains.
        if name.startswith(("test_", "test-")) and name.endswith(_TEST_FILE_SUFFIXES):
            return FileClassification(category=FileCategory.TEST, reason="test file by naming")
        if name.startswith(("spec_", "spec-")) and name.endswith(_TEST_FILE_SUFFIXES):
            return FileClassification(category=FileCategory.TEST, reason="spec file by naming")
        if name in (
            "testing.go",
            "test_main.go",
            "test_helper.go",
            "test_utils.go",
            "export_test.go",
        ):
            return FileClassification(category=FileCategory.TEST, reason="go test infrastructure")
        if name.endswith(
            (
                "_test.go",
                "_test.py",
                "test.java",
                "test.cs",
                "test.rb",
                "test.php",
                "test.swift",
                "test.kt",
                "_test.ex",
                "_test.exs",
                "_test.rs",
            )
        ):
            return FileClassification(category=FileCategory.TEST, reason="test file by naming")
        if name in (
            "taskfile.js",
            "taskfile.ts",
            "taskfile.yml",
            "taskfile.yaml",
            "gulpfile.js",
            "gruntfile.js",
            "jest.config.js",
            "jest.config.ts",
            "jest.config.mjs",
            "cypress.config.ts",
            "cypress.config.js",
            "playwright.config.ts",
            "playwright.config.js",
            "vitest.config.ts",
            "vitest.config.js",
            "tsconfig.json",
            "jsconfig.json",
            ".eslintrc.js",
            ".eslintrc.ts",
            ".eslintrc.json",
            ".eslintrc.yml",
            ".eslintrc.cjs",
            ".prettierrc.js",
            ".prettierrc.json",
            ".prettierrc.yml",
            ".prettierrc.cjs",
            ".stylelintrc.js",
            ".stylelintrc.json",
            ".stylelintrc.yml",
            "ruff.toml",
            ".ruff.toml",
            "black.toml",
            "isort.cfg",
            ".isort.cfg",
        ):
            return FileClassification(category=FileCategory.DEV_TOOLING, reason="build/lint config")
        if name.startswith("dockerfile") or name in (
            ".dockerignore",
            "docker-compose.yml",
            "docker-compose.yaml",
            "docker-compose.dev.yml",
            "docker-compose.prod.yml",
            "docker-compose.test.yml",
            "docker-compose.override.yml",
        ):
            return FileClassification(
                category=FileCategory.DEV_TOOLING, reason="docker infrastructure"
            )
        if name.endswith((".pem", ".key", ".crt", ".cer", ".p12", ".pfx")) and any(
            seg in norm_path
            for seg in (
                "/test/",
                "/tests/",
                "/fixture/",
                "/fixtures/",
                "/mock/",
                "/mocks/",
                "/certs/test/",
                "/ssl/test/",
                "/smoke/",
            )
        ):
            return FileClassification(category=FileCategory.TEST, reason="test certificate")
        if name in (
            "package-lock.json",
            "yarn.lock",
            "pnpm-lock.yaml",
            "composer.lock",
            "gemfile.lock",
            "go.sum",
            "cargo.lock",
            "poetry.lock",
            "pipfile.lock",
            "uv.lock",
            "gradle.lockfile",
            "pubspec.lock",
            "mix.lock",
            "flake.lock",
            "conda-lock.yml",
        ):
            return FileClassification(category=FileCategory.NON_PRODUCTION, reason="lock file")
        if name in (
            "package.json",
            "gemfile",
            "pubspec.yaml",
            "mix.exs",
            "cargo.toml",
            "pyproject.toml",
            "go.mod",
            "go.work",
            "go.work.sum",
            "flake.nix",
            "shell.nix",
        ):
            return FileClassification(
                category=FileCategory.PRODUCTION, reason="production dependency manifest"
            )
        if name in (
            ".gitignore",
            ".gitattributes",
            ".gitmodules",
            ".mailmap",
            ".editorconfig",
            ".npmrc",
            ".nvmrc",
            ".python-version",
            ".node-version",
            ".go-version",
            ".ruby-version",
            ".java-version",
            ".tool-versions",
            ".env.example",
            ".env.template",
            "makefile",
            "gnumakefile",
        ):
            return FileClassification(
                category=FileCategory.NON_PRODUCTION, reason="config / meta file"
            )
        return None

    # ═══════════════════════════════════════════════════════════════════════════
    # v2.0.2 FIX: Severity-aware suppression + manifest exception + blast radius
    # ═══════════════════════════════════════════════════════════════════════════

    def _is_severe_or_secret(self, finding: dict[str, Any]) -> bool:
        """Return True if the finding is too severe or sensitive to suppress."""
        severity_value = finding.get("severity", "")
        severity = str(getattr(severity_value, "value", severity_value)).lower()
        if severity in ("critical", "high"):
            return True

        # Also check category for vulnerability findings with high blast radius
        blast = finding.get("blast_radius", {})
        raw_blast_score: Any = 0
        if isinstance(blast, dict):
            raw_blast_score = blast.get("blast_radius_score", 0)
        elif hasattr(blast, "blast_radius_score"):
            raw_blast_score = getattr(blast, "blast_radius_score", 0)
        try:
            blast_score = float(raw_blast_score or 0)
        except (TypeError, ValueError):
            blast_score = 0.0

        # Base.BlastRadius documents a 0.0-1.0 score, while older scanners
        # may have emitted a 0-100 score (and some historical code used 0-10).
        # Normalize the documented compact scales before applying the gate.
        if 0.0 <= blast_score <= 1.0:
            blast_score *= 100.0
        elif 1.0 < blast_score <= 10.0:
            blast_score *= 10.0

        if blast_score >= 70.0:
            return True

        category_value = finding.get("category", "")
        category = str(getattr(category_value, "value", category_value)).lower()
        if category == "secret":
            return True

        rule_id = str(finding.get("rule_id", "")).lower()
        if any(kw in rule_id for kw in _SECRET_RULE_KEYWORDS):
            return True

        title = str(finding.get("title", "")).lower()
        return any(kw in title for kw in _SECRET_RULE_KEYWORDS)

    def _is_manifest_file(self, file_path: str) -> bool:
        """Check if file is a package manifest where SBOM findings live."""
        name = Path(file_path).name.lower()
        return name in _MANIFEST_FILES

    def should_scan_file(self, file_path: str) -> tuple[bool, str]:
        """Pre-scan gate: should we even open this file?"""
        classification = self.classify_file(file_path)
        if classification.category in (FileCategory.GENERATED, FileCategory.DOCUMENTATION):
            return False, f"Skipped: {classification.category.value} — {classification.reason}"
        ext = Path(file_path).suffix.lower()
        if ext in BLOCKED_EXTENSIONS and ext not in (".lock", ".in", ".m4", ".cmake"):
            return False, f"Skipped: binary / non-source extension — {ext}"
        return True, "Allowed: will scan and suppress per-finding if needed"

    def apply_suppression(
        self, finding: dict[str, Any], classification: FileClassification
    ) -> tuple[bool, str, str]:
        """Per-finding suppression with severity-aware exceptions.

        Returns:
            (suppressed: bool, new_severity: str, reason: str)
        """
        # ── Severity / secret / blast radius exception ──
        # NEVER suppress critical/high findings, secrets, or high blast-radius items
        if self._is_severe_or_secret(finding):
            self._suppression_stats["severity_exception_allowed"] += 1
            return False, "", ""

        # ── Manifest exception ──
        # SBOM / vulnerability findings in package manifests are EXPECTED there.
        # These are real production issues, not noise.
        category_value = finding.get("category", "")
        category = str(getattr(category_value, "value", category_value)).lower()
        if (
            category in ("vulnerability", "sbom")
            and classification.category is FileCategory.PRODUCTION
            and self._is_manifest_file(str(finding.get("file", "")))
        ):
            self._suppression_stats["manifest_exception_allowed"] += 1
            return False, "", ""

        # ── File-category suppression ──
        if classification.category in _SUPPRESSIBLE_CATEGORIES:
            stat_key = f"{classification.category.value}_suppressed"
            self._suppression_stats[stat_key] = self._suppression_stats.get(stat_key, 0) + 1
            reason = f"Suppressed: {classification.category.value} — {classification.reason}"
            return (
                True,
                "",
                reason,
            )

        # ── Rule-specific overrides (unchanged) ──
        rule_id = str(finding.get("rule_id", "") or "").lower()
        path = self._normalize_path(str(finding.get("file", "") or ""))
        if any(
            k in rule_id for k in ("eval", "exec", "function", "system", "passthru", "shell_exec")
        ):
            if any(
                seg in path
                for seg in (
                    "/build/",
                    "/compiled/",
                    "/scripts/",
                    "/tools/",
                    "/tooling/",
                    "/webpack/",
                    "/rollup/",
                    "/vite/",
                    "/esbuild/",
                    "/babel/",
                    "/gulpfile/",
                    "/gruntfile/",
                    "/taskfile/",
                    "/next.config/",
                    "/webpack.config/",
                )
            ):
                self._suppression_stats["rule_override_suppressed"] += 1
                reason = "Build system / tooling — intentional dynamic code"
                return True, "", reason
            if any(
                seg in path
                for seg in (
                    "/runtime/",
                    "/hmr/",
                    "/hot-module-replacement/",
                    "/sourcemap/",
                    "/source-map/",
                    "/devtools/",
                    "/react-dom/",
                    "/react/",
                    "/vue/",
                    "/angular/",
                    "/svelte/",
                    "/next/dist/",
                    "/next/compiled/",
                    "/turbopack/",
                    "/turbo/",
                )
            ):
                self._suppression_stats["rule_override_suppressed"] += 1
                reason = "Framework runtime internals — intentional eval for HMR/devtools"
                return True, "", reason

        if (
            "hardcoded" in rule_id
            and "password" in rule_id
            and any(
                seg in path
                for seg in (
                    "/test/",
                    "/tests/",
                    "/testdata/",
                    "/mock/",
                    "/mocks/",
                    "/fixture/",
                    "/fixtures/",
                    "/testhelpers/",
                    "/testcluster/",
                    "/testing/",
                    "/__mocks__/",
                    "/__testfixtures__/",
                    "/smoke/",
                    "/_examples/",
                )
            )
        ):
            self._suppression_stats["rule_override_suppressed"] += 1
            reason = "Test/mock credentials — not production secrets"
            return True, "", reason

        if (
            "hardcoded" in rule_id
            and any(k in rule_id for k in ("password", "secret", "token", "key", "credential"))
            and any(Path(path).name.startswith(p) for p in ("fake_", "mock_", "stub_"))
        ):
            self._suppression_stats["rule_override_suppressed"] += 1
            reason = "Fake/mock file — not production secrets"
            return True, "", reason

        if any(k in rule_id for k in ("private.key", "private_key", "pem", "certificate")) and any(
            seg in path
            for seg in (
                "/test/",
                "/tests/",
                "/fixture/",
                "/fixtures/",
                "/mock/",
                "/mocks/",
                "/certs/test/",
                "/ssl/test/",
            )
        ):
            self._suppression_stats["rule_override_suppressed"] += 1
            reason = "Test certificate — not a production key"
            return True, "", reason

        return False, "", ""

    def get_suppression_stats(self) -> dict[str, int]:
        return self._suppression_stats.copy()
