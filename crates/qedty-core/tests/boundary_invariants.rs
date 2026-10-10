use qedty_core::{canonical_json, deterministic_id, ecef_wgs84};
use serde_json::json;

#[test]
fn canonical_json_sorts_nested_object_keys_without_changing_values() {
    let value = json!({
        "z": {"b": 2, "a": 1},
        "a": "1e-7 is text, not a number"
    });

    assert_eq!(
        canonical_json(&value).expect("JSON value should serialize"),
        r#"{"a":"1e-7 is text, not a number","z":{"a":1,"b":2}}"#
    );
}

#[test]
fn deterministic_id_enforces_kind_namespace_and_digest_length_boundaries() {
    let parts = [json!("entity-1")];

    assert!(deterministic_id("", "qedty", &parts, 12).is_err());
    assert!(deterministic_id("entity", " ", &parts, 12).is_err());
    assert!(deterministic_id("entity", "qedty", &parts, 0).is_err());
    assert!(deterministic_id("entity", "qedty", &parts, 65).is_err());

    let id = deterministic_id("entity", "qedty", &parts, 12)
        .expect("valid identity inputs should succeed");
    assert!(id.starts_with("entity:"));
    assert_eq!(id.len(), "entity:".len() + 12);
}

#[test]
fn deterministic_id_is_stable_for_identical_inputs() {
    let parts = [json!({"b": 2, "a": 1})];
    let first = deterministic_id("entity", "qedty", &parts, 32).unwrap();
    let second = deterministic_id("entity", "qedty", &parts, 32).unwrap();
    assert_eq!(first, second);
}

#[test]
fn wgs84_ecef_equator_origin_has_expected_axis_value() {
    let (x, y, z) = ecef_wgs84(0.0, 0.0, 0.0);
    assert!((x - 6_378_137.0).abs() < 1e-6);
    assert!(y.abs() < 1e-6);
    assert!(z.abs() < 1e-6);
}
