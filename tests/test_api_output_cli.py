from seraph.cli.validate import validate
from seraph.output.geojson import feature, feature_collection
from seraph.output.json import dumps


def test_json_and_geojson_contracts() -> None:
    f = feature({"x": 1}, feature_id="a")
    fc = feature_collection([f])
    assert fc["type"] == "FeatureCollection"
    assert '"type": "FeatureCollection"' in dumps(fc)


def test_cli_validation_surface() -> None:
    v = validate()
    assert v["status"] == "ok"
    assert "geojson" in v["output_formats"]
