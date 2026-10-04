"""Container & VM Image Scanner — Unpacks OCI/Docker images and scans the rootfs.

v2.0.0: Fixed host-filesystem scan bug, added image config analysis,
         whiteout handling, binary skipping, and container-specific checks.
"""

import json
import logging
import re
import shutil
import subprocess  # nosec B404 - Required for docker/podman CLI interaction, inputs are strictly controlled and resolved via shutil.which
import tarfile
import tempfile

from pathlib import Path
from typing import Any, ClassVar, override

from seraph.guard.orchestration.discovery import RepoDiscovery
from seraph.guard.scanners.base import (
    BlastRadius,
    Category,
    Finding,
    ScanContext,
    Scanner,
    Severity,
)
from seraph.guard.scanners.pattern import PatternScanner
from seraph.guard.scanners.sbom import SBOMScanner
from seraph.guard.scanners.secret import AdvancedSecretScanner


logger = logging.getLogger(__name__)

MAX_FILE_SIZE = 50 * 1024 * 1024

BINARY_EXTENSIONS = {
    ".so",
    ".a",
    ".o",
    ".rlib",
    ".dll",
    ".dylib",
    ".exe",
    ".bin",
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".bmp",
    ".ico",
    ".svg",
    ".webp",
    ".mp3",
    ".mp4",
    ".avi",
    ".mov",
    ".wmv",
    ".flv",
    ".wav",
    ".ogg",
    ".zip",
    ".tar",
    ".gz",
    ".bz2",
    ".xz",
    ".7z",
    ".rar",
    ".deb",
    ".rpm",
    ".woff",
    ".woff2",
    ".ttf",
    ".eot",
    ".otf",
    ".pyc",
    ".pyo",
    ".class",
    ".jar",
    ".war",
}


