#!/usr/bin/env python3
"""Execute SHACL constraints against valid and invalid QEDTY evidence RDF graphs."""

from __future__ import annotations

from pathlib import Path

from pyshacl import validate
from rdflib import Graph, Namespace
from rdflib.namespace import RDF, SH

ROOT = Path(__file__).resolve().parents[1]
SHAPES_PATH = ROOT / "contracts" / "evidence" / "shacl" / "evidence.shacl.ttl"
SER = Namespace("https://qedty.local/evidence/")
XSD = Namespace("http://www.w3.org/2001/XMLSchema#")

VALID = """
@prefix ser: <https://qedty.local/evidence/> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .
ser:record-001 a ser:EvidenceRecord ;
    ser:evidenceId "qedty:evidence:001"^^xsd:string ;
    ser:contentSha256 "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef" ;
    ser:sourceUri "https://example.org/evidence/001"^^xsd:anyURI .
"""

CASES: tuple[tuple[str, str, bool, set[tuple[str, str]]], ...] = (
    (
        "valid evidence record",
        VALID,
        True,
        set(),
    ),
    (
        "missing evidence ID",
        """
        @prefix ser: <https://qedty.local/evidence/> .
        @prefix xsd: <http://www.w3.org/2001/XMLSchema#> .
        ser:record-002 a ser:EvidenceRecord ;
            ser:contentSha256 "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef" ;
            ser:sourceUri "https://example.org/evidence/002"^^xsd:anyURI .
        """,
        False,
        {(str(SER.evidenceId), str(SH.MinCountConstraintComponent))},
    ),
    (
        "duplicate evidence ID",
        VALID.replace(
            '"qedty:evidence:001"^^xsd:string',
            '"qedty:evidence:001"^^xsd:string, "qedty:evidence:alternate"^^xsd:string',
        ),
        False,
        {(str(SER.evidenceId), str(SH.MaxCountConstraintComponent))},
    ),
    (
        "wrong evidence ID datatype",
        VALID.replace('"qedty:evidence:001"^^xsd:string', "42"),
        False,
        {(str(SER.evidenceId), str(SH.DatatypeConstraintComponent))},
    ),
    (
        "missing content digest",
        """
        @prefix ser: <https://qedty.local/evidence/> .
        @prefix xsd: <http://www.w3.org/2001/XMLSchema#> .
        ser:record-003 a ser:EvidenceRecord ;
            ser:evidenceId "qedty:evidence:003"^^xsd:string ;
            ser:sourceUri "https://example.org/evidence/003"^^xsd:anyURI .
        """,
        False,
        {(str(SER.contentSha256), str(SH.MinCountConstraintComponent))},
    ),
    (
        "malformed content digest",
        VALID.replace(
            "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
            "ABCDEF-not-a-sha256",
        ),
        False,
        {(str(SER.contentSha256), str(SH.PatternConstraintComponent))},
    ),
    (
        "duplicate content digest",
        VALID.replace(
            'ser:contentSha256 "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef" ;',
            'ser:contentSha256 "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",\n'
            '    "1123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef" ;',
        ),
        False,
        {(str(SER.contentSha256), str(SH.MaxCountConstraintComponent))},
    ),
    (
        "missing source URI",
        """
        @prefix ser: <https://qedty.local/evidence/> .
        ser:record-004 a ser:EvidenceRecord ;
            ser:evidenceId "qedty:evidence:004" ;
            ser:contentSha256 "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef" .
        """,
        False,
        {(str(SER.sourceUri), str(SH.MinCountConstraintComponent))},
    ),
    (
        "duplicate source URI",
        VALID.replace(
            'ser:sourceUri "https://example.org/evidence/001"^^xsd:anyURI .',
            'ser:sourceUri "https://example.org/evidence/001"^^xsd:anyURI,\n'
            '    "https://example.org/evidence/alternate"^^xsd:anyURI .',
        ),
        False,
        {(str(SER.sourceUri), str(SH.MaxCountConstraintComponent))},
    ),
    (
        "wrong source URI datatype",
        VALID.replace(
            '"https://example.org/evidence/001"^^xsd:anyURI',
            '"https://example.org/evidence/001"',
        ),
        False,
        {(str(SER.sourceUri), str(SH.DatatypeConstraintComponent))},
    ),
)


def validate_case(
    name: str,
    turtle: str,
    expected_conforms: bool,
    expected_violations: set[tuple[str, str]],
) -> None:
    data_graph = Graph()
    data_graph.parse(data=turtle, format="turtle")

    conforms, report_graph, report_text = validate(
        data_graph=data_graph,
        shacl_graph=str(SHAPES_PATH),
        inference="none",
        abort_on_first=False,
        meta_shacl=True,
        advanced=False,
        debug=False,
    )

    results = set()
    for result in report_graph.subjects(RDF.type, SH.ValidationResult):
        path = report_graph.value(result, SH.resultPath)
        component = report_graph.value(result, SH.sourceConstraintComponent)
        if path is None or component is None:
            raise AssertionError(f"{name}: SHACL result lacks a path or constraint component")
        results.add((str(path), str(component)))

    if bool(conforms) != expected_conforms:
        raise AssertionError(
            f"{name}: expected conforms={expected_conforms}, got {conforms}.\n{report_text}"
        )
    if not expected_violations <= results:
        missing = expected_violations - results
        raise AssertionError(f"{name}: missing expected SHACL results {missing}.\n{report_text}")
    if expected_conforms and results:
        raise AssertionError(f"{name}: conforming graph produced results {results}.\n{report_text}")

    expectation = "conforms" if expected_conforms else "rejects expected violation"
    print(f"PASS SHACL: {name} ({expectation})")


def main() -> int:
    if not SHAPES_PATH.is_file():
        raise FileNotFoundError(f"Evidence SHACL shapes not found: {SHAPES_PATH}")

    for name, turtle, expected_conforms, expected_violations in CASES:
        validate_case(name, turtle, expected_conforms, expected_violations)

    print(f"PASS: executed {len(CASES)} evidence SHACL validation cases.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
