from pathlib import Path

import pytest

from seraph.guard.cli import build_scanners
from seraph.guard.config import SeraphConfig
from seraph.guard.config_loader import ConfigLoader


@pytest.mark.integration
def test_sbom_config_propagates(tmp_path: Path) -> None:
    config_path = tmp_path / "config.yaml"

    config_path.write_text(
        """
sbom:
  include_dev_dependencies: false
  deduplicate_across_manifests: true
  chunk_size: 500
  max_dependencies: 20000
  quick_mode: false
""",
        encoding="utf-8",
    )

    raw = ConfigLoader.load(str(tmp_path), str(config_path))

    config = SeraphConfig.from_cli_args(path=str(tmp_path))

    sbom = raw["sbom"]

    for key in (
        "include_dev_dependencies",
        "deduplicate_across_manifests",
        "chunk_size",
        "max_dependencies",
        "quick_mode",
    ):
        setattr(config.sbom, key, sbom[key])

    scanners = build_scanners(config)
    sbom_scanner = next(
        scanner for scanner in scanners if getattr(scanner, "name", "") == "SBOMScanner"
    )

    assert config.sbom.chunk_size == 500
    assert config.sbom.max_dependencies == 20000
    assert config.sbom.quick_mode is False

    assert sbom_scanner.chunk_size == 500
    assert sbom_scanner.max_dependencies == 20000
    assert sbom_scanner.quick_mode is False
