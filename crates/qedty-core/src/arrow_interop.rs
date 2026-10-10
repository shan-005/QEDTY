//! Apache Arrow RecordBatch and IPC stream interoperability.
//!
//! Supported columns: Utf8, Int64, Float64, Boolean and UTC Timestamp(Millisecond).
//! Schema-level string metadata, nulls and typed timestamp values are preserved.
//! This IPC boundary is cross-process; it is not a zero-copy C Data Interface.

use crate::columnar::{Column, ColumnarBatch, ColumnarError};
use arrow_array::{
    Array, ArrayRef, BooleanArray, Float64Array, Int64Array, RecordBatch, StringArray,
    TimestampMillisecondArray,
};
use arrow_ipc::{reader::StreamReader, writer::StreamWriter};
use arrow_schema::{ArrowError, DataType, Field, Schema, TimeUnit};
use std::{
    collections::{BTreeMap, HashMap},
    io::Cursor,
    sync::Arc,
};
use thiserror::Error;

#[derive(Debug, Error)]
pub enum ArrowInteropError {
    #[error(transparent)]
    Arrow(#[from] ArrowError),
    #[error(transparent)]
    Columnar(#[from] ColumnarError),
    #[error("unsupported Arrow type for column {column}: {data_type}")]
    UnsupportedDataType { column: String, data_type: String },
    #[error("Arrow array for column {0} does not match its declared type")]
    InvalidArray(String),
    #[error("duplicate Arrow column name: {0}")]
    DuplicateColumn(String),
    #[error("an IPC stream contained no record batch")]
    EmptyStream,
    #[error("this IPC API requires exactly one record batch per stream")]
    MultipleBatches,
    #[error("an empty-schema batch with rows cannot be represented by ColumnarBatch")]
    EmptySchemaWithRows,
}

/// Convert a QEDTY batch into a real Arrow RecordBatch.
pub fn to_record_batch(batch: &ColumnarBatch) -> Result<RecordBatch, ArrowInteropError> {
    let mut fields = Vec::with_capacity(batch.column_count());
    let mut arrays: Vec<ArrayRef> = Vec::with_capacity(batch.column_count());

    for (name, column) in batch.columns() {
        let (data_type, array): (DataType, ArrayRef) = match column {
            Column::Utf8(values) => (DataType::Utf8, Arc::new(StringArray::from(values.clone()))),
            Column::Int64(values) => (DataType::Int64, Arc::new(Int64Array::from(values.clone()))),
            Column::Float64(values) => (
                DataType::Float64,
                Arc::new(Float64Array::from(values.clone())),
            ),
            Column::Boolean(values) => (
                DataType::Boolean,
                Arc::new(BooleanArray::from(values.clone())),
            ),
            Column::TimestampMillis(values) => (
                DataType::Timestamp(TimeUnit::Millisecond, Some("UTC".into())),
                Arc::new(TimestampMillisecondArray::from(values.clone()).with_timezone("UTC")),
            ),
        };

        fields.push(Field::new(name.clone(), data_type, true));
        arrays.push(array);
    }

    let metadata: HashMap<String, String> = batch
        .schema_metadata()
        .iter()
        .map(|(key, value)| (key.clone(), value.clone()))
        .collect();

    let schema = Arc::new(Schema::new_with_metadata(fields, metadata));
    Ok(RecordBatch::try_new(schema, arrays)?)
}

/// Convert supported Arrow arrays into a QEDTY batch.
/// Unsupported timestamp units/timezones and Arrow types are rejected rather than
/// silently coercing data and changing its meaning.
pub fn from_record_batch(batch: &RecordBatch) -> Result<ColumnarBatch, ArrowInteropError> {
    let schema = batch.schema();

    if schema.fields().is_empty() && batch.num_rows() != 0 {
        return Err(ArrowInteropError::EmptySchemaWithRows);
    }

    let mut columns = BTreeMap::new();

    for (index, field) in schema.fields().iter().enumerate() {
        let name = field.name().clone();
        let array = batch.column(index);

        let column = match field.data_type() {
            DataType::Utf8 => {
                let values = array
                    .as_any()
                    .downcast_ref::<StringArray>()
                    .ok_or_else(|| ArrowInteropError::InvalidArray(name.clone()))?;
                Column::Utf8(
                    values
                        .iter()
                        .map(|value| value.map(str::to_owned))
                        .collect(),
                )
            }
            DataType::Int64 => {
                let values = array
                    .as_any()
                    .downcast_ref::<Int64Array>()
                    .ok_or_else(|| ArrowInteropError::InvalidArray(name.clone()))?;
                Column::Int64(values.iter().collect())
            }
            DataType::Float64 => {
                let values = array
                    .as_any()
                    .downcast_ref::<Float64Array>()
                    .ok_or_else(|| ArrowInteropError::InvalidArray(name.clone()))?;
                Column::Float64(values.iter().collect())
            }
            DataType::Boolean => {
                let values = array
                    .as_any()
                    .downcast_ref::<BooleanArray>()
                    .ok_or_else(|| ArrowInteropError::InvalidArray(name.clone()))?;
                Column::Boolean(values.iter().collect())
            }
            DataType::Timestamp(TimeUnit::Millisecond, timezone)
                if timezone.as_deref() == Some("UTC") =>
            {
                let values = array
                    .as_any()
                    .downcast_ref::<TimestampMillisecondArray>()
                    .ok_or_else(|| ArrowInteropError::InvalidArray(name.clone()))?;
                Column::TimestampMillis(values.iter().collect())
            }
            other => {
                return Err(ArrowInteropError::UnsupportedDataType {
                    column: name,
                    data_type: other.to_string(),
                });
            }
        };

        if columns.insert(name.clone(), column).is_some() {
            return Err(ArrowInteropError::DuplicateColumn(name));
        }
    }

    let metadata = schema
        .metadata()
        .iter()
        .map(|(key, value)| (key.clone(), value.clone()))
        .collect::<BTreeMap<_, _>>();

    Ok(ColumnarBatch::try_new_with_metadata(columns, metadata)?)
}

/// Encode one QEDTY batch as a standards-based Arrow IPC stream.
pub fn encode_ipc_stream(batch: &ColumnarBatch) -> Result<Vec<u8>, ArrowInteropError> {
    let record_batch = to_record_batch(batch)?;
    let schema = record_batch.schema();
    let mut output = Vec::new();

    {
        let mut writer = StreamWriter::try_new(&mut output, &schema)?;
        writer.write(&record_batch)?;
        writer.finish()?;
    }

    Ok(output)
}

/// Decode exactly one RecordBatch from an Arrow IPC stream.
pub fn decode_ipc_stream(bytes: &[u8]) -> Result<ColumnarBatch, ArrowInteropError> {
    let mut reader = StreamReader::try_new(Cursor::new(bytes), None)?;
    let batch = reader
        .next()
        .transpose()?
        .ok_or(ArrowInteropError::EmptyStream)?;

    if reader.next().transpose()?.is_some() {
        return Err(ArrowInteropError::MultipleBatches);
    }

    from_record_batch(&batch)
}

#[cfg(test)]
mod tests {
    use super::{decode_ipc_stream, encode_ipc_stream, from_record_batch, to_record_batch};
    use crate::columnar::{Column, ColumnarBatch};
    use arrow_schema::{DataType, TimeUnit};
    use std::collections::BTreeMap;

    fn sample(origin: &str) -> ColumnarBatch {
        let mut columns = BTreeMap::new();
        columns.insert(
            "active".into(),
            Column::Boolean(vec![Some(true), None, Some(false)]),
        );
        columns.insert("count".into(), Column::Int64(vec![Some(1), None, Some(3)]));
        columns.insert(
            "event_time_ms".into(),
            Column::TimestampMillis(vec![Some(1_712_345_678_901), None, Some(-1)]),
        );
        columns.insert(
            "measurement".into(),
            Column::Float64(vec![Some(1.25), None, Some(-2.5)]),
        );
        columns.insert(
            "name".into(),
            Column::Utf8(vec![Some("alpha".into()), None, Some("gamma".into())]),
        );

        ColumnarBatch::try_new_with_metadata(
            columns,
            BTreeMap::from([
                ("qedty.contract".into(), "arrow-interop@1".into()),
                ("qedty.origin".into(), origin.into()),
            ]),
        )
        .unwrap()
    }

    #[test]
    fn record_batch_preserves_nulls_utc_timestamps_and_schema_metadata() {
        let original = sample("rust");
        let arrow = to_record_batch(&original).unwrap();

        assert_eq!(arrow.num_rows(), 3);
        assert_eq!(
            arrow
                .schema()
                .metadata()
                .get("qedty.contract")
                .map(String::as_str),
            Some("arrow-interop@1")
        );
        assert_eq!(
            arrow
                .schema()
                .field_with_name("event_time_ms")
                .unwrap()
                .data_type(),
            &DataType::Timestamp(TimeUnit::Millisecond, Some("UTC".into()))
        );

        let restored = from_record_batch(&arrow).unwrap();
        assert_eq!(restored, original);
    }

    #[test]
    fn ipc_stream_round_trip_preserves_all_supported_data() {
        let original = sample("rust");
        let stream = encode_ipc_stream(&original).unwrap();
        let restored = decode_ipc_stream(&stream).unwrap();
        assert_eq!(restored, original);
    }
}
