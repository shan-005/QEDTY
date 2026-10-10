//! Expanded native conformance runner for quantities, contract results and graph kernels.
use qedty_core::contract_result::ContractResult;
use qedty_core::graph::DirectedGraph;
use qedty_core::quantity::{convert_value, format_value};
use qedty_core::spatial::{haversine_m, GeoPoint};
use qedty_core::{canonical_json, sha256_hex};
use serde_json::Value;
use std::error::Error;
use std::io;
use std::path::{Path, PathBuf};

fn invalid(message: impl Into<String>) -> io::Error {
    io::Error::new(io::ErrorKind::InvalidData, message.into())
}
fn root() -> PathBuf {
    Path::new(env!("CARGO_MANIFEST_DIR")).join("../../..")
}
fn read_json(path: &Path) -> Result<Value, Box<dyn Error>> {
    let raw = std::fs::read_to_string(path)?;
    Ok(serde_json::from_str(raw.trim_start_matches('\u{feff}'))?)
}
fn string<'a>(value: &'a Value, key: &'static str) -> Result<&'a str, Box<dyn Error>> {
    value
        .get(key)
        .and_then(Value::as_str)
        .ok_or_else(|| invalid(format!("missing string field `{key}`")).into())
}
fn find_vector<'a>(document: &'a Value, name: &str) -> Result<&'a Value, Box<dyn Error>> {
    document
        .get("vectors")
        .and_then(Value::as_array)
        .and_then(|vectors| {
            vectors
                .iter()
                .find(|vector| vector.get("name").and_then(Value::as_str) == Some(name))
        })
        .ok_or_else(|| invalid(format!("missing graph vector `{name}`")).into())
}
fn expected_labels(vector: &Value, field: &str, actual: &[String]) -> Result<(), Box<dyn Error>> {
    let expected = vector
        .get(field)
        .and_then(Value::as_array)
        .ok_or_else(|| invalid(format!("missing array `{field}`")))?;
    let labels: Vec<&str> = expected
        .iter()
        .map(|item| {
            item.as_str()
                .ok_or_else(|| invalid(format!("non-string label in `{field}`")))
        })
        .collect::<Result<_, _>>()?;
    if labels != actual.iter().map(String::as_str).collect::<Vec<_>>() {
        return Err(invalid(format!("{field}: actual={actual:?}, expected={labels:?}")).into());
    }
    Ok(())
}

fn check_quantity(vector_dir: &Path) -> Result<(), Box<dyn Error>> {
    let vector = read_json(&vector_dir.join("quantity.json"))?;
    if string(&vector, "kind")? != "quantity" {
        return Err(invalid("quantity vector has unexpected kind").into());
    }
    let value: f64 = string(&vector, "value")?.parse()?;
    let actual = format_value(convert_value(
        value,
        string(&vector, "from_unit")?,
        string(&vector, "to_unit")?,
    )?)?;
    let expected = string(&vector, "expected_value")?;
    if actual != expected {
        return Err(invalid(format!(
            "quantity mismatch: actual={actual}, expected={expected}"
        ))
        .into());
    }
    println!("PASS core/quantity.json");
    Ok(())
}

fn check_contract_result(vector_dir: &Path) -> Result<(), Box<dyn Error>> {
    let vector = read_json(&vector_dir.join("contract_result.json"))?;
    if string(&vector, "kind")? != "contract_result" {
        return Err(invalid("contract result vector has unexpected kind").into());
    }
    let result = ContractResult::from_value(&vector)?;
    let actual = result.canonical_json()?;
    let expected = string(&vector, "expected_canonical_json")?;
    if actual != expected {
        return Err(invalid(format!(
            "contract-result mismatch: actual={actual}, expected={expected}"
        ))
        .into());
    }
    println!("PASS core/contract_result.json");
    Ok(())
}

