#!/usr/bin/env python3
"""Verify inventory, parse JSON assets, and validate local Markdown links."""

from __future__ import annotations

import json
import posixpath
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "QEDTY-PROJECT-MANIFEST.json"


def tracked_paths() -> list[str]:
    result = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=ROOT,
        check=True,
        capture_output=True,
    )
    return sorted(path.decode("utf-8") for path in result.stdout.split(b"\0") if path)


def inventory(paths: list[str]) -> tuple[dict[str, int], dict[str, int]]:
    by_extension: Counter[str] = Counter()
    by_root: Counter[str] = Counter()
    for path in paths:
        item = Path(path)
        extension = item.suffix.lower() if item.suffix else "<no-extension>"
        by_extension[extension] += 1
        by_root[item.parts[0] if item.parts else "."] += 1
    return dict(sorted(by_extension.items())), dict(sorted(by_root.items()))


def validate_json_assets(paths: list[str]) -> bool:
    """Ensure every tracked JSON and JSON-LD asset is valid strict JSON."""
    json_paths = [path for path in paths if Path(path).suffix.lower() in {".json", ".jsonld"}]
    failures: list[str] = []
    for path in json_paths:
        try:
            json.loads((ROOT / path).read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            failures.append(f"{path}: invalid JSON: {exc}")
    if failures:
        for failure in failures:
            print(f"ERROR: {failure}", file=sys.stderr)
        return False
    print(f"PASS: parsed {len(json_paths)} tracked JSON/JSON-LD files.")
    return True


def validate_markdown_links(paths: list[str]) -> bool:
    """Verify local Markdown links and reference definitions resolve to tracked paths."""
    markdown_paths = [path for path in paths if Path(path).suffix.lower() == ".md"]
    tracked = set(paths)
    directories: set[str] = set()
    for path in paths:
        parent = posixpath.dirname(path)
        while parent and parent != ".":
            directories.add(parent)
            parent = posixpath.dirname(parent)

    inline_link = re.compile(r"!?\[[^\]]*\]\((<[^>]+>|[^)]+)\)")
    reference_definition = re.compile(r"^ {0,3}\[[^\]]+\]:\s*(<[^>]+>|\S+)", re.MULTILINE)
    failures: list[str] = []
    checked = 0

    for source in markdown_paths:
        try:
            text = (ROOT / source).read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            failures.append(f"{source}: unable to read Markdown: {exc}")
            continue

        # Markdown links inside fenced code examples are illustrative, not references.
        prose_lines: list[str] = []
        fence_char: str | None = None
        fence_len = 0
        for line in text.splitlines():
            fence = re.match(r"^ {0,3}(`{3,}|~{3,})", line)
            if fence:
                marker = fence.group(1)
                if fence_char is None:
                    fence_char, fence_len = marker[0], len(marker)
                elif marker[0] == fence_char and len(marker) >= fence_len:
                    fence_char, fence_len = None, 0
                continue
            if fence_char is None:
                prose_lines.append(line)
        prose = "\n".join(prose_lines)
        prose = re.sub(r"(?<!\\)`+.*?(?<!\\)`+", "", prose)

        links = [match.group(1) for match in inline_link.finditer(prose)]
        links.extend(match.group(1) for match in reference_definition.finditer(prose))
        for raw_target in links:
            target = raw_target.strip()
            if target.startswith("<") and target.endswith(">"):
                target = target[1:-1].strip()
            else:
                target = target.split()[0] if target.split() else ""
            if not target or target.startswith("#"):
                continue
            try:
                parsed = urlsplit(target)
            except ValueError:
                failures.append(f"{source}: invalid Markdown link target {target!r}")
                continue
            if parsed.scheme or parsed.netloc:
                continue
            local_path = unquote(parsed.path)
            if not local_path:
                continue
            if local_path.startswith("/"):
                resolved = posixpath.normpath(local_path.lstrip("/"))
            else:
                resolved = posixpath.normpath(posixpath.join(posixpath.dirname(source), local_path))
            checked += 1
            if resolved not in tracked and resolved not in directories:
                failures.append(f"{source}: broken local Markdown link {target!r} -> {resolved!r}")

    if failures:
        for failure in failures:
            print(f"ERROR: {failure}", file=sys.stderr)
        return False
    print(
        f"PASS: checked {checked} local Markdown links across {len(markdown_paths)} Markdown files."
    )
    return True


def main() -> int:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    if "branch" in manifest:
        print(
            "ERROR: inventory manifests must be branch-neutral; remove the `branch` field.",
            file=sys.stderr,
        )
        return 1

    actual_paths = tracked_paths()
    expected_paths = manifest.get("files")
    if not isinstance(expected_paths, list) or actual_paths != expected_paths:
        expected = set(expected_paths) if isinstance(expected_paths, list) else set()
        actual = set(actual_paths)
        print("ERROR: manifest file list does not match git ls-files.", file=sys.stderr)
        for path in sorted(actual - expected):
            print(f"  missing from manifest: {path}", file=sys.stderr)
        for path in sorted(expected - actual):
            print(f"  not tracked by Git: {path}", file=sys.stderr)
        return 1

    if manifest.get("tracked_file_count") != len(actual_paths):
        print("ERROR: manifest tracked_file_count is stale.", file=sys.stderr)
        return 1

    extensions, roots = inventory(actual_paths)
    if manifest.get("extension_counts") != extensions:
        print("ERROR: manifest extension_counts is stale.", file=sys.stderr)
        return 1
    if manifest.get("root_counts") != roots:
        print("ERROR: manifest root_counts is stale.", file=sys.stderr)
        return 1

    expected_counts = {
        "python_files": extensions.get(".py", 0),
        "rust_files": extensions.get(".rs", 0),
        "protobuf_files": extensions.get(".proto", 0),
        "markdown_files": extensions.get(".md", 0),
        "json_files": extensions.get(".json", 0),
        "turtle_files": extensions.get(".ttl", 0),
        "yaml_files": extensions.get(".yaml", 0) + extensions.get(".yml", 0),
        "shell_files": extensions.get(".sh", 0),
    }
    for field, expected in expected_counts.items():
        if manifest.get(field) != expected:
            print(f"ERROR: manifest {field} is stale.", file=sys.stderr)
            return 1

    if not validate_json_assets(actual_paths):
        return 1
    if not validate_markdown_links(actual_paths):
        return 1

    print(f"PASS: inventory matches {len(actual_paths)} tracked paths.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
