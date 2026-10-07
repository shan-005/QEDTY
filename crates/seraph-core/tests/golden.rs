use seraph_core::{canonical_json, deterministic_id, ecef_wgs84};
use serde::Deserialize;
use serde_json::Value;

#[derive(Debug, Deserialize)]
struct IdentityVector {
    kind: String,
    namespace: String,
    parts: Vec<Value>,
    length: usize,
    expected_id: String,
}

#[derive(Debug, Deserialize)]
struct JsonVector {
    kind: String,
    value: Value,
    expected: String,
}

#[derive(Debug, Deserialize)]
struct GeometryVector {
    kind: String,
    latitude: f64,
    longitude: f64,
    height_m: f64,
    expected_ecef_m: [f64; 3],
    absolute_tolerance_m: f64,
}

#[test]
fn identity_vector_matches() {
    let raw = include_str!("../../../data/contracts/golden-vectors/core/identity.json");
    let vector: IdentityVector = serde_json::from_str(raw).unwrap();
    assert_eq!(vector.kind, "identity");
    let actual = deterministic_id(
        &vector.kind,
        &vector.namespace,
        &vector.parts,
        vector.length,
    )
    .unwrap();
    assert_eq!(actual, vector.expected_id);
}

#[test]
fn canonical_json_vector_matches() {
    let raw = include_str!("../../../data/contracts/golden-vectors/core/canonical_json.json");
    let vector: JsonVector = serde_json::from_str(raw).unwrap();
    assert_eq!(vector.kind, "canonical_json");
    assert_eq!(canonical_json(&vector.value).unwrap(), vector.expected);
}

#[test]
fn geometry_vector_matches() {
    let raw = include_str!("../../../data/contracts/golden-vectors/core/geometry_ecef.json");
    let vector: GeometryVector = serde_json::from_str(raw).unwrap();
    assert_eq!(vector.kind, "geometry_ecef");

    // ecef_wgs84 returns a tuple: (f64, f64, f64)
    let actual = ecef_wgs84(vector.latitude, vector.longitude, vector.height_m);

    // Convert the tuple to an array [f64; 3] so it implements IntoIterator
    let actual_array = [actual.0, actual.1, actual.2];

    for (a, e) in actual_array.into_iter().zip(vector.expected_ecef_m) {
        assert!((a - e).abs() <= vector.absolute_tolerance_m, "{a} != {e}");
    }
}
