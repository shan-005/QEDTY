#!/usr/bin/env python3
"""
Single-name repository identity migration.

Edit NEW_NAME to the desired standalone project name and run from the WSL
repository root:

    python3 rename_project_identity.py
    python3 rename_project_identity.py --approve

The old project identity is inferred from pyproject.toml and the source package;
this keeps the script reusable for a future rename without hard-coding today's
old project name into the migration tool.

The migration changes identity-bearing names and references only. It does not
redesign algorithms, contracts, schemas, architecture, or test semantics.
Git history is never modified. Build/cache directories are regenerated instead
of rewritten.
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import stat
import subprocess
import sys
import tarfile
import tempfile
import tomllib
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import NoReturn

# -----------------------------------------------------------------------------
# ONLY EDIT THIS VALUE for the next standalone project name.
# -----------------------------------------------------------------------------
NEW_NAME = "QEDTY"

# Repository/build areas that should never be rewritten as source identity.
EXCLUDED_DIRS = {
    ".git", ".venv", "venv", "env", ".tox", ".nox", "__pycache__",
    ".pytest_cache", ".mypy_cache", ".ruff_cache", ".coverage_cache", "htmlcov",
    "dist", "build", "target", "node_modules", ".cache", ".cargo",
    ".seraph-cache", ".seraph-learn", ".qedty-cache", ".qedty-learn",
}
EXCLUDED_SUFFIXES = {
    ".pyc", ".pyo", ".so", ".dll", ".dylib", ".a", ".rlib", ".rmeta",
    ".o", ".obj", ".exe", ".bin", ".db", ".sqlite", ".sqlite3",
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".pdf", ".zip",
    ".tar", ".gz", ".bz2", ".xz", ".7z", ".woff", ".woff2", ".ttf",
    ".lockb", ".parquet", ".feather", ".arrow", ".wasm",
}


@dataclass(frozen=True)
class Change:
    old: Path
    new: Path


def die(message: str) -> NoReturn:
    print(f"ERROR: {message}", file=sys.stderr)
    raise RuntimeError(message)


def root_dir() -> Path:
    try:
        value = subprocess.check_output(
            ["git", "rev-parse", "--show-toplevel"],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
        if value:
            return Path(value).resolve()
    except (OSError, subprocess.CalledProcessError):
        pass
    return Path.cwd().resolve()


def read_project_name(root: Path) -> str | None:
    p = root / "pyproject.toml"
    if not p.is_file():
        return None
    try:
        data = tomllib.loads(p.read_text(encoding="utf-8"))
        value = data.get("project", {}).get("name")
        return value if isinstance(value, str) and value.strip() else None
    except (OSError, tomllib.TOMLDecodeError):
        return None


def discover_old_brand(root: Path) -> tuple[str, str]:
    """Return (old full project name, old base brand) without hard-coding it."""
    project = read_project_name(root)
    if project:
        raw = project.strip()
    else:
        raw = ""

    if not raw:
        # Fallback: use the most plausible import package under src/.
        src = root / "src"
        candidates = []
        if src.is_dir():
            for p in src.iterdir():
                if p.is_dir() and (p / "__init__.py").is_file() and not p.name.endswith(".egg-info"):
                    candidates.append(p.name)
        if candidates:
            raw = sorted(candidates)[0]

    if not raw:
        die("cannot infer the current project identity from pyproject.toml or src/")

    normalized = raw.lower().replace("_", "-")
    base = re.sub(r"-(?:pci-?x|core)$", "", normalized)
    base = base.strip("-_")
    if not base:
        die(f"could not infer base brand from project identity {raw!r}")
    return raw, base


def style_variants(token: str) -> dict[str, str]:
    """Return exact spelling variants for a token."""
    lower = token.lower()
    upper = token.upper()
    title = token[:1].upper() + token[1:].lower() if token else token
    return {lower: NEW_LOWER, upper: NEW_UPPER, title: NEW_TITLE}


def make_replacements(old_project: str, old_brand: str) -> tuple[tuple[str, str], ...]:
    """Build a longest-first replacement table for path and text identities."""
    old_project_lower = old_project.lower()
    old_project_hyphen = old_project_lower.replace("_", "-")
    old_brand_lower = old_brand.lower().replace("_", "-")

    source_tokens = {
        old_project_lower,
        old_project_lower.replace("-", "_"),
        old_project_hyphen,
        old_project_hyphen.replace("-", "_"),
        old_brand_lower,
        old_brand_lower.replace("-", "_"),
    }

    # Add separator/case variants of the known current naming families.
    for sep in ("-", "_"):
        source_tokens.add(f"{old_brand_lower}{sep}pci{sep}x")
        source_tokens.add(f"{old_brand_lower}{sep}core")

    # Case variants. Preserve the user's desired standalone name at the
    # destination, using matching upper/title/lower forms.
    pairs: list[tuple[str, str]] = []
    for token in sorted(source_tokens, key=len, reverse=True):
        lower = token.lower()
        upper = token.upper()
        title = token[:1].upper() + token[1:].lower()
        if lower not in {"", NEW_LOWER}:
            pairs.extend(((upper, NEW_UPPER), (title, NEW_TITLE), (lower, NEW_LOWER)))

    # Deduplicate while keeping longest-first behavior.
    unique: dict[str, str] = {}
    for old, new in sorted(pairs, key=lambda pair: len(pair[0]), reverse=True):
        if old and old != new and old not in unique:
            unique[old] = new
    return tuple(unique.items())


def is_excluded(root: Path, path: Path) -> bool:
    try:
        rel = path.relative_to(root)
    except ValueError:
        return True
    return any(part in EXCLUDED_DIRS for part in rel.parts)


def is_text_file(root: Path, path: Path) -> bool:
    if not path.is_file() or is_excluded(root, path):
        return False
    if path.suffix.lower() in EXCLUDED_SUFFIXES:
        return False
    try:
        data = path.read_bytes()
    except OSError:
        return False
    return b"\x00" not in data


def transform_name(name: str, replacements: tuple[tuple[str, str], ...]) -> str:
    result = name
    for old, new in replacements:
        result = result.replace(old, new)
    return result


def transformed_path(rel: Path, replacements: tuple[tuple[str, str], ...]) -> Path:
    return Path(*(transform_name(part, replacements) for part in rel.parts))


def discover_changes(root: Path, replacements: tuple[tuple[str, str], ...]) -> tuple[list[Change], list[Change]]:
    dirs: list[Change] = []
    files: list[Change] = []
    for path in root.rglob("*"):
        if is_excluded(root, path):
            continue
        rel = path.relative_to(root)
        new_rel = transformed_path(rel, replacements)
        if new_rel == rel:
            continue
        change = Change(rel, new_rel)
        (dirs if path.is_dir() else files).append(change)

    dirs.sort(key=lambda c: (len(c.old.parts), str(c.old)), reverse=True)
    files.sort(key=lambda c: (len(c.old.parts), str(c.old)), reverse=True)
    return dirs, files


def select_root_dir_changes(changes: list[Change]) -> list[Change]:
    """Do not rename descendants separately when their renamed parent moves them."""
    selected: list[Change] = []
    old_paths = {c.old for c in changes}
    for ch in sorted(changes, key=lambda c: (len(c.old.parts), str(c.old))):
        if any(ch.old != ancestor and ancestor in old_paths for ancestor in ch.old.parents):
            continue
        selected.append(ch)
    return sorted(selected, key=lambda c: (len(c.old.parts), str(c.old)), reverse=True)


def find_old_text(root: Path, old_re: re.Pattern[str]) -> list[tuple[Path, int, str]]:
    hits: list[tuple[Path, int, str]] = []
    for path in root.rglob("*"):
        if not is_text_file(root, path):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for line_no, line in enumerate(text.splitlines(), 1):
            if old_re.search(line):
                hits.append((path.relative_to(root), line_no, line))
    return hits


def find_forbidden_new(root: Path, forbidden: tuple[str, ...]) -> list[tuple[Path, int, str]]:
    hits: list[tuple[Path, int, str]] = []
    for path in root.rglob("*"):
        if not is_text_file(root, path):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for line_no, line in enumerate(text.splitlines(), 1):
            if any(token in line for token in forbidden):
                hits.append((path.relative_to(root), line_no, line))
    return hits


def old_path_hits(root: Path, old_re: re.Pattern[str]) -> list[Path]:
    result = []
    for path in root.rglob("*"):
        if is_excluded(root, path):
            continue
        if old_re.search(path.name):
            result.append(path.relative_to(root))
    return result


def snapshot(root: Path) -> Path:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = Path(tempfile.gettempdir()) / f"qedty_identity_backup_{stamp}.tar.gz"

    def filt(info: tarfile.TarInfo) -> tarfile.TarInfo | None:
        parts = Path(info.name).parts
        if parts and parts[0] in EXCLUDED_DIRS:
            return None
        if Path(info.name).suffix.lower() in EXCLUDED_SUFFIXES:
            return None
        return info

    with tarfile.open(backup, "w:gz", dereference=False) as tf:
        for child in root.iterdir():
            if child.name == ".git" or child.name in EXCLUDED_DIRS:
                continue
            tf.add(child, arcname=child.name, recursive=True, filter=filt)
    return backup


def restore(root: Path, backup: Path) -> None:
    print(f"Restoring pre-migration tree from {backup}", file=sys.stderr)
    for child in list(root.iterdir()):
        if child.name == ".git":
            continue
        try:
            if child.is_dir() and not child.is_symlink():
                shutil.rmtree(child)
            else:
                child.unlink()
        except FileNotFoundError:
            pass
    with tarfile.open(backup, "r:gz") as tf:
        tf.extractall(root)


def rename_dirs(root: Path, changes: list[Change]) -> None:
    for ch in select_root_dir_changes(changes):
        old = root / ch.old
        new = root / ch.new
        if not old.exists():
            die(f"directory disappeared: {ch.old}")
        if new.exists():
            die(f"directory destination already exists: {ch.new}")
        new.parent.mkdir(parents=True, exist_ok=True)
        old.rename(new)


def rename_files(root: Path, replacements: tuple[tuple[str, str], ...]) -> None:
    _, files = discover_changes(root, replacements)
    # A file is now reached at its post-directory-rename location. Only its
    # basename/path components that still contain the old identity need moving.
    for ch in files:
        old = root / ch.old
        new = root / ch.new
        if not old.exists():
            die(f"file disappeared: {ch.old}")
        if new.exists():
            die(f"file destination already exists: {ch.new}")
        new.parent.mkdir(parents=True, exist_ok=True)
        old.rename(new)


def rewrite_text(root: Path, replacements: tuple[tuple[str, str], ...]) -> None:
    for path in root.rglob("*"):
        if not is_text_file(root, path):
            continue
        try:
            before = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        after = before
        for old, new in replacements:
            after = after.replace(old, new)
        if after == before:
            continue
        mode = stat.S_IMODE(path.stat().st_mode)
        temp = path.with_name(path.name + ".qedty-migration-tmp")
        temp.write_text(after, encoding="utf-8", newline="")
        os.chmod(temp, mode)
        temp.replace(path)


def remove_generated(root: Path) -> None:
    for rel in (
        Path(".coverage"), Path("htmlcov"), Path("dist"), Path("build"),
        Path(".pytest_cache"), Path(".mypy_cache"), Path(".ruff_cache"),
        Path(f"src/{NEW_LOWER}.egg-info"), Path(f"crates/{NEW_LOWER}/target"),
    ):
        path = root / rel
        if path.exists():
            shutil.rmtree(path) if path.is_dir() and not path.is_symlink() else path.unlink()


def run(label: str, command: list[str], cwd: Path) -> None:
    print(f"==> {label}")
    print("    " + " ".join(command))
    subprocess.run(command, cwd=cwd, check=True)


def validate(root: Path, old_re: re.Pattern[str], forbidden: tuple[str, ...]) -> None:
    required = (
        root / f"src/{NEW_LOWER}",
        root / f"proto/{NEW_LOWER}",
        root / f"contracts/{NEW_LOWER}",
        root / f"crates/{NEW_LOWER}",
        root / "pyproject.toml",
        root / "README.md",
    )
    for path in required:
        if not path.exists():
            die(f"required path missing: {path.relative_to(root)}")

    pyproject = read_project_name(root)
    if pyproject and pyproject.lower().replace("_", "-") != NEW_LOWER:
        die(f"pyproject project name is {pyproject!r}; expected {NEW_LOWER!r}")

    cargo = root / f"crates/{NEW_LOWER}/Cargo.toml"
    if cargo.is_file():
        text = cargo.read_text(encoding="utf-8")
        match = re.search(r"^name\s*=\s*\"([^\"]+)\"", text, re.MULTILINE)
        if not match or match.group(1) != NEW_LOWER:
            die(f"Rust package name is not exactly {NEW_LOWER!r}")

    leftovers = find_old_text(root, old_re)
    paths = old_path_hits(root, old_re)
    forbidden_hits = find_forbidden_new(root, forbidden)
    if leftovers or paths or forbidden_hits:
        print("IDENTITY VALIDATION FAILED", file=sys.stderr)
        for p, n, line in leftovers[:200]:
            print(f"  OLD TEXT  {p}:{n}: {line}", file=sys.stderr)
        for p in paths[:200]:
            print(f"  OLD PATH  {p}", file=sys.stderr)
        for p, n, line in forbidden_hits[:200]:
            print(f"  FORBIDDEN {p}:{n}: {line}", file=sys.stderr)
        die("old identity or forbidden derived QEDTY identity remains")

    if shutil.which("uv") is None:
        die("uv is required for the Python validation contract")
    run("uv lock", ["uv", "lock"], root)
    run("uv sync", ["uv", "sync"], root)
    run("ruff check", ["uv", "run", "ruff", "check", "src", "tests"], root)
    run("ruff format", ["uv", "run", "ruff", "format", "--check", "src", "tests"], root)

    if subprocess.run(
        ["uv", "run", "basedpyright", "--version"], cwd=root, check=False
    ).returncode == 0:
        run("basedpyright", ["uv", "run", "basedpyright"], root)

    run("pytest", ["uv", "run", "pytest", "-q"], root)

    if cargo.is_file():
        if shutil.which("cargo") is None:
            die("cargo is required because a Rust crate exists")
        cwd = root / f"crates/{NEW_LOWER}"
        run("cargo fmt", ["cargo", "fmt", "--check"], cwd)
        run("cargo check", ["cargo", "check"], cwd)
        run("cargo test", ["cargo", "test"], cwd)

    verify = root / "scripts/verify.sh"
    if verify.is_file():
        if not os.access(verify, os.X_OK):
            verify.chmod(verify.stat().st_mode | stat.S_IXUSR)
        run("scripts/verify.sh", [str(verify)], root)

    makefile = root / "Makefile"
    if makefile.is_file() and shutil.which("make"):
        make_text = makefile.read_text(encoding="utf-8", errors="ignore")
        if re.search(r"(?m)^check\s*:", make_text):
            run("make check", ["make", "check"], root)

    # Final scan after uv/cargo/generated metadata has run.
    if find_old_text(root, old_re) or old_path_hits(root, old_re) or find_forbidden_new(root, forbidden):
        die("post-validation identity scan failed")


def main() -> int:
    parser = argparse.ArgumentParser(description="Rename the repository to one standalone project name.")
    parser.add_argument("--approve", action="store_true", help="perform migration and full validation")
    parser.add_argument("--keep-backup", action="store_true", help="keep the temporary backup archive")
    args = parser.parse_args()

    root = root_dir()
    if not (root / ".git").is_dir():
        die("run this from inside the repository")

    new_upper = NEW_NAME.upper()
    new_lower = NEW_NAME.lower().replace(" ", "-").replace("_", "-")
    new_title = NEW_NAME[:1].upper() + NEW_NAME[1:].lower()
    globals()["NEW_UPPER"] = new_upper
    globals()["NEW_LOWER"] = new_lower
    globals()["NEW_TITLE"] = new_title

    old_project, old_brand = discover_old_brand(root)
    replacements = make_replacements(old_project, old_brand)

    # Build regex only from inferred current identity, so this migration tool
    # does not retain a hard-coded old brand after the migration.
    old_tokens = sorted({old for old, _ in replacements if old}, key=len, reverse=True)
    old_re = re.compile("|".join(re.escape(x) for x in old_tokens))
    forbidden = (
        f"{new_upper}-PCI-X",
        f"{new_upper}_PCI_X",
        f"{new_lower}-pci-x",
        f"{new_lower}_pci_x",
        f"{new_upper}-CORE",
        f"{new_upper}_CORE",
        f"{new_lower}-core",
        f"{new_lower}_core",
    )

    print("Single-name identity migration")
    print("===============================")
    print(f"Repository : {root}")
    print(f"Old identity: {old_project}  (base: {old_brand})")
    print(f"New identity: {new_upper}  (package: {new_lower}, Rust crate: {new_lower})")
    print("No derived PCI-X/Core identity will be created.")
    print()

    dirs, files = discover_changes(root, replacements)
    effective_dirs = select_root_dir_changes(dirs)
    print(f"Preflight path changes: {len(files)} files + {len(effective_dirs)} directories")
    for ch in effective_dirs:
        print(f"  DIR  {ch.old} -> {ch.new}")
    for ch in files:
        print(f"  FILE {ch.old} -> {ch.new}")

    if not args.approve:
        print("\nPreflight only. Re-run with --approve to execute the migration.")
        return 0

    # Pre-mutation destination collision check.
    moving_old = {ch.old for ch in dirs + files}
    for ch in effective_dirs + files:
        target = root / ch.new
        if target.exists() and ch.new not in moving_old:
            die(f"destination already exists: {ch.new}")

    backup = snapshot(root)
    print(f"Backup: {backup}")

    try:
        rename_dirs(root, dirs)
        rename_files(root, replacements)
        rewrite_text(root, replacements)
        remove_generated(root)
        validate(root, old_re, forbidden)
    except BaseException:
        try:
            restore(root, backup)
        except BaseException as restore_error:
            print(f"CRITICAL: automatic restore failed: {restore_error}", file=sys.stderr)
            print(f"Manual backup remains at: {backup}", file=sys.stderr)
        else:
            print("Automatic restore completed.", file=sys.stderr)
        raise

    print("\nMIGRATION PASSED")
    print("================")
    subprocess.run(["git", "status", "--short"], cwd=root, check=False)
    if args.keep_backup:
        print(f"Backup kept: {backup}")
    else:
        backup.unlink(missing_ok=True)
        print("Temporary backup removed after successful validation.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("Interrupted.", file=sys.stderr)
        raise SystemExit(130)