class ContainerScanner(Scanner):
    name = "ContainerScanner"
    version = "2.0.0"
    categories: ClassVar[list[Category]] = [
        Category.SECRET,
        Category.VULNERABILITY,
        Category.POLICY,
        Category.PATTERN,
    ]

    def __init__(self, image: str | None = None, timeout: int = 300) -> None:
        self.image = image
        self.timeout = timeout
        self.temp_dir: Path | None = None

        # Resolve docker/podman binary path to prevent PATH hijacking (Bandit B603/B607)
        docker_bin = shutil.which("docker") or shutil.which("podman")
        if docker_bin is None:
            msg = "docker or podman executable not found in PATH"
            raise RuntimeError(msg)
        self._docker_bin: str = docker_bin

    @override
    def is_applicable(self, context: ScanContext) -> bool:
        return bool(self.image)

    @override
    async def scan(self, context: ScanContext) -> list[Finding]:
        if not self.image:
            return []

        findings: list[Finding] = []
        logger.info("ContainerScanner: Pulling and unpacking image: %s", self.image)

        try:
            rootfs_path, image_config = self._unpack_image(self.image)
            if not rootfs_path:
                return [self._make_pull_failed_finding("Image unpack produced no filesystem")]

            file_count = sum(1 for _ in rootfs_path.rglob("*") if _.is_file())
            logger.info(
                "ContainerScanner: Unpacked %s → %d files at %s",
                self.image,
                file_count,
                rootfs_path,
            )

            if image_config:
                findings.extend(self._analyze_image_config(image_config))

            rootfs_context = ScanContext(
                path=str(rootfs_path), is_git_repo=False, config=context.config, profile=None
            )
            try:
                discovery = RepoDiscovery(rootfs_path)
                profile = discovery.discover()
                rootfs_context.profile = profile
            except Exception as e:
                logger.debug("ContainerScanner: Discovery failed: %s", e)

            secret_scanner = AdvancedSecretScanner(min_entropy=4.0, git_history=False)
            pattern_scanner = PatternScanner()
            sbom_scanner = SBOMScanner(timeout=60)

            findings.extend(await secret_scanner.scan(rootfs_context))
            findings.extend(await pattern_scanner.scan(rootfs_context))
            findings.extend(await sbom_scanner.scan(rootfs_context))

            for f in findings:
                f.metadata["container_image"] = self.image
                if f.file:
                    f.file = f"container://{self.image}:{f.file}"

        except Exception as e:
            logger.error("ContainerScanner: Failed to scan %s: %s", self.image, e)
            findings.append(self._make_pull_failed_finding(str(e)))
        finally:
            self._cleanup()

        logger.info("ContainerScanner: Found %d issues in %s", len(findings), self.image)
        return findings

    def _analyze_image_config(self, config: dict[str, Any]) -> list[Finding]:
        findings: list[Finding] = []
        user = config.get("User", "") or config.get("config", {}).get("User", "")

        if not user or user in ("0", "0:0", "root"):
            findings.append(
                Finding(
                    scanner=self.name,
                    category=Category.POLICY,
                    severity=Severity.MEDIUM,
                    confidence=0.95,
                    file=f"container://{self.image}:Dockerfile/config",
                    line=0,
                    title="Container Runs as Root",
                    description="Container image has no USER directive or runs as root (uid 0). This increases the impact of container escape vulnerabilities.",
                    evidence=f"User: '{user or '(empty)'}'",
                    fix_available=True,
                    fix_command="Add USER <non-root-uid> to the Dockerfile",
                    blast_radius=BlastRadius(
                        blast_radius_score=0.6, reduction_if_fixed=0.5, is_assessed=True
                    ),
                    metadata={"container_image": self.image, "check": "user"},
                )
            )

        env_vars = config.get("config", {}).get("Env", []) or config.get("Env", [])
        sensitive_patterns = [
            (r"(?i)AWS_ACCESS_KEY", "AWS Access Key", Severity.HIGH),
            (r"(?i)AWS_SECRET", "AWS Secret Key", Severity.HIGH),
            (r"(?i)SECRET_KEY", "Generic Secret Key", Severity.HIGH),
            (r"(?i)PASSWORD", "Password", Severity.HIGH),
            (r"(?i)PRIVATE_KEY", "Private Key", Severity.HIGH),
            (r"(?i)TOKEN", "Auth Token", Severity.MEDIUM),
            (r"(?i)API_KEY", "API Key", Severity.HIGH),
            (r"(?i)DATABASE_URL", "Database Connection String", Severity.MEDIUM),
            (r"(?i)MONGO_URI", "MongoDB Connection String", Severity.MEDIUM),
            (r"(?i)REDIS_URL", "Redis Connection String", Severity.MEDIUM),
        ]

        for env in env_vars:
            if not isinstance(env, str):
                continue
            for pattern, name, severity in sensitive_patterns:
                if re.search(pattern, env):
                    key_name = env.split("=", 1)[0] if "=" in env else env
                    findings.append(
                        Finding(
                            scanner=self.name,
                            category=Category.SECRET,
                            severity=severity,
                            confidence=0.8,
                            file=f"container://{self.image}:image-config",
                            line=0,
                            title=f"Sensitive Env Var in Image: {name}",
                            description=f"Environment variable '{key_name}' matches a sensitive pattern. Secrets baked into images are visible to anyone who pulls the image.",
                            evidence=f"ENV {key_name}=***REDACTED***",
                            fix_available=True,
                            fix_command=f"Remove {key_name} from the image. Use runtime env vars or a secrets manager.",
                            metadata={
                                "container_image": self.image,
                                "check": "env",
                                "env_key": key_name,
                            },
                        )
                    )
                    break

        exposed_ports = config.get("config", {}).get("ExposedPorts", {}) or config.get(
            "ExposedPorts", {}
        )
        dangerous_ports = {
            "22/tcp": ("SSH", Severity.HIGH),
            "2375/tcp": ("Docker Daemon", Severity.CRITICAL),
            "2376/tcp": ("Docker Daemon TLS", Severity.CRITICAL),
            "3306/tcp": ("MySQL", Severity.MEDIUM),
            "5432/tcp": ("PostgreSQL", Severity.MEDIUM),
            "6379/tcp": ("Redis", Severity.MEDIUM),
            "27017/tcp": ("MongoDB", Severity.MEDIUM),
            "9200/tcp": ("Elasticsearch", Severity.MEDIUM),
            "8080/tcp": ("HTTP Alt", Severity.LOW),
        }

        for port, info in dangerous_ports.items():
            if port in exposed_ports:
                service_name, sev = info
                findings.append(
                    Finding(
                        scanner=self.name,
                        category=Category.POLICY,
                        severity=sev,
                        confidence=0.9,
                        file=f"container://{self.image}:Dockerfile/EXPOSE",
                        line=0,
                        title=f"Dangerous Port Exposed: {port} ({service_name})",
                        description=f"Port {port} ({service_name}) is exposed in the image. This should typically only be accessible within the container network.",
                        evidence=f"EXPOSE {port}",
                        fix_available=False,
                        fix_command=f"Remove EXPOSE {port} or use Docker network policies to restrict access.",
                        metadata={"container_image": self.image, "check": "ports", "port": port},
                    )
                )

        health = config.get("config", {}).get("Healthcheck", {})
        if not health:
            findings.append(
                Finding(
                    scanner=self.name,
                    category=Category.POLICY,
                    severity=Severity.LOW,
                    confidence=0.8,
                    file=f"container://{self.image}:Dockerfile/HEALTHCHECK",
                    line=0,
                    title="No Health Check Defined",
                    description="Container image has no HEALTHCHECK directive. Orchestrators cannot determine if the container is healthy.",
                    evidence="",
                    fix_available=True,
                    fix_command="Add HEALTHCHECK --interval=30s CMD curl -f http://localhost/ || exit 1",
                    metadata={"container_image": self.image, "check": "healthcheck"},
                )
            )
        return findings

    def _make_pull_failed_finding(self, reason: str) -> Finding:
        return Finding(
            scanner=self.name,
            category=Category.SECRET,
            severity=Severity.HIGH,
            confidence=1.0,
            file=self.image or "unknown",
            line=0,
            title=f"Container Scan Failed: {self.image}",
            description=reason,
            evidence="",
            fix_available=False,
            fix_command="Ensure Docker is running and the image name is correct.",
            metadata={"container_image": self.image or "unknown"},
        )

    @staticmethod
    def _safe_extract(tar: tarfile.TarFile, path: Path) -> None:
        """Safely extract tar members, preventing directory traversal and symlink attacks."""
        base = path.resolve()
        for member in tar.getmembers():
            # Sanitize name to prevent absolute paths
            clean_name = member.name.lstrip("/")
            target = (base / clean_name).resolve()

            # Ensure the resolved target is strictly within the base directory
            if not target.is_relative_to(base):
                continue  # skip anything that escapes the target dir

            # Skip symlinks/hardlinks entirely, simplest safe policy
            if member.issym() or member.islnk():
                continue

            tar.extract(member, path)

    def _unpack_image(self, image: str) -> tuple[Path | None, dict[str, Any] | None]:
        self.temp_dir = Path(tempfile.mkdtemp(prefix="seraph_container_"))
        tar_path = self.temp_dir / "image.tar"
        rootfs_path = self.temp_dir / "rootfs"
        rootfs_path.mkdir(parents=True, exist_ok=True)
        image_config: dict[str, Any] | None = None
        config_member_path: Path | None = None

        try:
            logger.info("  [1/4] Pulling image %s...", image)
            pull_result = subprocess.run(  # nosec B603 - executable resolved via shutil.which, args passed as list, no shell
                [self._docker_bin, "pull", image],
                capture_output=True,
                text=True,
                timeout=self.timeout,
                check=False,
            )
            if pull_result.returncode != 0:
                logger.error("  Docker pull failed: %s", pull_result.stderr.strip())
                return None, None

            logger.info("  [2/4] Saving image to tar...")
            save_result = subprocess.run(  # nosec B603 - executable resolved via shutil.which, args passed as list, no shell
                [self._docker_bin, "save", "-o", str(tar_path), image],
                capture_output=True,
                text=True,
                timeout=self.timeout,
                check=False,
            )
            if save_result.returncode != 0:
                logger.error("  Docker save failed: %s", save_result.stderr.strip())
                return None, None

            if not tar_path.exists() or tar_path.stat().st_size == 0:
                logger.error("  Docker save produced empty tar")
                return None, None

            logger.info("  [3/4] Extracting image layers...")
            with tarfile.open(tar_path, "r") as tar:
                manifest_member = None
                config_member = None
                for member in tar.getmembers():
                    if member.name == "manifest.json":
                        manifest_member = member
                    elif member.name.endswith(".json") and "config" in member.name:
                        config_member = member

                if manifest_member:
                    manifest_data = tar.extractfile(manifest_member)
                    if manifest_data:
                        manifest = json.loads(manifest_data.read().decode())
                        if manifest:
                            config_file = manifest[0].get("Config", "")
                            if config_file:
                                config_member_path = self.temp_dir / config_file

                try:
                    # Python 3.12+ safe extraction
                    tar.extractall(path=self.temp_dir, filter="data")
                except TypeError:
                    # Fallback for older Python versions or unexpected TypeErrors:
                    # Manually validate and extract to prevent directory traversal / tar slip
                    self._safe_extract(tar, self.temp_dir)

                if config_member:
                    config_path = self.temp_dir / config_member.name
                    if config_path.exists():
                        image_config = json.loads(config_path.read_text(encoding="utf-8"))
                elif config_member_path and config_member_path.exists():
                    image_config = json.loads(config_member_path.read_text(encoding="utf-8"))

                logger.info("  [4/4] Unpacking layers into rootfs...")
                manifest_path = self.temp_dir / "manifest.json"
                layers: list[str] = []
                if manifest_path.exists():
                    manifest = json.loads(manifest_path.read_text())
                    if manifest:
                        layers = manifest[0].get("Layers", [])

                for layer_rel in layers:
                    layer_tar = self.temp_dir / layer_rel
                    if not layer_tar.exists():
                        logger.warning("  Layer not found: %s", layer_rel)
                        continue

                    try:
                        with tarfile.open(layer_tar, "r") as l_tar:
                            for member in l_tar.getmembers():
                                name = member.name
                                if "/.wh." in name:
                                    whiteout_name = name.split("/.wh.")[-1]
                                    # Safe whiteout resolution
                                    clean_whiteout = whiteout_name.lstrip("/")
                                    if ".." in clean_whiteout.split("/"):
                                        continue
                                    whiteout_path = (rootfs_path / clean_whiteout).resolve()
                                    if (
                                        whiteout_path.is_relative_to(rootfs_path)
                                        and whiteout_path.exists()
                                        and whiteout_path.is_file()
                                    ):
                                        whiteout_path.unlink()
                                    continue

                                if not member.isfile():
                                    continue
                                if member.size > MAX_FILE_SIZE:
                                    continue
                                ext = Path(name).suffix.lower()
                                if ext in BINARY_EXTENSIONS:
                                    continue

                                # Safe path resolution
                                clean_name = name.lstrip("/")
                                if ".." in clean_name.split("/"):
                                    continue

                                target_path = (rootfs_path / clean_name).resolve()
                                if not target_path.is_relative_to(rootfs_path):
                                    continue

                                target_path.parent.mkdir(parents=True, exist_ok=True)
                                try:
                                    # Read and write manually to completely avoid tar.extract vulnerabilities
                                    src_file = l_tar.extractfile(member)
                                    if src_file is not None:
                                        with src_file as src, open(target_path, "wb") as dst:
                                            shutil.copyfileobj(src, dst)
                                except (PermissionError, OSError, AttributeError) as e:
                                    logger.debug("  Skip file %s: %s", clean_name, e)
                    except (tarfile.TarError, Exception) as e:
                        logger.warning("  Failed to extract layer %s: %s", layer_rel, e)

                file_count = sum(1 for _ in rootfs_path.rglob("*") if _.is_file())
                if file_count == 0:
                    logger.error("  Rootfs is empty after extraction")
                    return None, image_config

                logger.info("  Unpacked %d files from %d layers", file_count, len(layers))
                return rootfs_path, image_config

        except subprocess.TimeoutExpired:
            logger.error("  Docker command timed out for image %s", image)
            return None, None
        except subprocess.CalledProcessError as e:
            logger.error("  Docker command failed: %s", e.stderr)
            return None, None
        except json.JSONDecodeError as e:
            logger.error("  Failed to parse image manifest/config: %s", e)
            return None, None
        except Exception:
            logger.exception("  Failed to unpack image")
            return None, None

    def _cleanup(self) -> None:
        if self.temp_dir and self.temp_dir.exists():
            try:
                shutil.rmtree(self.temp_dir, ignore_errors=True)
            except Exception as e:
                logger.warning("  Failed to cleanup temp dir: %s", e)
