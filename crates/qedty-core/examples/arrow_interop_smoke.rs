use qedty_core::{
    arrow_interop::{decode_ipc_stream, encode_ipc_stream},
    columnar::{Column, ColumnarBatch},
};
use std::{collections::BTreeMap, env, fs};

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
    .expect("smoke-test sample must be valid")
}

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let args: Vec<_> = env::args_os().skip(1).collect();

    if args.len() != 2 {
        return Err("usage: arrow_interop_smoke RUST_OUTPUT.ipc PYTHON_INPUT.ipc".into());
    }

    fs::write(&args[0], encode_ipc_stream(&sample("rust"))?)?;

    let python_stream = fs::read(&args[1])?;
    let imported = decode_ipc_stream(&python_stream)?;

    assert_eq!(
        imported,
        sample("python"),
        "Rust must preserve PyArrow values, nulls, timestamps, and schema metadata"
    );

    println!("PASS: Rust IPC export created.");
    println!("PASS: Rust imported the PyArrow IPC stream exactly.");
    Ok(())
}
