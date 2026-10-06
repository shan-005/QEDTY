from seraph.core.enums import EntityType
from seraph.core.hash import deterministic_id
from seraph.ontology.entities import Entity
from seraph.storage.sqlite import SQLiteWorldStore


def test_storage(tmp_path):
    s = SQLiteWorldStore(tmp_path / "w.sqlite")
    e = Entity(
        entity_id=deterministic_id("entity", "seraph", "company", "x"),
        entity_type=EntityType.COMPANY,
        canonical_name="x",
    )
    s.put_entity(e)
    assert (tmp_path / "w.sqlite").exists()
