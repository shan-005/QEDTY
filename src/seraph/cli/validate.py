from seraph.core.enums import EpistemicStatus
from seraph.core.version import PRODUCT_VERSION
from seraph.graph.schema import KEY


def validate() -> dict:
    return {
        "status": "ok",
        "product_version": PRODUCT_VERSION,
        "world_graph_schema": KEY,
        "epistemic_states": [s.value for s in EpistemicStatus],
    }
