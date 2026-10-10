//! Arrow-neutral, deterministic columnar batch boundary.
//!
//! This small type checks common columnar invariants without adding an Arrow
//! dependency to the core workspace. It is an adapter seam, not Arrow IPC or the
//! Arrow C Data Interface; a production Arrow adapter remains a separate package
//! and requires schema-specific cross-language conformance vectors.

use serde_json::{Map, Number, Value};
use std::collections::BTreeMap;
use thiserror::Error;

#[derive(Debug, Clone, PartialEq)]
pub enum Column {
    Utf8(Vec<Option<String>>),
    Int64(Vec<Option<i64>>),
    Float64(Vec<Option<f64>>),
    Boolean(Vec<Option<bool>>),
    /// Unix-epoch milliseconds with Arrow timezone fixed to UTC.
    TimestampMillis(Vec<Option<i64>>),
}

impl Column {
    pub fn len(&self) -> usize {
        match self {
            Self::Utf8(v) => v.len(),
            Self::Int64(v) => v.len(),
            Self::Float64(v) => v.len(),
            Self::Boolean(v) => v.len(),
            Self::TimestampMillis(v) => v.len(),
        }
    }
    pub fn is_empty(&self) -> bool {
        self.len() == 0
    }
    fn value_at(&self, index: usize) -> Value {
        match self {
            Self::Utf8(values) => values[index]
                .clone()
                .map(Value::String)
                .unwrap_or(Value::Null),
            Self::Int64(values) => values[index]
                .map(|v| Value::Number(Number::from(v)))
                .unwrap_or(Value::Null),
            Self::Float64(values) => values[index]
                .and_then(Number::from_f64)
                .map(Value::Number)
                .unwrap_or(Value::Null),
            Self::Boolean(values) => values[index].map(Value::Bool).unwrap_or(Value::Null),
            Self::TimestampMillis(values) => values[index]
                .map(|v| Value::Number(Number::from(v)))
                .unwrap_or(Value::Null),
        }
    }
}

#[derive(Debug, Clone, Error, PartialEq, Eq)]
pub enum ColumnarError {
    #[error("column name must not be blank")]
    BlankColumn,
    #[error("all columns must have equal lengths")]
    LengthMismatch,
    #[error("Float64 column values must be finite or null")]
    NonFiniteFloat,
}

#[derive(Debug, Clone, PartialEq)]
pub struct ColumnarBatch {
    columns: BTreeMap<String, Column>,
    row_count: usize,
    schema_metadata: BTreeMap<String, String>,
}

impl ColumnarBatch {
    pub fn try_new(columns: BTreeMap<String, Column>) -> Result<Self, ColumnarError> {
        Self::try_new_with_metadata(columns, BTreeMap::new())
    }

    pub fn try_new_with_metadata(
        columns: BTreeMap<String, Column>,
        schema_metadata: BTreeMap<String, String>,
    ) -> Result<Self, ColumnarError> {
        let mut expected_len = None;
        for (name, column) in &columns {
            if name.trim().is_empty() {
                return Err(ColumnarError::BlankColumn);
            }
            if let Some(length) = expected_len {
                if column.len() != length {
                    return Err(ColumnarError::LengthMismatch);
                }
            } else {
                expected_len = Some(column.len());
            }
            if let Column::Float64(values) = column {
                if values.iter().flatten().any(|value| !value.is_finite()) {
                    return Err(ColumnarError::NonFiniteFloat);
                }
            }
        }
        Ok(Self {
            row_count: expected_len.unwrap_or(0),
            columns,
            schema_metadata,
        })
    }

    pub fn row_count(&self) -> usize {
        self.row_count
    }
    pub fn column_count(&self) -> usize {
        self.columns.len()
    }
    pub fn columns(&self) -> &BTreeMap<String, Column> {
        &self.columns
    }
    pub fn schema_metadata(&self) -> &BTreeMap<String, String> {
        &self.schema_metadata
    }

    pub fn row(&self, index: usize) -> Option<Value> {
        if index >= self.row_count {
            return None;
        }
        let mut object = Map::new();
        for (name, column) in &self.columns {
            object.insert(name.clone(), column.value_at(index));
        }
        Some(Value::Object(object))
    }

    pub fn to_json_rows(&self) -> Vec<Value> {
        (0..self.row_count)
            .filter_map(|index| self.row(index))
            .collect()
    }
}

#[cfg(test)]
mod tests {
    use super::{Column, ColumnarBatch, ColumnarError};
    use std::collections::BTreeMap;

    #[test]
    fn orders_columns_and_preserves_nulls() {
        let mut columns = BTreeMap::new();
        columns.insert(
            "name".into(),
            Column::Utf8(vec![Some("alpha".into()), None]),
        );
        columns.insert("value".into(), Column::Float64(vec![Some(2.5), Some(0.0)]));
        let batch = ColumnarBatch::try_new(columns).unwrap();
        assert_eq!(batch.row_count(), 2);
        assert_eq!(batch.row(0).unwrap()["name"], "alpha");
        assert_eq!(batch.row(1).unwrap()["name"], serde_json::Value::Null);
        assert!(batch.row(2).is_none());
    }

    #[test]
    fn rejects_mismatched_lengths_and_non_finite_numbers() {
        let mut columns = BTreeMap::new();
        columns.insert("a".into(), Column::Int64(vec![Some(1)]));
        columns.insert("b".into(), Column::Boolean(vec![Some(true), Some(false)]));
        assert_eq!(
            ColumnarBatch::try_new(columns),
            Err(ColumnarError::LengthMismatch)
        );
        let mut columns = BTreeMap::new();
        columns.insert("x".into(), Column::Float64(vec![Some(f64::INFINITY)]));
        assert_eq!(
            ColumnarBatch::try_new(columns),
            Err(ColumnarError::NonFiniteFloat)
        );
    }
}
