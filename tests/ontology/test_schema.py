from seraph.ontology.schema import (
    ENTITY_TYPE_IRIS,
    GEOSPARQL_NAMESPACE,
    ONTOLOGY_PROFILE,
    PROV_NAMESPACE,
    RELATIONSHIP_TYPE_IRIS,
    SERAPH_NAMESPACE,
    STANDARDS_BASELINE,
    iri,
    normalize_iri,
    ontology_metadata,
)


def test_namespace_and_terms() -> None:
    assert ONTOLOGY_PROFILE == "seraph-ontology@2.0.0"
    assert SERAPH_NAMESPACE.startswith("https://")
    assert PROV_NAMESPACE.endswith("prov#")
    assert GEOSPARQL_NAMESPACE.endswith("geosparql#")
    assert iri("Entity").endswith("/Entity")
    assert normalize_iri("https://example.org/x") == "https://example.org/x"
    assert len(ontology_metadata()["terms"]) >= 8
    assert len(ENTITY_TYPE_IRIS) >= 20
    assert len(RELATIONSHIP_TYPE_IRIS) >= 20
    assert "shacl" in STANDARDS_BASELINE


def test_normalization_rejects_blank_iri_and_local_term() -> None:
    import pytest

    with pytest.raises(ValueError):
        iri("   ")
    with pytest.raises(ValueError):
        iri("bad term")
    with pytest.raises(ValueError):
        normalize_iri("not-an-iri")


def test_absolute_iri_validation_accepts_standard_iri_schemes() -> None:
    assert normalize_iri("mailto:ontology@example.org") == "mailto:ontology@example.org"
    assert normalize_iri("urn:seraph:entity:123") == "urn:seraph:entity:123"
