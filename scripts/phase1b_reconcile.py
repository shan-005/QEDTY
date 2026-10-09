#!/usr/bin/env python3
"""QEDTY Phase 1B repository reconciliation and baseline generator.

Standard-library only. Run from the QEDTY repository root:

    uv run python scripts/phase1b_reconcile.py
    uv run python scripts/phase1b_reconcile.py --run-tests

The script:
- removes UTF-8 BOMs from tracked text files;
- fixes the legacy IRIN-0/QEDTY repository URL in tracked text;
- validates the repository against GitHub main's recursive Git tree;
- regenerates QEDTY-PROJECT-MANIFEST.json from the actual local Git index;
- checks that generated artifacts are not tracked;
- reports exact local-vs-remote file differences.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import urllib.request
from collections import Counter
from datetime import date
from pathlib import Path

REPO = "shan-005/QEDTY"
BRANCH = "main"
TREE_API = f"https://api.github.com/repos/{REPO}/git/trees/{BRANCH}?recursive=1"
TEXT_EXTENSIONS = {
    ".py",
    ".pyi",
    ".rs",
    ".toml",
    ".json",
    ".jsonld",
    ".ttl",
    ".yaml",
    ".yml",
    ".md",
    ".txt",
    ".sh",
    ".proto",
    ".cff",
    ".ini",
    ".cfg",
    ".xml",
    ".csv",
}
TEXT_FILENAMES = {
    ".gitignore",
    ".python-version",
    "CODEOWNERS",
    "LICENSE",
    "Makefile",
    "CITATION.cff",
    "CHANGELOG.md",
    "README.md",
    "SECURITY.md",
    "SUPPORT.md",
    "CONTRIBUTING.md",
    "CODE_OF_CONDUCT.md",
}


def git_files() -> list[str]:
    raw = subprocess.run(
        ["git", "ls-files", "-z"],
        check=True,
        capture_output=True,
    ).stdout
    return sorted(x.decode("utf-8") for x in raw.split(b"\0") if x)


def is_text_path(path: str) -> bool:
    p = Path(path)
    return p.name in TEXT_FILENAMES or p.suffix.lower() in TEXT_EXTENSIONS


def canonicalize_repository_urls(text: str) -> str:
    """Rewrite legacy repository URLs without altering historical product names."""
    replacements = (
        ("https://github.com/IRIN-0/qedty", f"https://github.com/{REPO}"),
        ("https://github.com/IRIN-0/QEDTY", f"https://github.com/{REPO}"),
        ("http://github.com/IRIN-0/qedty", f"https://github.com/{REPO}"),
        ("http://github.com/IRIN-0/QEDTY", f"https://github.com/{REPO}"),
        ("github.com/IRIN-0/qedty", f"github.com/{REPO}"),
        ("github.com/IRIN-0/QEDTY", f"github.com/{REPO}"),
    )
    for old, new in replacements:
        text = text.replace(old, new)
    return text


def clean_text_files(repo: Path, tracked: list[str]) -> tuple[list[str], list[str]]:
    bom_fixed: list[str] = []
    legacy_fixed: list[str] = []

    for rel in tracked:
        if not is_text_path(rel):
            continue
        path = repo / rel
        if not path.is_file():
            continue

        original = path.read_bytes()
        data = original[3:] if original.startswith(b"\xef\xbb\xbf") else original
        if data != original:
            bom_fixed.append(rel)

        try:
            decoded = data.decode("utf-8")
        except UnicodeDecodeError:
            if data != original:
                path.write_bytes(data)
            continue

        new_text = canonicalize_repository_urls(decoded)
        if new_text != decoded:
            legacy_fixed.append(rel)
        desired = new_text.encode("utf-8")
        if desired != original:
            path.write_bytes(desired)

    return bom_fixed, legacy_fixed

def fetch_remote_files() -> tuple[str, set[str]]:
    req = urllib.request.Request(
        TREE_API,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "QEDTY-phase1b-reconciler",
        },
    )
    with urllib.request.urlopen(req, timeout=20) as r:
        payload = json.load(r)
    if payload.get("truncated"):
        raise RuntimeError("GitHub recursive tree is truncated; refusing to claim parity.")
    tree_sha = str(payload["sha"])
    files = {x["path"] for x in payload["tree"] if x.get("type") == "blob"}
    return tree_sha, files


def file_inventory(files: list[str]) -> dict[str, object]:
    by_ext = Counter()
    by_root = Counter()
    for rel in files:
        p = Path(rel)
        ext = p.suffix.lower() if p.suffix else "<no-extension>"
        by_ext[ext] += 1
        by_root[p.parts[0] if p.parts else "."] += 1

    python = by_ext[".py"]
    rust = by_ext[".rs"]
    proto = by_ext[".proto"]
    markdown = by_ext[".md"]
    json_count = by_ext[".json"]
    ttl = by_ext[".ttl"]
    yaml = by_ext[".yaml"] + by_ext[".yml"]
    shell = by_ext[".sh"]

    return {
        "python_files": python,
        "rust_files": rust,
        "protobuf_files": proto,
        "markdown_files": markdown,
        "json_files": json_count,
        "turtle_files": ttl,
        "yaml_files": yaml,
        "shell_files": shell,
        "root_counts": dict(sorted(by_root.items())),
        "extension_counts": dict(sorted(by_ext.items())),
    }


def write_manifest(repo: Path, local_files: list[str]) -> dict[str, object]:
    """Write stable inventory data, not self-referential commit/tree metadata."""
    inv = file_inventory(local_files)
    manifest: dict[str, object] = {
        "schema_version": 3,
        "product": "QEDTY",
        "architecture_release": "0.1a0-dev0",
        "repository": f"https://github.com/{REPO}",
        "branch": BRANCH,
        "generated_on": date.today().isoformat(),
        "tracked_file_count": len(local_files),
        "inventory_policy": (
            "This file records the tracked path inventory and counts. Current commit/tree "
            "identifiers and remote parity are generated by CI, not embedded in this file."
        ),
        "legacy_scanner_directories_absent": all(
            not any(f == prefix or f.startswith(prefix + "/") for f in local_files)
            for prefix in ("__pycache__", ".venv", ".git", "target")
        ),
        "uv_lock_status": "tracked; regenerate with target uv >= 0.12.23 when dependency inputs change",
        **inv,
        "files": local_files,
    }
    path = repo / "QEDTY-PROJECT-MANIFEST.json"
    path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return manifest

def generated_tracked_warnings(local_files: list[str]) -> list[str]:
    prefixes = (
        "target/",
        ".venv/",
        ".git/",
        "build/",
        "dist/",
        "htmlcov/",
        ".pytest_cache/",
        ".mypy_cache/",
        ".ruff_cache/",
        ".benchmarks/",
    )
    exact = {".coverage", "coverage.xml", "junit.xml"}
    bad = [p for p in local_files if p in exact or p.startswith(prefixes)]
    return bad


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-tests", action="store_true")
    parser.add_argument("--allow-local-extra", action="store_true")
    args = parser.parse_args()

    repo = Path.cwd()
    if not (repo / ".git").exists():
        print("ERROR: run from the QEDTY repository root.", file=sys.stderr)
        return 2

    before = git_files()
    bom_fixed, legacy_fixed = clean_text_files(repo, before)
    local = git_files()  # refreshed after cleanup in case the manifest itself changes later

    try:
        remote_sha, remote = fetch_remote_files()
    except Exception as exc:
        print(f"ERROR: could not fetch GitHub tree: {exc}", file=sys.stderr)
        return 3

    local_set = set(local)
    missing = sorted(remote - local_set)
    extra = sorted(local_set - remote)

    bad_generated = generated_tracked_warnings(local)
    write_manifest(repo, local)

    print("QEDTY Phase 1B reconciliation")
    print(f"repository: {REPO}")
    print(f"branch: {BRANCH}")
    print(f"remote tree: {remote_sha}")
    print(f"local tracked files: {len(local)}")
    print(f"remote tracked files: {len(remote)}")
    print(f"tree parity: {not missing and not extra}")
    print(f"BOMs removed: {len(bom_fixed)}")
    if bom_fixed:
        for p in bom_fixed:
            print(f"  BOM: {p}")
    print(f"legacy repository URL fixes: {len(legacy_fixed)}")
    if legacy_fixed:
        for p in legacy_fixed:
            print(f"  URL: {p}")
    if bad_generated:
        print("ERROR: generated artifacts are tracked:")
        for p in bad_generated:
            print(f"  {p}")
    if missing:
        print("MISSING FROM LOCAL (present on GitHub):")
        for p in missing:
            print(f"  {p}")
    if extra:
        print("EXTRA LOCALLY (not present on GitHub):")
        for p in extra:
            print(f"  {p}")

    if missing or (extra and not args.allow_local_extra) or bad_generated:
        print("\nPHASE 1B STATUS: NOT CLOSED")
        return 4

    if args.run_tests:
        print("\nRunning scripts/verify.sh ...")
        subprocess.run(["bash", "scripts/verify.sh"], check=True)
        if (repo / "crates/qedty-core/Cargo.toml").exists():
            print("\nRunning Rust tests ...")
            subprocess.run(
                ["cargo", "test", "--manifest-path", "crates/qedty-core/Cargo.toml"],
                check=True,
            )

    print("\nPHASE 1B STATUS: PASS")
    print(f"Manifest: {repo / 'QEDTY-PROJECT-MANIFEST.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
