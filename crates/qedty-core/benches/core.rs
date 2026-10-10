//! Criterion benchmarks for the stable QEDTY Rust kernel surface.
//!
//! These are measurement harnesses, not claims of performance superiority.

use criterion::{black_box, criterion_group, criterion_main, Criterion};
use qedty_core::columnar::{Column, ColumnarBatch};
use qedty_core::graph::DirectedGraph;
use qedty_core::quantity::convert_value;
use qedty_core::{canonical_json, deterministic_id, ecef_wgs84};
use serde_json::json;
use std::collections::BTreeMap;

fn bench_canonical_json(c: &mut Criterion) {
    let payload = json!({
        "contract": "qedty.benchmark@1",
        "entities": (0..64)
            .map(|index| json!({
                "id": format!("entity-{index:04}"),
                "attributes": {
                    "region": "north",
                    "index": index,
                    "critical": index % 7 == 0,
                    "tags": ["planetary", "continuity", "benchmark"]
                }
            }))
            .collect::<Vec<_>>()
    });

    c.bench_function("canonical_json/64_entities", |b| {
        b.iter(|| canonical_json(black_box(&payload)).expect("benchmark JSON is serializable"))
    });
}

fn bench_deterministic_id(c: &mut Criterion) {
    let parts = vec![
        json!("infrastructure:node:west-001"),
        json!({
            "region": "west",
            "tags": ["power", "transmission"],
            "coordinates": [-122.4194, 37.7749]
        }),
    ];

    c.bench_function("identity/two_structured_parts", |b| {
        b.iter(|| {
            deterministic_id("entity", "criterion-benchmark", black_box(&parts), 32)
                .expect("benchmark identity input is valid")
        })
    });
}

fn bench_ecef(c: &mut Criterion) {
    c.bench_function("geodesy/wgs84_ecef", |b| {
        b.iter(|| ecef_wgs84(black_box(37.7749), black_box(-122.4194), black_box(30.0)))
    });
}

fn bench_quantity_conversion(c: &mut Criterion) {
    c.bench_function("quantity/convert_km_to_m", |b| {
        b.iter(|| {
            convert_value(black_box(12.345), "km", "m")
                .expect("kilometres-to-metres conversion is supported")
        })
    });
}

fn benchmark_graph() -> DirectedGraph {
    let mut graph = DirectedGraph::new();
    for index in 0..64 {
        graph
            .add_node(&format!("node-{index:03}"))
            .expect("generated node label is valid");
    }
    for index in 0..63 {
        let from = format!("node-{index:03}");
        let next = format!("node-{:03}", index + 1);
        graph
            .add_edge(&from, &next, 1.0, 0.99, 100.0)
            .expect("generated graph edge is valid");
        if index + 2 < 64 {
            let skip = format!("node-{:03}", index + 2);
            graph
                .add_edge(&from, &skip, 1.5, 0.98, 50.0)
                .expect("generated graph edge is valid");
        }
    }
    graph
}

fn bench_graph_shortest_path(c: &mut Criterion) {
    let graph = benchmark_graph();
    c.bench_function("graph/shortest_path_64_nodes", |b| {
        b.iter(|| {
            black_box(
                graph
                    .shortest_path(black_box("node-000"), black_box("node-063"))
                    .expect("benchmark endpoints exist"),
            )
        })
    });
}

fn bench_columnar_materialization(c: &mut Criterion) {
    let mut columns = BTreeMap::new();
    columns.insert(
        "entity_id".to_owned(),
        Column::Utf8(
            (0..512)
                .map(|index| Some(format!("entity-{index:04}")))
                .collect(),
        ),
    );
    columns.insert(
        "score".to_owned(),
        Column::Float64((0..512).map(|index| Some(index as f64 / 10.0)).collect()),
    );
    columns.insert(
        "active".to_owned(),
        Column::Boolean((0..512).map(|index| Some(index % 3 == 0)).collect()),
    );
    let batch = ColumnarBatch::try_new(columns).expect("generated columnar batch is valid");

    c.bench_function("columnar/to_json_rows_512", |b| {
        b.iter(|| black_box(batch.to_json_rows()))
    });
}

criterion_group!(
    benches,
    bench_canonical_json,
    bench_deterministic_id,
    bench_ecef,
    bench_quantity_conversion,
    bench_graph_shortest_path,
    bench_columnar_materialization
);
criterion_main!(benches);
