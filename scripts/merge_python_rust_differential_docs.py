#!/usr/bin/env python3
"""Safely merge the differential conformance notes into existing Rust docs.

This script refuses to edit when neither the known source text nor the new text
is present, preventing silent overwrites of docs that have changed upstream.
"""

from __future__ import annotations

import argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

SOURCE_OLD = (
    "4. **Do not report unimplemented vectors as passes.** The current "
    "`quantity.json` and `time.json` fixtures have no matching Rust API in the current crate."
)
SOURCE_NEW = (
    "4. **Do not report unimplemented vectors as passes.** The current Rust crate and "
    "conformance executables implement quantity conversion and timestamp normalization "
    "against the shared `quantity.json` and `time.json` fixtures. Keep documentation tied "
    "to the exact runner output; broader randomized Python–Rust differential coverage is "
    "a separate engineering acceptance gate."
)

README_OLD = (
    "The expected conformance output covers four implemented families: canonical JSON, "
    "deterministic identity, WGS-84 ECEF, and RFC 3339 timestamp normalization. The core "
    "crate's own temporal interval tests and shared-vector integration tests also run as "
    "part of `cargo test --workspace`."
)
README_NEW = (
    "The `qedty-conformance` CLI checks canonical JSON, deterministic identity, WGS-84 "
    "ECEF, UTC timestamp normalization, quantity conversion and contract-result "
    "normalization from shared vectors. `rust-expansion-conformance` additionally checks "
    "graph/spatial golden scenarios. These fixed checks are not a substitute for direct "
    "same-input differential comparison; see `docs/engineering/PYTHON_RUST_DIFFERENTIAL.md`."
)

CONFORMANCE_SECTION = r"""

## Direct Python–Rust differential runner

`rust/crates/qedty-conformance/src/bin/qedty-differential.rs` exposes the current shared core operations through one JSON Lines request/response per case. `scripts/check_python_rust_differential.py` evaluates each identical payload using QEDTY's real Python reference functions, invokes the native runner, compares exact values or the per-case numeric tolerance, and fails on protocol errors or mismatches. Negative cases require a declared shared error category.

Run from the repository root:

```bash
uv run pytest -q tests/differential
uv run python scripts/check_python_rust_differential.py --generated-count 64 --seed 20261010
```

The checked-in cases cover canonical JSON, deterministic IDs, physical-unit conversion, RFC 3339 normalization, checked ECEF, contract-result normalization, half-open interval membership and all 13 Allen relations. Generated cases use a fixed replayable seed. Do not regenerate expected golden outputs from the Rust implementation. This adapter does not claim that every QEDTY Python domain API is implemented in Rust: specifically, the native `DirectedGraph` primitive is not the Python temporal world-graph API. Only claim parity where a shared contract and matching semantic boundary exist.
""".strip()


def transform(
    path: Path,
    old: str,
    new: str,
    *,
    append_section: str | None = None,
) -> tuple[str, bool]:
    original = path.read_text(encoding="utf-8")
    changed = False
    if old in original:
        original = original.replace(old, new, 1)
        changed = True
    elif new not in original:
        raise ValueError(
            f"refusing to modify {path.relative_to(ROOT)}: expected source text not found"
        )
    if append_section is not None:
        marker = "## Direct Python–Rust differential runner"
        if marker not in original:
            original = original.rstrip() + "\n\n" + append_section + "\n"
            changed = True
    return original, changed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--apply", action="store_true", help="write the reviewed documentation edits"
    )
    args = parser.parse_args()
    specs = [
        (ROOT / "rust/research/SOURCES.md", SOURCE_OLD, SOURCE_NEW, None),
        (ROOT / "rust/README.md", README_OLD, README_NEW, None),
        (ROOT / "rust/CONFORMANCE.md", "", "", CONFORMANCE_SECTION),
    ]
    pending: list[tuple[Path, str, bool]] = []
    try:
        for path, old, new, section in specs:
            if not path.is_file():
                raise ValueError(f"required documentation file is absent: {path.relative_to(ROOT)}")
            if section is not None:
                content = path.read_text(encoding="utf-8")
                marker = "## Direct Python–Rust differential runner"
                result = (
                    content if marker in content else content.rstrip() + "\n\n" + section + "\n"
                )
                pending.append((path, result, result != content))
            else:
                result, changed = transform(path, old, new)
                pending.append((path, result, changed))
    except (OSError, ValueError) as error:
        print(f"ERROR: {error}")
        return 2

    edits = [(path, content) for path, content, changed in pending if changed]
    if not args.apply:
        if edits:
            print("Documentation changes are ready but not applied:")
            for path, _ in edits:
                print(f"  {path.relative_to(ROOT)}")
            print("Review the working-tree state, then rerun with --apply.")
        else:
            print("PASS: differential documentation notes already merged.")
        return 0

    for path, content in edits:
        path.write_text(content, encoding="utf-8")
        print(f"UPDATED {path.relative_to(ROOT)}")
    print(
        f"PASS: applied {len(edits)} guarded documentation edit(s). "
        "Review with git diff before committing."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
