from seraph.core.enums import EpistemicStatus
from seraph.graph.schema import KEY
from seraph.core.version import PRODUCT_VERSION
def validate()->dict:return {"status":"ok","product_version":PRODUCT_VERSION,"world_graph_schema":KEY,"epistemic_states":[s.value for s in EpistemicStatus]}
