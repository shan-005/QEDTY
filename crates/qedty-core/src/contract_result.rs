//! Evidence-bearing result envelopes with deterministic metadata normalization.
//!
//! The field set and optional-field behavior mirror `src/qedty/core/contracts.py`.
//! Values and metadata remain JSON values so this layer does not impose domain
//! schemas on the Python semantic authority.

use serde_json::{Map, Value};
use thiserror::Error;

#[derive(Debug, Clone, Error, PartialEq, Eq)]
pub enum ContractResultError {
    #[error("contract result must be a JSON object")]
    NotObject,
    #[error("required field `{0}` is missing or has the wrong type")]
    MissingField(&'static str),
    #[error("`{0}` must contain string values")]
    InvalidStringList(&'static str),
    #[error("valid_at is not a supported timezone-aware RFC 3339 timestamp")]
    InvalidTimestamp,
    #[error("canonical serialization failed: {0}")]
    Canonical(String),
}

#[derive(Debug, Clone, PartialEq)]
pub struct ContractResult {
    value: Value,
    epistemic_state: String,
    evidence_ids: Vec<String>,
    provenance_ids: Vec<String>,
    assumptions: Vec<String>,
    model_id: Option<String>,
    model_version: Option<String>,
    valid_at: Option<String>,
    uncertainty: Option<Value>,
    metadata: Value,
}

fn required_string<'a>(
    value: &'a Value,
    field: &'static str,
) -> Result<&'a str, ContractResultError> {
    value
        .get(field)
        .and_then(Value::as_str)
        .ok_or(ContractResultError::MissingField(field))
}

fn optional_string(
    value: &Value,
    field: &'static str,
) -> Result<Option<String>, ContractResultError> {
    match value.get(field) {
        None | Some(Value::Null) => Ok(None),
        Some(Value::String(text)) if !text.trim().is_empty() => Ok(Some(text.clone())),
        _ => Err(ContractResultError::MissingField(field)),
    }
}

fn normalized_strings(
    value: &Value,
    field: &'static str,
) -> Result<Vec<String>, ContractResultError> {
    let values = value
        .get(field)
        .ok_or(ContractResultError::MissingField(field))?;
    let array = values
        .as_array()
        .ok_or(ContractResultError::MissingField(field))?;
    let mut output = Vec::with_capacity(array.len());
    for item in array {
        let text = item
            .as_str()
            .ok_or(ContractResultError::InvalidStringList(field))?
            .trim();
        // Match the Python reference helper: trim, discard blank values, then
        // sort and deduplicate the remaining identifiers/assumptions.
        if !text.is_empty() {
            output.push(text.to_owned());
        }
    }
    output.sort();
    output.dedup();
    Ok(output)
}

impl ContractResult {
    pub fn value(&self) -> &Value {
        &self.value
    }

    pub fn epistemic_state(&self) -> &str {
        &self.epistemic_state
    }

    pub fn evidence_ids(&self) -> &[String] {
        &self.evidence_ids
    }

    pub fn provenance_ids(&self) -> &[String] {
        &self.provenance_ids
    }

    pub fn assumptions(&self) -> &[String] {
        &self.assumptions
    }

    pub fn model_id(&self) -> Option<&str> {
        self.model_id.as_deref()
    }

    pub fn model_version(&self) -> Option<&str> {
        self.model_version.as_deref()
    }

    pub fn valid_at(&self) -> Option<&str> {
        self.valid_at.as_deref()
    }

    pub fn uncertainty(&self) -> Option<&Value> {
        self.uncertainty.as_ref()
    }

    pub fn metadata(&self) -> &Value {
        &self.metadata
    }

    /// Parse and normalize a Python/reference-shaped contract-result JSON value.
    pub fn from_value(input: &Value) -> Result<Self, ContractResultError> {
        if !input.is_object() {
            return Err(ContractResultError::NotObject);
        }
        let value = input
            .get("value")
            .cloned()
            .ok_or(ContractResultError::MissingField("value"))?;
        let epistemic_state = required_string(input, "epistemic_state")?.trim().to_owned();
        if epistemic_state.is_empty() {
            return Err(ContractResultError::MissingField("epistemic_state"));
        }
        let evidence_ids = normalized_strings(input, "evidence_ids")?;
        let provenance_ids = normalized_strings(input, "provenance_ids")?;
        let assumptions = normalized_strings(input, "assumptions")?;
        let metadata = input
            .get("metadata")
            .cloned()
            .unwrap_or_else(|| Value::Object(Map::new()));
        if !metadata.is_object() {
            return Err(ContractResultError::MissingField("metadata"));
        }
        let model_id = optional_string(input, "model_id")?;
        let model_version = optional_string(input, "model_version")?;
        let uncertainty = match input.get("uncertainty") {
            None | Some(Value::Null) => None,
            Some(value) => Some(value.clone()),
        };
        let valid_at = match input.get("valid_at") {
            None | Some(Value::Null) => None,
            Some(Value::String(timestamp)) => {
                let instant = crate::temporal::parse_rfc3339(timestamp)
                    .map_err(|_| ContractResultError::InvalidTimestamp)?;
                Some(
                    crate::temporal::to_rfc3339(instant)
                        .map_err(|_| ContractResultError::InvalidTimestamp)?,
                )
            }
            _ => return Err(ContractResultError::InvalidTimestamp),
        };
        Ok(Self {
            value,
            epistemic_state,
            evidence_ids,
            provenance_ids,
            assumptions,
            model_id,
            model_version,
            valid_at,
            uncertainty,
            metadata,
        })
    }