fn check_graph_vectors(root: &Path) -> Result<(), Box<dyn Error>> {
    let document = read_json(&root.join("tests/graph_golden_vectors.json"))?;
    let temporal = find_vector(&document, "temporal_chain")?;
    let mut graph = DirectedGraph::new();
    graph.add_edge("a", "b", 1.0, 1.0, 0.0)?;
    graph.add_edge("b", "c", 1.0, 1.0, 0.0)?;
    expected_labels(temporal, "bfs_labels", &graph.breadth_first("a")?)?;
    if graph.edge_count()
        != temporal["active_relationships"]
            .as_u64()
            .ok_or_else(|| invalid("invalid active_relationships"))? as usize
        || graph.node_count()
            != temporal["snapshot_entities"]
                .as_u64()
                .ok_or_else(|| invalid("invalid snapshot_entities"))? as usize
    {
        return Err(invalid("temporal_chain graph cardinality mismatch").into());
    }

    let reliability = find_vector(&document, "reliability_preference")?;
    let mut graph = DirectedGraph::new();
    graph.add_edge("a", "c", 1.0, 0.3, 0.0)?;
    graph.add_edge("a", "b", 1.0, 0.9, 0.0)?;
    graph.add_edge("b", "c", 1.0, 0.9, 0.0)?;
    let path = graph
        .most_reliable_path("a", "c")?
        .ok_or_else(|| invalid("expected a reliability path"))?;
    expected_labels(reliability, "best_path_labels", &path.nodes)?;
    if (path.score
        - reliability["best_path_score"]
            .as_f64()
            .ok_or_else(|| invalid("invalid best_path_score"))?)
    .abs()
        > 1e-12
    {
        return Err(invalid("best reliability score mismatch").into());
    }

    let shortest = find_vector(&document, "weighted_shortest_path")?;
    let mut graph = DirectedGraph::new();
    graph.add_edge("a", "c", 10.0, 1.0, 0.0)?;
    graph.add_edge("a", "b", 1.0, 1.0, 0.0)?;
    graph.add_edge("b", "c", 2.0, 1.0, 0.0)?;
    let path = graph
        .shortest_path("a", "c")?
        .ok_or_else(|| invalid("expected shortest path"))?;
    expected_labels(shortest, "shortest_path_labels", &path.nodes)?;
    if (path.score
        - shortest["shortest_path_cost"]
            .as_f64()
            .ok_or_else(|| invalid("invalid shortest_path_cost"))?)
    .abs()
        > 1e-12
    {
        return Err(invalid("shortest path cost mismatch").into());
    }

    let connectivity = find_vector(&document, "connectivity")?;
    if graph.strongly_connected_components().len()
        != connectivity["strong_component_count"]
            .as_u64()
            .ok_or_else(|| invalid("invalid strong_component_count"))? as usize
        || graph.weak_components().len()
            != connectivity["weak_component_count"]
                .as_u64()
                .ok_or_else(|| invalid("invalid weak_component_count"))? as usize
    {
        return Err(invalid("connectivity component count mismatch").into());
    }
    let centrality = find_vector(&document, "centrality")?;
    let ranks = graph.pagerank(100, 0.85)?;
    let rank_sum: f64 = ranks.values().sum();
    if (rank_sum
        - centrality["pagerank_sum"]
            .as_f64()
            .ok_or_else(|| invalid("invalid pagerank_sum"))?)
    .abs()
        > 1e-12
    {
        return Err(invalid("PageRank normalization mismatch").into());
    }

    let flow = find_vector(&document, "max_flow")?;
    let mut graph = DirectedGraph::new();
    graph.add_edge("s", "a", 1.0, 1.0, 0.4)?;
    graph.add_edge("s", "b", 1.0, 1.0, 0.4)?;
    graph.add_edge("a", "t", 1.0, 1.0, 0.4)?;
    graph.add_edge("b", "t", 1.0, 1.0, 0.4)?;
    if (graph.max_flow("s", "t")?
        - flow["max_flow"]
            .as_f64()
            .ok_or_else(|| invalid("invalid max_flow"))?)
    .abs()
        > 1e-12
    {
        return Err(invalid("maximum-flow mismatch").into());
    }

    let persistence = find_vector(&document, "persistence")?;
    let sample = serde_json::json!({"b": 2, "a": [true, "x"]});
    let canonical = canonical_json(&sample)?;
    let round_tripped: Value = serde_json::from_str(&canonical)?;
    let stable = sha256_hex(&sample)? == sha256_hex(&round_tripped)?;
    if stable
        != persistence["digest_stable"]
            .as_bool()
            .ok_or_else(|| invalid("invalid digest_stable"))?
    {
        return Err(invalid("canonical digest round trip mismatch").into());
    }

    let spatial = find_vector(&document, "spatial_delegate")?;
    let center = GeoPoint::new(0.0, 0.0)?;
    let lon = (1000.0 / 6_371_008.8_f64).to_degrees();
    let point = GeoPoint::new(0.0, lon)?;
    let target = spatial["minimum_distance_m"]
        .as_f64()
        .ok_or_else(|| invalid("invalid minimum_distance_m"))?;
    if (haversine_m(center, point) - target).abs() > 1e-5 {
        return Err(invalid("spatial distance fixture mismatch").into());
    }
    println!("PASS graph/graph_golden_vectors.json (8 scenarios)");
    Ok(())
}

fn run() -> Result<(), Box<dyn Error>> {
    let root = root();
    let vector_dir = root.join("data/contracts/golden-vectors/core");
    check_quantity(&vector_dir)?;
    check_contract_result(&vector_dir)?;
    check_graph_vectors(&root)?;
    println!("PASS: expanded Rust conformance checks passed (quantity, contract result, and 8 graph/spatial golden scenarios)");
    Ok(())
}

fn main() {
    if let Err(error) = run() {
        eprintln!("FAIL: {error}");
        std::process::exit(1);
    }
}
