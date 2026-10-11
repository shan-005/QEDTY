from __future__ import annotations

import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MATRIX_PATH = ROOT / "docs" / "engineering" / "CROSS_LANGUAGE_CONFORMANCE_MATRIX.csv"
REQUIRED_COLUMNS = {
    "domain",
    "python_reference",
    "rust_implementation",
    "contract_or_vectors",
    "evidence_level",
    "status",
    "audit_finding",
    "required_work",
}
ALLOWED_STATUSES = {
    "DIRECT_DIFFERENTIAL",
    "SHARED_GOLDEN_ONLY",
    "LANGUAGE_UNIT_ONLY",
    "NO_SHARED_CONTRACT",
    "PYTHON_ONLY",
}
PATH_COLUMNS = ("python_reference", "rust_implementation", "contract_or_vectors")


def test_conformance_matrix_is_machine_readable_complete_and_path_valid() -> None:
    assert MATRIX_PATH.is_file(), "conformance matrix is missing"
    with MATRIX_PATH.open(encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        assert reader.fieldnames is not None
        assert REQUIRED_COLUMNS.issubset(reader.fieldnames)
        rows = list(reader)

    assert rows, "conformance matrix must contain domain rows"
    domains = [row["domain"].strip() for row in rows]
    assert all(domains), "domain name cannot be blank"
    assert len(domains) == len(set(domains)), "duplicate matrix domain"

    for row in rows:
        for column in REQUIRED_COLUMNS:
            assert row[column].strip(), f"{row['domain']}: blank {column}"
        assert row["status"] in ALLOWED_STATUSES, (
            row["domain"],
            row["status"],
        )
        for column in PATH_COLUMNS:
            for relative in row[column].split(";"):
                relative = relative.strip()
                if relative == "NONE":
                    continue
                assert (ROOT / relative).is_file(), (
                    row["domain"],
                    column,
                    relative,
                )

    observed = {row["status"] for row in rows}
    assert "DIRECT_DIFFERENTIAL" in observed
    assert "NO_SHARED_CONTRACT" in observed
    assert "PYTHON_ONLY" in observed
