#!/usr/bin/env python3
"""Audit and optionally repair legacy project identifiers in tracked QEDTY text.

The checker is deliberately standard-library-only. It scans every UTF-8 tracked
file rather than maintaining a fragile extension allow-list, which covers source,
docs, workflows, schemas, manifests, lockfiles and policy/configuration text.
Binary/non-UTF-8 files are skipped and reported as binary, not silently decoded.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path
from typing import Final

# Split these tokens so the checker source does not match its own audit rules.
_OLD_PRODUCT: Final[str] = "SERA" + "PH"
_OLD_HANDLE: Final[str] = "IRIN" + "-0"
_OLD_PRODUCT_VARIANT: Final[str] = _OLD_PRODUCT + "-PCI-X"

_REPLACEMENTS: Final[tuple[tuple[re.Pattern[str], str], ...]] = (
    (re.compile(re.escape(_OLD_PRODUCT_VARIANT), re.IGNORECASE), "QEDTY-PCI-X"),
    (re.compile(re.escape(_OLD_PRODUCT), re.IGNORECASE), "QEDTY"),
    (re.compile(re.escape(_OLD_HANDLE), re.IGNORECASE), "shan-005"),
)
_NUMBERED_MILESTONE: Final[re.Pattern[str]] = re.compile(
    r"\bphase\s+(?:1a|1b|2|3)\b", re.IGNORECASE
)
_MILESTONE_REPLACEMENTS: Final[dict[str, str]] = {
    "phase 1a": "Python semantic foundation",
    "phase 1b": "repository reconciliation",
    "phase 2": "Rust core expansion and conformance",
    "phase 3": "Systematic Python–Rust Differential Testing",
}
_ARCHIVE_EVIDENCE_PREFIX = "rust/benches/results/"


def tracked_paths() -> list[str]:
    result = subprocess.run(
        ["git", "ls-files", "-z"],
        check=True,
        capture_output=True,
    )
    return sorted(
        item.decode("utf-8")
        for item in result.stdout.split(b"\0")
        if item
    )


def read_utf8(path: Path) -> str | None:
    try:
        raw = path.read_bytes()
    except OSError as exc:
        print(f"ERROR: cannot read {path}: {exc}", file=sys.stderr)
        return None
    if b"\0" in raw:
        return None
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return None


def replace_legacy(text: str) -> str:
    for pattern, replacement in _REPLACEMENTS:
        text = pattern.sub(replacement, text)
    return text


def is_active_markdown(path: str) -> bool:
    return path.lower().endswith(".md") and not (
        path.startswith(_ARCHIVE_EVIDENCE_PREFIX)
        or path == "CHANGELOG.md"
    )


def replace_milestone_labels(text: str) -> str:
    def replacement(match: re.Match[str]) -> str:
        key = " ".join(match.group(0).lower().split())
        return _MILESTONE_REPLACEMENTS[key]

    return _NUMBERED_MILESTONE.sub(replacement, text)


def audit(fix: bool) -> int:
    root = Path.cwd()
    try:
        paths = tracked_paths()
    except (OSError, subprocess.CalledProcessError) as exc:
        print(f"ERROR: git ls-files failed: {exc}", file=sys.stderr)
        return 2

    findings: list[str] = []
    skipped_binary = 0
    fixed_files: list[str] = []

    for rel in paths:
        path = root / rel
        if not path.is_file():
            continue
        original = read_utf8(path)
        if original is None:
            skipped_binary += 1
            continue

        updated = replace_legacy(original)
        if is_active_markdown(rel):
            updated = replace_milestone_labels(updated)

        if updated != original:
            if fix:
                try:
                    path.write_text(updated, encoding="utf-8", newline="")
                except OSError as exc:
                    print(f"ERROR: cannot update {rel}: {exc}", file=sys.stderr)
                    return 2
                fixed_files.append(rel)
                continue
            findings.append(rel)
            continue

        # Always report path names as well as file contents. This does not rename
        # tracked paths because a path rename needs a separate reviewed operation.
        folded_path = rel.casefold()
        if any(token.casefold() in folded_path for token in (
            _OLD_PRODUCT, _OLD_HANDLE, _OLD_PRODUCT_VARIANT
        )):
            findings.append(f"{rel} [legacy path name]")
        if is_active_markdown(rel) and _NUMBERED_MILESTONE.search(original):
            findings.append(f"{rel} [numbered internal milestone label]")

    if fix:
        print(f"Fixed {len(fixed_files)} tracked text file(s).")
        for rel in fixed_files:
            print(f"  FIXED {rel}")
        # Re-run the read-only check to prove the applied replacements are clean.
        return audit(fix=False)

    if findings:
        print("FAIL: legacy identifiers or numbered internal milestone labels remain:")
        for rel in sorted(set(findings)):
            print(f"  {rel}")
        print("Run: uv run python scripts/check_project_identity.py --fix")
        return 1

    print(
        "PASS: no legacy project identifiers or numbered internal milestone "
        f"labels in {len(paths)} tracked paths (skipped {skipped_binary} binary/non-UTF-8 files)."
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true", help="audit without changing files")
    mode.add_argument("--fix", action="store_true", help="apply literal project-name and active-doc milestone renames")
    args = parser.parse_args()
    if not (Path.cwd() / ".git").exists():
        print("ERROR: run from the QEDTY repository root.", file=sys.stderr)
        return 2
    return audit(fix=args.fix)


if __name__ == "__main__":
    raise SystemExit(main())
