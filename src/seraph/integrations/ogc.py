from seraph.spatial.models import Point
from seraph.spatial.jsonfg import feature
def jsonfg_for_entity(entity_id:str,name:str,point:Point):return feature(entity_id,point,feature_type=name)
