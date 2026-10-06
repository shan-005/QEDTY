from __future__ import annotations
from typing import Any
from seraph.spatial.geojson import point_feature
def feature_collection(features:list[dict[str,Any]])->dict[str,Any]:return {"type":"FeatureCollection","features":features}
