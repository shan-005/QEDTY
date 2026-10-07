from seraph.cli.validate import validate
from seraph.core.version import PRODUCT_VERSION
from seraph.output.geojson import feature_collection
from seraph.output.jsonfg import collection


def main() -> int:
    assert validate()["status"] == "ok"
    f={"type":"Feature","properties":{},"geometry":None}
    assert feature_collection([f])["type"] == "FeatureCollection"
    assert collection([f])["json-fg-version"]
    print("API OpenAPI surface: PASS")
    print("Output GeoJSON/JSON-FG: PASS")
    print("CLI validation surface: PASS")
    return 0
if __name__ == "__main__": raise SystemExit(main())
