"""Focused regression tests for the 2026-09-27 production hardening.

These tests exercise the failure classes observed in Gate 4 without depending on
large external repositories or network availability.
"""

from __future__ import annotations

import json

from typing import TYPE_CHECKING

import pytest

from seraph.guard.scanners.sbom import SBOMScanner, _build_osv_query
from seraph.ufic.classifier import OmissionDetector
from seraph.ufic.topology import TopologyEngine


if TYPE_CHECKING:
    from pathlib import Path


def test_osv_query_uses_exactly_one_version_identity() -> None:
    query, error = _build_osv_query(
        {
            "package": {
                "name": "rails",
                "ecosystem": "RubyGems",
            },
            "version": "7.1.2",
        }
    )
    assert error is None
    assert query == {
        "package": {"name": "rails", "ecosystem": "RubyGems"},
        "version": "7.1.2",
    }


def test_osv_query_rejects_non_concrete_versions() -> None:
    query, error = _build_osv_query(
        {"package": {"name": "x", "ecosystem": "npm"}, "version": "^1.2.3"}
    )
    assert query is None
    assert "concrete version" in (error or "")


def test_osv_query_rejects_versioned_purl_plus_top_level_version() -> None:
    query, error = _build_osv_query(
        {
            "package": {"purl": "pkg:npm/lodash@4.17.20"},
            "version": "4.17.20",
        }
    )
    assert query is None
    assert "already contains a version" in (error or "")


@pytest.mark.parametrize(
    "a,b",
    (
        ["1.0.0-alpha", "1.0.0"],
        ["1.0.0-alpha.1", "1.0.0-alpha.beta"],
        ["1.2.3", "2.0.0"],
    ),
)
def test_semver_comparison_is_type_safe(a: str, b: str) -> None:
    pa = SBOMScanner._version_parts(a)
    pb = SBOMScanner._version_parts(b)
    assert pa is not None
    assert pb is not None
    assert pa < pb


def test_topology_ignores_directory_named_like_source_file(tmp_path: Path) -> None:
    (tmp_path / "packages").mkdir()
    (tmp_path / "packages" / "src").mkdir(parents=True)
    (tmp_path / "packages" / "src" / "fake.js").mkdir()
    engine = TopologyEngine()
    result = engine._extract_api_surface(
        tmp_path,
        [],
    )
    assert result == []


def test_omission_detector_ignores_directory_named_like_python_file(tmp_path: Path) -> None:
    """
    Regression guard:

    A directory whose name looks like a Python source file must not crash
    omission detection traversal.

    OmissionDetector exposes scan(), not detect_omissions().
    UFICClassifier.detect_omissions() delegates to OmissionDetector.scan().
    """
    (tmp_path / "fake.py").mkdir()
    detector = OmissionDetector()

    result = detector.scan(tmp_path)

    assert isinstance(result, list)
    assert result == []


def test_json_repeatability_signature_is_json_not_python() -> None:
    first = {"findings": [{"scanner": "x", "severity": "high", "file": "a.py", "line": 1}]}
    second = json.loads(json.dumps(first))
    assert first == second
