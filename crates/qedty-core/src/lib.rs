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
    Ok(serde_json::to_string(&sorted)?)
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