    /// Convert into the reference envelope shape. Optional fields are omitted when absent.
    pub fn to_value(&self) -> Value {
        let mut object = Map::new();
        object.insert("value".to_owned(), self.value.clone());
        object.insert(
            "epistemic_state".to_owned(),
            Value::String(self.epistemic_state.clone()),
        );
        object.insert(
            "evidence_ids".to_owned(),
            serde_json::json!(self.evidence_ids),
        );
        object.insert(
            "provenance_ids".to_owned(),
            serde_json::json!(self.provenance_ids),
        );
        object.insert(
            "assumptions".to_owned(),
            serde_json::json!(self.assumptions),
        );
        object.insert("metadata".to_owned(), self.metadata.clone());
        if let Some(value) = &self.model_id {
            object.insert("model_id".to_owned(), Value::String(value.clone()));
        }
        if let Some(value) = &self.model_version {
            object.insert("model_version".to_owned(), Value::String(value.clone()));
        }
        if let Some(value) = &self.valid_at {
            object.insert("valid_at".to_owned(), Value::String(value.clone()));
        }
        if let Some(value) = &self.uncertainty {
            object.insert("uncertainty".to_owned(), value.clone());
        }
        Value::Object(object)
    }

    /// Serialize using QEDTY's established canonical JSON profile.
    pub fn canonical_json(&self) -> Result<String, ContractResultError> {
        crate::canonical_json(&self.to_value())
            .map_err(|error| ContractResultError::Canonical(error.to_string()))
    }

    pub fn with_evidence<I, S>(&self, additions: I) -> Self
    where
        I: IntoIterator<Item = S>,
        S: AsRef<str>,
    {
        let mut clone = self.clone();
        clone.evidence_ids.extend(
            additions
                .into_iter()
                .map(|item| item.as_ref().trim().to_owned())
                .filter(|item| !item.is_empty()),
        );
        clone.evidence_ids.sort();
        clone.evidence_ids.dedup();
        clone
    }

    pub fn with_assumptions<I, S>(&self, additions: I) -> Self
    where
        I: IntoIterator<Item = S>,
        S: AsRef<str>,
    {
        let mut clone = self.clone();
        clone.assumptions.extend(
            additions
                .into_iter()
                .map(|item| item.as_ref().trim().to_owned())
                .filter(|item| !item.is_empty()),
        );
        clone.assumptions.sort();
        clone.assumptions.dedup();
        clone
    }
}

#[cfg(test)]
mod tests {
    use super::ContractResult;
    use serde_json::Value;

    #[test]
    fn sorts_deduplicates_and_normalizes_timestamp() {
        let raw = r#"{"value":{"ok":true},"epistemic_state":"modeled","evidence_ids":["e2","e1","e1"],"provenance_ids":["p2","p1"],"assumptions":["a2","a1","a1"],"valid_at":"2026-10-06T00:00:00Z","metadata":{}}"#;
        let result =
            ContractResult::from_value(&serde_json::from_str::<Value>(raw).unwrap()).unwrap();
        assert_eq!(result.evidence_ids, vec!["e1".to_owned(), "e2".to_owned()]);
        assert_eq!(
            result.provenance_ids,
            vec!["p1".to_owned(), "p2".to_owned()]
        );
        assert_eq!(result.assumptions, vec!["a1".to_owned(), "a2".to_owned()]);
        assert_eq!(
            result.valid_at.as_deref(),
            Some("2026-10-06T00:00:00.000000Z")
        );
    }

    #[test]
    fn rejects_naive_timestamps_and_invalid_ids() {
        let raw = r#"{"value":1,"epistemic_state":"modeled","evidence_ids":[""],"provenance_ids":[],"assumptions":[],"valid_at":"2026-10-06T00:00:00","metadata":{}}"#;
        assert!(ContractResult::from_value(&serde_json::from_str::<Value>(raw).unwrap()).is_err());
    }
}
