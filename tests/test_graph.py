from datetime import UTC,datetime,timedelta
from seraph.core.enums import EntityType,RelationshipType
from seraph.core.hash import deterministic_id
from seraph.ontology.entities import Entity
from seraph.ontology.relations import Relationship
from seraph.graph.store import TemporalGraph
def test_temporal_path():
 s=datetime(2026,1,1,tzinfo=UTC); e=s+timedelta(days=1)
 a=Entity(entity_id=deterministic_id("entity","seraph","satellite","a"),entity_type=EntityType.SATELLITE,canonical_name="a")
 b=Entity(entity_id=deterministic_id("entity","seraph","service","b"),entity_type=EntityType.SERVICE,canonical_name="b")
 r=Relationship(relationship_id=deterministic_id("rel",a.entity_id,b.entity_id,RelationshipType.PROVIDES.value,s.isoformat(),e.isoformat()),source={"entity_id":a.entity_id},target={"entity_id":b.entity_id},relationship_type=RelationshipType.PROVIDES,valid_from=s,valid_to=e)
 g=TemporalGraph();g.add_entity(a);g.add_entity(b);g.add_relationship(r);assert g.shortest_paths(a.entity_id,b.entity_id,at=s)[0].hops==1
