import pytest
from datetime import UTC,datetime
from seraph.core.enums import EntityType,RelationshipType
from seraph.core.hash import deterministic_id
from seraph.ontology.entities import Entity
from seraph.ontology.relations import Relationship
def test_relation_rejects_self_loop():
    from pydantic import ValidationError
    eid=deterministic_id("entity","seraph","satellite","demo"); Entity(entity_id=eid,entity_type=EntityType.SATELLITE,canonical_name="Demo")
    with pytest.raises(ValidationError): Relationship(relationship_id=deterministic_id("rel",eid,eid,RelationshipType.SUPPORTS.value,None,None),source={"entity_id":eid},target={"entity_id":eid},relationship_type=RelationshipType.SUPPORTS)
