pub mod geometry;

use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::collections::BTreeMap;
use thiserror::Error;

pub const CORE_CONTRACT_VERSION: &str = "1.0.0";
pub const HASH_ALGORITHM: &str = "SHA-256";
pub const CANONICAL_JSON_PROFILE: &str = "qedty-canonical-json@1";

#[derive(Debug, Error)]
pub enum CoreError {
    #[error("identity input must not be empty")]
    EmptyIdentity,
    #[error("identity digest length must be between 1 and 64")]
    InvalidDigestLength,
    #[error("canonical JSON serialization failed: {0}")]
    Json(#[from] serde_json::Error),
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct EntityRef {
    pub entity_id: String,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct TimeWindow {
    pub start: String,
    pub end: String,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct Quantity {
    pub value: String,
    pub unit: String,
}

fn sort_json(value: serde_json::Value) -> serde_json::Value {
    match value {
        serde_json::Value::Object(map) => {
            let mut sorted = BTreeMap::new();
            for (key, value) in map {
                sorted.insert(key, sort_json(value));
            }
            serde_json::Value::Object(sorted.into_iter().collect())
        }
        serde_json::Value::Array(values) => {
            serde_json::Value::Array(values.into_iter().map(sort_json).collect())
        }
        other => other,
    }
}

pub fn canonical_json<T: Serialize>(value: &T) -> Result<String, CoreError> {
    let raw = serde_json::to_value(value)?;
    let sorted = sort_json(raw);
    let serialized = serde_json::to_string(&sorted)?;
    Ok(normalize_python_exponent_notation(&serialized))
}

/// Match Python's JSON float exponent spelling without changing string values.
///
/// Python's json encoder pads one-digit exponents (for example, `1e-7` becomes
/// `1e-07`). serde_json uses the same shortest-roundtrip numeric value but may
/// omit that leading zero. QEDTY's existing canonical JSON profile is defined by
/// the Python reference, so this formatting difference must not change canonical
/// bytes or SHA-256 identities.
fn normalize_python_exponent_notation(json: &str) -> String {
    let bytes = json.as_bytes();
    let mut output = String::with_capacity(json.len() + 8);
    let mut index = 0;

    while index < bytes.len() {
        if bytes[index] == b'"' {
            let start = index;
            index += 1;
            let mut escaped = false;
            while index < bytes.len() {
                let byte = bytes[index];
                index += 1;
                if escaped {
                    escaped = false;
                } else if byte == b'\\' {
                    escaped = true;
                } else if byte == b'"' {
                    break;
                }
            }
            output.push_str(&json[start..index]);
            continue;
        }

        let starts_number = bytes[index].is_ascii_digit()
            || (bytes[index] == b'-'
                && index + 1 < bytes.len()
                && bytes[index + 1].is_ascii_digit());
        if starts_number {
            let start = index;
            while index < bytes.len()
                && matches!(
                    bytes[index],
                    b'0'..=b'9' | b'.' | b'e' | b'E' | b'+' | b'-'
                )
            {
                index += 1;
            }
            output.push_str(&normalize_python_exponent_token(&json[start..index]));
            continue;
        }

        // Outside strings, valid JSON syntax is ASCII. Non-ASCII bytes are
        // copied as part of a string above, preserving UTF-8 exactly.
        output.push(char::from(bytes[index]));
        index += 1;
    }

    output
}

fn normalize_python_exponent_token(token: &str) -> String {
    let exponent_index = match token.find('e').or_else(|| token.find('E')) {
        Some(index) => index,
        None => return token.to_owned(),
    };
    let mantissa = &token[..exponent_index];
    let exponent = &token[exponent_index + 1..];
    let (sign, digits) = if let Some(digits) = exponent.strip_prefix('-') {
        ("-", digits)
    } else if let Some(digits) = exponent.strip_prefix('+') {
        ("+", digits)
    } else {
        ("+", exponent)
    };
    let digits = digits.trim_start_matches('0');
    let digits = if digits.is_empty() { "0" } else { digits };

    if digits.len() < 2 {
        format!("{mantissa}e{sign}0{digits}")
    } else {
        format!("{mantissa}e{sign}{digits}")
    }
}

pub fn sha256_hex<T: Serialize>(value: &T) -> Result<String, CoreError> {
    let json = canonical_json(value)?;
    let digest = Sha256::digest(json.as_bytes());
    Ok(format!("{digest:x}"))
}

pub fn deterministic_id(
    kind: &str,
    namespace: &str,
    parts: &[serde_json::Value],
    length: usize,
) -> Result<String, CoreError> {
    if kind.trim().is_empty() || namespace.trim().is_empty() || !(1..=64).contains(&length) {
        return Err(if kind.trim().is_empty() || namespace.trim().is_empty() {
            CoreError::EmptyIdentity
        } else {
            CoreError::InvalidDigestLength
        });
    }
    let mut identity_parts = Vec::with_capacity(parts.len() + 1);
    identity_parts.push(serde_json::Value::String(namespace.to_owned()));
    identity_parts.extend(parts.iter().cloned());
    let preimage = serde_json::json!({
        "kind": kind,
        "parts": identity_parts,
    });
    let digest = sha256_hex(&preimage)?;
    Ok(format!("{}:{}", kind, &digest[..length]))
}

pub fn ecef_wgs84(latitude_deg: f64, longitude_deg: f64, height_m: f64) -> (f64, f64, f64) {
    const A: f64 = 6_378_137.0;
    const INV_F: f64 = 298.257223563;
    let f = 1.0 / INV_F;
    let lat = latitude_deg.to_radians();
    let lon = longitude_deg.to_radians();
    let sin_lat = lat.sin();
    let cos_lat = lat.cos();
    let n = A / (1.0 - (2.0 * f - f * f) * sin_lat * sin_lat).sqrt();
    (
        (n + height_m) * cos_lat * lon.cos(),
        (n + height_m) * cos_lat * lon.sin(),
        ((1.0 - f).powi(2) * n + height_m) * sin_lat,
    )
}

#[cfg(test)]
mod canonical_json_tests {
    use super::canonical_json;

    #[test]
    fn canonical_json_matches_python_float_exponent_notation() {
        let value = serde_json::json!({
            "zero": -0.0,
            "positive_small": 1e-7,
            "negative_small": -1e-7,
            "positive_large": 1e+20,
            "fixed": 0.0001,
            "as_string": "1e-07",
        });

        assert_eq!(
            canonical_json(&value).expect("JSON value should serialize"),
            r#"{"as_string":"1e-07","fixed":0.0001,"negative_small":-1e-07,"positive_large":1e+20,"positive_small":1e-07,"zero":-0.0}"#
        );
    }

    #[test]
    fn canonical_json_does_not_rewrite_exponent_text_inside_strings() {
        let value = serde_json::json!({"value": "not-a-number: 1e-7"});
        assert_eq!(
            canonical_json(&value).expect("JSON value should serialize"),
            r#"{"value":"not-a-number: 1e-7"}"#
        );
    }
}
