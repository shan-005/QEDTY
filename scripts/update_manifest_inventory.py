#!/usr/bin/env python3
"""Recompute QEDTY's branch-neutral tracked-path manifest for this additive bundle.

The helper includes the explicitly listed new bundle paths before Git staging so
that the manifest is correct by the time the files are staged and committed. It
does not sweep in unrelated untracked working files.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "QEDTY-PROJECT-MANIFEST.json"
BUNDLE_PATHS = (
    ".github/workflows/python-rust-differential.yml",
    "contracts/json-schema/differential-cases.schema.json",
    "data/contracts/differential/README.md",
    "data/contracts/differential/cases/core.json",
    "docs/engineering/PYTHON_RUST_DIFFERENTIAL.md",
    "rust/crates/qedty-conformance/src/bin/qedty-differential.rs",
    "scripts/check_python_rust_differential.py",
    "scripts/merge_python_rust_differential_docs.py",
    "scripts/update_manifest_inventory.py",
    "tests/differential/test_differential_cases.py",
)
COUNT_FIELDS = {
    "python_files": ".py",
    "rust_files": ".rs",
    "protobuf_files": ".proto",
    "markdown_files": ".md",
    "json_files": ".json",
    "turtle_files": ".ttl",
    "shell_files": ".sh",
}


def current_paths() -> list[str]:
    result = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=ROOT,
        check=True,
        capture_output=True,
    )
    paths = {item.decode("utf-8") for item in result.stdout.split(b"\0") if item}
    for relative in BUNDLE_PATHS:
        path = ROOT / relative
        if not path.is_file():
            raise FileNotFoundError(f"expected bundle file missing: {relative}")
        paths.add(relative)
    return sorted(paths)


def counts(paths: list[str]) -> tuple[dict[str, int], dict[str, int]]:
    by_extension: Counter[str] = Counter()
    by_root: Counter[str] = Counter()
    for relative in paths:
        item = Path(relative)
        extension = item.suffix.lower() if item.suffix else "<no-extension>"
        by_extension[extension] += 1
        by_root[item.parts[0] if item.parts else "."] += 1
    return dict(sorted(by_extension.items())), dict(sorted(by_root.items()))


def build_manifest(existing: dict[str, Any], paths: list[str]) -> dict[str, Any]:
    extensions, roots = counts(paths)
    manifest = dict(existing)
    manifest["tracked_file_count"] = len(paths)
    manifest["files"] = paths
    manifest["extension_counts"] = extensions
    manifest["root_counts"] = roots
    for field, extension in COUNT_FIELDS.items():
        manifest[field] = extensions.get(extension, 0)
    manifest["yaml_files"] = extensions.get(".yaml", 0) + extensions.get(".yml", 0)
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--write", action="store_true", help="write the recomputed manifest")
    mode.add_argument(
        "--check", action="store_true", help="fail if the manifest is stale (default)"
    )
    args = parser.parse_args()
    try:
        existing = json.loads(MANIFEST.read_text(encoding="utf-8"))
        if not isinstance(existing, dict):
            raise ValueError("project manifest must be a JSON object")
        if "branch" in existing:
            raise ValueError("project inventory manifest must remain branch-neutral")
        paths = current_paths()
        updated = build_manifest(existing, paths)
        serialized = json.dumps(updated, ensure_ascii=False, indent=2) + "\n"
        current = MANIFEST.read_text(encoding="utf-8")
        if current == serialized:
            print(f"PASS: project manifest already matches {len(paths)} paths.")
            return 0
        if args.write:
            MANIFEST.write_text(serialized, encoding="utf-8")
            print(f"UPDATED: project manifest now inventories {len(paths)} paths.")
            print(
                "Stage the bundle files and manifest, then run scripts/check_manifest_inventory.py."
            )
            return 0
        print(
            "ERROR: QEDTY-PROJECT-MANIFEST.json is stale for the current bundle paths.",
            file=sys.stderr,
        )
        print(
            "Review the working tree, then run: "
            "uv run python scripts/update_manifest_inventory.py --write",
            file=sys.stderr,
        )
        return 1
    except (OSError, subprocess.CalledProcessError, ValueError) as error:
        print(f"ERROR: could not update/check the project manifest: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
