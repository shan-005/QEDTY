#!/usr/bin/env python3
"""Run evidence behavior tests; this check does not alias temporal conformance."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    completed = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", str(ROOT / "tests" / "test_evidence.py")],
        cwd=ROOT,
        check=False,
    )
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
