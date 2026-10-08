from typing import Any

from qedty.core.enums import EpistemicStatus
from qedty.core.version import PRODUCT_VERSION
from qedty.graph.schema import KEY


def validate() -> dict[str, Any]:
    return {
        "status": "ok",
        "product_version": PRODUCT_VERSION,
        "world_graph_schema": KEY,
        "epistemic_states": [s.value for s in EpistemicStatus],
        "api_contract": "1.0.0",
        "output_formats": ["json", "geojson", "json-fg", "csv", "markdown"],
    }
