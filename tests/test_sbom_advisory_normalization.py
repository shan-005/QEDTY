"""Permanent regression tests for SBOM advisory normalization logic.

These tests ensure that:
1. CVSS vectors are correctly parsed for score/severity (not confused with version prefixes).
2. Fixed versions are correctly selected from the matching SemVer branch.
3. RustSec informational advisories (unmaintained/unsound) are not promoted to MEDIUM.
4. Database-specific severity is only used as a fallback when no CVSS is present.
"""

import pytest

from seraph.guard.scanners.sbom import SBOMScanner


@pytest.mark.security
def test_cvss_31_vector_is_calculated_not_version_prefix() -> None:
    vuln = {
        "id": "GHSA-test-31",
        "severity": [
            {
                "type": "CVSS_V3",
                "score": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:N/I:N/A:H",
            }
        ],
    }

    severity, score, vector, version, source_severity, source = SBOMScanner._extract_severity(vuln)

    assert score == 7.5
    assert severity == "HIGH"
    assert vector.startswith("CVSS:3.1/")
    assert version == "3.1"
    assert source_severity == "HIGH"
    assert source == "CVSS_V3"


@pytest.mark.security
def test_cvss_40_vector_is_calculated_not_version_prefix() -> None:
    vuln = {
        "id": "GHSA-test-40",
        "severity": [
            {
                "type": "CVSS_V4",
                "score": "CVSS:4.0/AV:N/AC:L/AT:N/PR:N/UI:N/VC:H/VI:H/VA:H/SC:H/SI:H/SA:N",
            }
        ],
    }

    severity, score, vector, version, source_severity, source = SBOMScanner._extract_severity(vuln)

    assert score == 9.9
    assert severity == "CRITICAL"
    assert vector.startswith("CVSS:4.0/")
    assert version == "4.0"
    assert source_severity == "CRITICAL"
    assert source == "CVSS_V4"


@pytest.mark.security
def test_fixed_version_selects_matching_semver_branch() -> None:
    vuln = {
        "affected": [
            {
                "ranges": [
                    {
                        "type": "SEMVER",
                        "events": [
                            {"introduced": "0"},
                            {"fixed": "3.15.2"},
                            {"introduced": "4.0.0"},
                            {"fixed": "4.3.2"},
                        ],
                    }
                ]
            }
        ]
    }

    fixed, all_fixed = SBOMScanner._extract_fixed_version(vuln, "4.2.0", "npm")

    assert fixed == "4.3.2"
    assert set(all_fixed) == {"3.15.2", "4.3.2"}


@pytest.mark.security
def test_fixed_version_selects_matching_next_branch() -> None:
    vuln = {
        "affected": [
            {
                "ranges": [
                    {
                        "type": "SEMVER",
                        "events": [
                            {"introduced": "0"},
                            {"fixed": "15.5.16"},
                            {"introduced": "16.0.0"},
                            {"fixed": "16.2.5"},
                        ],
                    }
                ]
            }
        ]
    }

    fixed, _ = SBOMScanner._extract_fixed_version(vuln, "16.2.3", "npm")
    assert fixed == "16.2.5"


@pytest.mark.security
def test_rustsec_unmaintained_is_not_promoted_to_medium() -> None:
    vuln = {
        "id": "RUSTSEC-2025-0056",
        "summary": "adler crate is unmaintained, use adler2 instead",
        "database_specific": {"informational": "unmaintained", "cvss": None},
    }

    severity, score, _, _, source_severity, source = SBOMScanner._extract_severity(vuln)
    advisory_type = SBOMScanner._extract_advisory_type(vuln)

    assert score is None
    assert severity == "UNKNOWN"
    assert source_severity == "UNKNOWN"
    assert source == "none"
    assert advisory_type == "unmaintained"


@pytest.mark.security
def test_rustsec_unsound_is_classified_separately() -> None:
    vuln = {
        "id": "RUSTSEC-2026-0190",
        "summary": "Unsoundness in Error::downcast_mut()",
        "database_specific": {"informational": "unsound", "cvss": None},
    }

    assert SBOMScanner._extract_advisory_type(vuln) == "unsound"


@pytest.mark.security
def test_database_specific_severity_is_used_only_without_cvss() -> None:
    vuln = {
        "id": "GHSA-test-db",
        "severity": [],
        "database_specific": {"severity": "HIGH"},
    }

    severity, score, _, _, source_severity, source = SBOMScanner._extract_severity(vuln)

    assert score is None
    assert severity == "HIGH"
    assert source_severity == "HIGH"
    assert source == "database_specific"
