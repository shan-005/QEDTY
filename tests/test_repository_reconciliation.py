from __future__ import annotations

import json
import runpy
from pathlib import Path


def test_generated_manifest_is_branch_neutral(tmp_path: Path) -> None:
    script = Path(__file__).resolve().parents[1] / "scripts" / "reconcile_repository.py"
    namespace = runpy.run_path(str(script))

    manifest = namespace["write_manifest"](tmp_path, ["README.md"])
    written = json.loads((tmp_path / "QEDTY-PROJECT-MANIFEST.json").read_text(encoding="utf-8"))

    assert "branch" not in manifest
    assert "branch" not in written
    assert written["files"] == ["README.md"]
