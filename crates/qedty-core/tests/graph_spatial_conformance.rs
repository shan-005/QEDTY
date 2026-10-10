use qedty_core::graph::DirectedGraph;
use qedty_core::spatial::{haversine_m, GeoPoint};
use serde_json::Value;

const GOLDEN_VECTORS: &str = include_str!("../../../tests/graph_golden_vectors.json");

fn fixture() -> Value {
    serde_json::from_str(GOLDEN_VECTORS)
        .expect("shared Python/Rust golden-vector fixture must parse")
}

fn vector<'a>(root: &'a Value, name: &str) -> &'a Value {
    root["vectors"]
        .as_array()
        .expect("fixture vectors must be an array")
        .iter()
        .find(|item| item["name"].as_str() == Some(name))
        .unwrap_or_else(|| panic!("missing golden vector: {name}"))
}

fn labels<'a>(item: &'a Value, field: &str) -> Vec<&'a str> {
    item[field]
        .as_array()
        .unwrap_or_else(|| panic!("missing array field: {field}"))
        .iter()
        .map(|value| value.as_str().expect("labels must be strings"))
        .collect()
}

fn reference_graph() -> DirectedGraph {
    let mut graph = DirectedGraph::new();
    graph.add_edge("a", "b", 1.0, 0.9, 0.4).unwrap();
    graph.add_edge("b", "c", 2.0, 0.9, 0.4).unwrap();
    graph.add_edge("a", "c", 5.0, 0.5, 0.0).unwrap();
    graph
}

#[test]
fn temporal_chain_vector_checks_traversal_and_graph_counts() {
    let root = fixture();
    let expected = vector(&root, "temporal_chain");
    let mut graph = DirectedGraph::new();

    graph.add_edge("a", "b", 1.0, 1.0, 1.0).unwrap();
    graph.add_edge("b", "c", 1.0, 1.0, 1.0).unwrap();

    assert_eq!(
        graph.breadth_first("a").unwrap(),
        labels(expected, "bfs_labels")
            .into_iter()
            .map(str::to_owned)
            .collect::<Vec<_>>()
    );
    assert_eq!(
        graph.edge_count() as u64,
        expected["active_relationships"].as_u64().unwrap()
    );
    assert_eq!(
        graph.node_count() as u64,
        expected["snapshot_entities"].as_u64().unwrap()
    );
}

#[test]
fn weighted_shortest_path_matches_shared_expected_labels_and_cost() {
    let root = fixture();
    let expected = vector(&root, "weighted_shortest_path");
    let graph = reference_graph();
    let result = graph.shortest_path("a", "c").unwrap().unwrap();

    assert_eq!(
        result.nodes.iter().map(String::as_str).collect::<Vec<_>>(),
        labels(expected, "shortest_path_labels")
    );
    let expected_cost = expected["shortest_path_cost"].as_f64().unwrap();
    assert!((result.score - expected_cost).abs() < 1e-12);
}

#[test]
fn reliability_preference_matches_shared_expected_path_and_score() {
    let root = fixture();
    let expected = vector(&root, "reliability_preference");
    let graph = reference_graph();
    let result = graph.most_reliable_path("a", "c").unwrap().unwrap();

    assert_eq!(
        result.nodes.iter().map(String::as_str).collect::<Vec<_>>(),
        labels(expected, "best_path_labels")
    );
    let expected_score = expected["best_path_score"].as_f64().unwrap();
    assert!((result.score - expected_score).abs() < 1e-12);
}

#[test]
fn connectivity_and_pagerank_match_shared_invariants() {
    let root = fixture();
    let connectivity = vector(&root, "connectivity");
    let centrality = vector(&root, "centrality");
    let graph = reference_graph();

    assert_eq!(
        graph.strongly_connected_components().len() as u64,
        connectivity["strong_component_count"].as_u64().unwrap()
    );
    assert_eq!(
        graph.weak_components().len() as u64,
        connectivity["weak_component_count"].as_u64().unwrap()
    );

    let scores = graph.pagerank(100, 0.85).unwrap();
    let sum: f64 = scores.values().sum();
    let expected_sum = centrality["pagerank_sum"].as_f64().unwrap();
    assert!((sum - expected_sum).abs() < 1e-12);
}

#[test]
fn max_flow_matches_shared_expected_value() {
    let root = fixture();
    let expected = vector(&root, "max_flow");
    let mut graph = DirectedGraph::new();

    graph.add_edge("s", "a", 1.0, 1.0, 0.4).unwrap();
    graph.add_edge("s", "b", 1.0, 1.0, 0.4).unwrap();
    graph.add_edge("a", "merge", 1.0, 1.0, 0.4).unwrap();
    graph.add_edge("b", "merge", 1.0, 1.0, 0.4).unwrap();
    graph.add_edge("merge", "t", 1.0, 1.0, 0.8).unwrap();

    let actual = graph.max_flow("s", "t").unwrap();
    let expected_flow = expected["max_flow"].as_f64().unwrap();
    assert!((actual - expected_flow).abs() < 1e-12);
}

#[test]
fn persistence_vector_checks_canonical_json_and_digest_stability() {
    let root = fixture();
    let expected = vector(&root, "persistence");
    assert!(expected["digest_stable"].as_bool().unwrap());

    let original = serde_json::json!({
        "z": 1,
        "metadata": {"version": 1, "label": "QEDTY"},
        "a": ["node-1", "node-2"]
    });

    let canonical = qedty_core::canonical_json(&original).unwrap();
    let parsed: Value = serde_json::from_str(&canonical).unwrap();
    let canonical_again = qedty_core::canonical_json(&parsed).unwrap();

    assert_eq!(canonical, canonical_again);
    assert_eq!(
        qedty_core::sha256_hex(&original).unwrap(),
        qedty_core::sha256_hex(&parsed).unwrap()
    );
}

#[test]
fn spatial_distance_matches_shared_expected_value() {
    let root = fixture();
    let expected = vector(&root, "spatial_delegate");
    let expected_distance = expected["minimum_distance_m"].as_f64().unwrap();

    let origin = GeoPoint::new(0.0, 0.0).unwrap();
    let longitude_deg = (expected_distance / 6_371_008.8_f64).to_degrees();
    let destination = GeoPoint::new(0.0, longitude_deg).unwrap();
    let actual_distance = haversine_m(origin, destination);

    assert!(
        (actual_distance - expected_distance).abs() < 1e-8,
        "expected {expected_distance} m, got {actual_distance} m"
    );
}
