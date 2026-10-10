use qedty_core::contract_result::ContractResult;
use qedty_core::quantity::{convert_value, format_value};
use serde_json::Value;

#[test]
fn quantity_fixture_matches_reference_semantics() {
    let raw = include_str!("../../../data/contracts/golden-vectors/core/quantity.json")
        .trim_start_matches('\u{feff}');
    let vector: Value = serde_json::from_str(raw).unwrap();
    assert_eq!(vector["kind"], "quantity");
    let value = vector["value"].as_str().unwrap().parse::<f64>().unwrap();
    let actual = format_value(
        convert_value(
            value,
            vector["from_unit"].as_str().unwrap(),
            vector["to_unit"].as_str().unwrap(),
        )
        .unwrap(),
    )
    .unwrap();
    assert_eq!(actual, vector["expected_value"].as_str().unwrap());
}

#[test]
fn contract_result_fixture_matches_reference_canonical_json() {
    let raw = include_str!("../../../data/contracts/golden-vectors/core/contract_result.json")
        .trim_start_matches('\u{feff}');
    let vector: Value = serde_json::from_str(raw).unwrap();
    let result = ContractResult::from_value(&vector).unwrap();
    assert_eq!(
        result.canonical_json().unwrap(),
        vector["expected_canonical_json"].as_str().unwrap()
    );
}

#[test]
fn graph_fixture_is_present_and_contains_expected_cases() {
    let raw = include_str!("../../../tests/graph_golden_vectors.json");
    let value: Value = serde_json::from_str(raw).unwrap();
    let vectors = value["vectors"].as_array().unwrap();
    assert_eq!(vectors.len(), 8);
    assert!(vectors
        .iter()
        .any(|item| item["name"] == "weighted_shortest_path"));
    assert!(vectors
        .iter()
        .any(|item| item["name"] == "spatial_delegate"));
}

#[test]
fn canonical_json_is_idempotent_for_large_integer_fallback() {
    let input = "191919183982383838398";
    let value: Value = serde_json::from_str(input).expect("reported fuzz input must parse");

    let canonical = qedty_core::canonical_json(&value).expect("value must canonicalize");
    let reparsed: Value = serde_json::from_str(&canonical).expect("canonical output must parse");
    let canonical_again =
        qedty_core::canonical_json(&reparsed).expect("reparsed value must canonicalize");

    assert_eq!(
        canonical, canonical_again,
        "regression for canonical_json fuzz finding: {input}"
    );
}
