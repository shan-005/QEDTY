use qedty_core::canonical_json;
use serde_json::Value;

#[test]
fn previously_discovered_numeric_inputs_are_idempotent() {
    // Retain the numeric inputs associated with the earlier libFuzzer failure.
    // These are deterministic regressions, not substitutes for fuzz campaigns.
    let inputs = [
        "191919183982383838398",
        "1.9191918398238386e+20",
        "0.920333333333333333333",
    ];

    for raw in inputs {
        let parsed: Value = serde_json::from_str(raw).expect("regression input must be valid JSON");
        let canonical = canonical_json(&parsed).expect("parsed JSON must be canonicalizable");
        let reparsed: Value =
            serde_json::from_str(&canonical).expect("canonical output must parse");
        let canonical_again =
            canonical_json(&reparsed).expect("reparsed value must be canonicalizable");

        assert_eq!(
            canonical, canonical_again,
            "canonicalization was not idempotent for input {raw}"
        );
    }
}

#[test]
fn canonicalization_does_not_change_numeric_text_inside_strings() {
    let parsed: Value = serde_json::from_str(r#"{"number":"1e-7","text":"value 1e+20"}"#).unwrap();

    assert_eq!(
        canonical_json(&parsed).unwrap(),
        r#"{"number":"1e-7","text":"value 1e+20"}"#
    );
}
