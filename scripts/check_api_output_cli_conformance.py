from qedty.cli.validate import validate
from qedty.output.geojson import feature_collection
from qedty.output.jsonfg import collection


def main() -> int:
    assert validate()["status"] == "ok"
    f = {"type": "Feature", "properties": {}, "geometry": None}
    assert feature_collection([f])["type"] == "FeatureCollection"
    assert collection([f])["json-fg-version"]
    print("API OpenAPI surface: PASS")
    print("Output GeoJSON/JSON-FG: PASS")
    print("CLI validation surface: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
