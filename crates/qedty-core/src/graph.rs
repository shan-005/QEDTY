//! Deterministic directed-graph primitives for small/medium in-memory kernels.
//!
//! Labels and adjacency are kept in ordered collections so path ties and outputs
//! do not depend on hash-map iteration order. This module is intentionally a
//! basic semantic graph; it is not a replacement for the Python world-graph API
//! or a benchmarked large-graph engine.

use std::collections::{BTreeMap, BTreeSet, VecDeque};
use thiserror::Error;

#[derive(Debug, Clone, Error, PartialEq, Eq)]
pub enum GraphError {
    #[error("node label must not be blank")]
    BlankNode,
    #[error(
        "edge cost and capacity must be finite and non-negative; reliability must be in [0, 1]"
    )]
    InvalidEdgeWeight,
    #[error("start node does not exist: {0}")]
    UnknownNode(String),
    #[error("graph algorithm parameters are invalid")]
    InvalidParameter,
    #[error("PageRank did not converge within the iteration limit")]
    PageRankDidNotConverge,
}

#[derive(Debug, Clone, PartialEq)]
pub struct Edge {
    pub from: String,
    pub to: String,
    pub cost: f64,
    pub reliability: f64,
    pub capacity: f64,
}

#[derive(Debug, Clone, PartialEq)]
pub struct PathResult {
    pub nodes: Vec<String>,
    pub score: f64,
}

#[derive(Debug, Clone, Default, PartialEq)]
pub struct DirectedGraph {
    nodes: BTreeSet<String>,
    edges: Vec<Edge>,
}

impl DirectedGraph {
    pub fn new() -> Self {
        Self::default()
    }

    pub fn add_node(&mut self, label: &str) -> Result<(), GraphError> {
        let label = label.trim();
        if label.is_empty() {
            return Err(GraphError::BlankNode);
        }
        self.nodes.insert(label.to_owned());
        Ok(())
    }

    pub fn add_edge(
        &mut self,
        from: &str,
        to: &str,
        cost: f64,
        reliability: f64,
        capacity: f64,
    ) -> Result<(), GraphError> {
        let from = from.trim();
        let to = to.trim();
        if from.is_empty() || to.is_empty() {
            return Err(GraphError::BlankNode);
        }
        if !cost.is_finite()
            || cost < 0.0
            || !capacity.is_finite()
            || capacity < 0.0
            || !reliability.is_finite()
            || !(0.0..=1.0).contains(&reliability)
        {
            return Err(GraphError::InvalidEdgeWeight);
        }
        self.nodes.insert(from.to_owned());
        self.nodes.insert(to.to_owned());
        let edge = Edge {
            from: from.to_owned(),
            to: to.to_owned(),
            cost,
            reliability,
            capacity,
        };
        let compare_edges = |a: &Edge, b: &Edge| {
            a.from
                .cmp(&b.from)
                .then_with(|| a.to.cmp(&b.to))
                .then_with(|| a.cost.total_cmp(&b.cost))
                .then_with(|| a.reliability.total_cmp(&b.reliability))
                .then_with(|| a.capacity.total_cmp(&b.capacity))
        };
        if self.edges.last().map_or(true, |last| {
            compare_edges(last, &edge) != std::cmp::Ordering::Greater
        }) {
            self.edges.push(edge);
        } else {
            let insertion = self.edges.partition_point(|existing| {
                compare_edges(existing, &edge) != std::cmp::Ordering::Greater
            });
            self.edges.insert(insertion, edge);
        }
        Ok(())
    }

    pub fn nodes(&self) -> impl Iterator<Item = &str> {
        self.nodes.iter().map(String::as_str)
    }
    pub fn edges(&self) -> &[Edge] {
        &self.edges
    }
    pub fn node_count(&self) -> usize {
        self.nodes.len()
    }
    pub fn edge_count(&self) -> usize {
        self.edges.len()
    }

    fn require_node(&self, label: &str) -> Result<(), GraphError> {
        let label = label.trim();
        if self.nodes.contains(label) {
            Ok(())
        } else {
            Err(GraphError::UnknownNode(label.to_owned()))
        }
    }

    fn outgoing(&self, label: &str) -> Vec<&Edge> {
        let start = self
            .edges
            .partition_point(|edge| edge.from.as_str() < label);
        let end = self
            .edges
            .partition_point(|edge| edge.from.as_str() <= label);
        self.edges[start..end].iter().collect()
    }

    /// Breadth-first reachable labels, excluding the start node, in visit order.
    pub fn breadth_first(&self, start: &str) -> Result<Vec<String>, GraphError> {
        let start = start.trim();
        self.require_node(start)?;
        let mut queue = VecDeque::from([start.to_owned()]);
        let mut visited = BTreeSet::from([start.to_owned()]);
        let mut result = Vec::new();
        while let Some(current) = queue.pop_front() {
            for edge in self.outgoing(&current) {
                if visited.insert(edge.to.clone()) {
                    result.push(edge.to.clone());
                    queue.push_back(edge.to.clone());
                }
            }
        }
        Ok(result)
    }

    /// Minimum additive-cost path. Equal-cost alternatives are resolved by stable
    /// label/edge ordering. Returns `None` when the destination is unreachable.
    pub fn shortest_path(&self, start: &str, goal: &str) -> Result<Option<PathResult>, GraphError> {
        let start = start.trim();
        let goal = goal.trim();
        self.require_node(start)?;
        self.require_node(goal)?;
        let mut distance: BTreeMap<String, f64> = self
            .nodes
            .iter()
            .map(|node| (node.clone(), f64::INFINITY))
            .collect();
        let mut previous: BTreeMap<String, String> = BTreeMap::new();
        let mut remaining = self.nodes.clone();
        distance.insert(start.to_owned(), 0.0);
        while !remaining.is_empty() {
            let current = remaining
                .iter()
                .filter_map(|node| {
                    let d = *distance.get(node)?;
                    d.is_finite().then_some((node.clone(), d))
                })
                .min_by(|(label_a, da), (label_b, db)| {
                    da.total_cmp(db).then_with(|| label_a.cmp(label_b))
                });
            let Some((current, current_distance)) = current else {
                break;
            };
            remaining.remove(&current);
            if current == goal {
                break;
            }
            for edge in self.outgoing(&current) {
                if !remaining.contains(&edge.to) {
                    continue;
                }
                let candidate = current_distance + edge.cost;
                // Both edge weights can be finite while their sum overflows.
                // Ignore this unrepresentable path and continue searching for
                // another finite-cost route to the destination.
                if !candidate.is_finite() {
                    continue;
                }
                let old = *distance.get(&edge.to).unwrap_or(&f64::INFINITY);
                let lexicographically_better = previous
                    .get(&edge.to)
                    .map_or(true, |old_parent| current < *old_parent);
                if candidate < old || (candidate == old && lexicographically_better) {
                    distance.insert(edge.to.clone(), candidate);
                    previous.insert(edge.to.clone(), current.clone());
                }
            }
        }
        let score = *distance.get(goal).unwrap_or(&f64::INFINITY);
        if !score.is_finite() {
            return Ok(None);
        }
        let mut path = vec![goal.to_owned()];
        let mut current = goal.to_owned();
        while current != start {
            current = previous
                .get(&current)
                .ok_or(GraphError::InvalidParameter)?
                .clone();
            path.push(current.clone());
        }
        path.reverse();
        Ok(Some(PathResult { nodes: path, score }))
    }

    /// Maximum-product reliability path. Reliability scores are constrained to [0, 1].
    pub fn most_reliable_path(
        &self,
        start: &str,
        goal: &str,
    ) -> Result<Option<PathResult>, GraphError> {
        let start = start.trim();
        let goal = goal.trim();
        self.require_node(start)?;
        self.require_node(goal)?;
        let mut score: BTreeMap<String, f64> =
            self.nodes.iter().map(|node| (node.clone(), 0.0)).collect();
        let mut reachable = BTreeSet::from([start.to_owned()]);
        let mut previous: BTreeMap<String, String> = BTreeMap::new();
        let mut remaining = self.nodes.clone();
        score.insert(start.to_owned(), 1.0);
        while !remaining.is_empty() {
            let current = remaining
                .iter()
                .filter(|node| reachable.contains(*node))
                .min_by(|a, b| score[*b].total_cmp(&score[*a]).then_with(|| a.cmp(b)))
                .cloned();
            let Some(current) = current else {
                break;
            };
            remaining.remove(&current);
            if current == goal {
                break;
            }
            for edge in self.outgoing(&current) {
                if !remaining.contains(&edge.to) {
                    continue;
                }
                let candidate = score[&current] * edge.reliability;
                if !reachable.contains(&edge.to) || candidate > score[&edge.to] {
                    score.insert(edge.to.clone(), candidate);
                    reachable.insert(edge.to.clone());
                    previous.insert(edge.to.clone(), current.clone());
                }
            }
        }
        if !reachable.contains(goal) {
            return Ok(None);
        }
        let mut path = vec![goal.to_owned()];
        let mut current = goal.to_owned();
        while current != start {
            current = previous
                .get(&current)
                .ok_or(GraphError::InvalidParameter)?
                .clone();
            path.push(current.clone());
        }
        path.reverse();
        Ok(Some(PathResult {
            nodes: path,
            score: score[goal],
        }))
    }

    pub fn weak_components(&self) -> Vec<Vec<String>> {
        let mut undirected: BTreeMap<String, BTreeSet<String>> = self
            .nodes
            .iter()
            .map(|node| (node.clone(), BTreeSet::new()))
            .collect();
        for edge in &self.edges {
            undirected
                .entry(edge.from.clone())
                .or_default()
                .insert(edge.to.clone());
            undirected
                .entry(edge.to.clone())
                .or_default()
                .insert(edge.from.clone());
        }
        let mut visited = BTreeSet::new();
        let mut components = Vec::new();
        for start in &self.nodes {
            if visited.contains(start) {
                continue;
            }
            let mut queue = VecDeque::from([start.clone()]);
            visited.insert(start.clone());
            let mut component = Vec::new();
            while let Some(node) = queue.pop_front() {
                component.push(node.clone());
                for next in undirected.get(&node).into_iter().flatten() {
                    if visited.insert(next.clone()) {
                        queue.push_back(next.clone());
                    }
                }
            }
            component.sort();
            components.push(component);
        }
        components.sort();
        components
    }

    pub fn strongly_connected_components(&self) -> Vec<Vec<String>> {
        let mut adjacency: BTreeMap<String, Vec<String>> = self
            .nodes
            .iter()
            .cloned()
            .map(|node| (node, Vec::new()))
            .collect();
        let mut reverse = adjacency.clone();

        for edge in &self.edges {
            adjacency
                .get_mut(&edge.from)
                .expect("edge source must be a graph node")
                .push(edge.to.clone());
            reverse
                .get_mut(&edge.to)
                .expect("edge target must be a graph node")
                .push(edge.from.clone());
        }

        for neighbors in adjacency.values_mut() {
            neighbors.sort();
            neighbors.dedup();
        }
        for neighbors in reverse.values_mut() {
            neighbors.sort();
            neighbors.dedup();
        }

        // First pass: iterative DFS finishing order.
        let mut visited = BTreeSet::new();
        let mut order = Vec::with_capacity(self.nodes.len());

        for start in &self.nodes {
            if !visited.insert(start.clone()) {
                continue;
            }

            let mut stack = vec![(start.clone(), 0_usize)];
            while !stack.is_empty() {
                let next = {
                    let (node, next_index) = stack.last_mut().expect("DFS stack is non-empty");
                    let neighbors = adjacency
                        .get(node)
                        .expect("every node has an adjacency list");

                    if *next_index < neighbors.len() {
                        let next = neighbors[*next_index].clone();
                        *next_index += 1;
                        Some(next)
                    } else {
                        None
                    }
                };

                if let Some(next) = next {
                    if visited.insert(next.clone()) {
                        stack.push((next, 0));
                    }
                } else {
                    let (finished, _) = stack.pop().expect("DFS stack is non-empty");
                    order.push(finished);
                }
            }
        }

        // Second pass: traverse the reverse graph iteratively.
        visited.clear();
        let mut components = Vec::new();

        for start in order.iter().rev() {
            if !visited.insert(start.clone()) {
                continue;
            }

            let mut component = Vec::new();
            let mut stack = vec![start.clone()];

            while let Some(node) = stack.pop() {
                component.push(node.clone());

                if let Some(neighbors) = reverse.get(&node) {
                    for next in neighbors.iter().rev() {
                        if visited.insert(next.clone()) {
                            stack.push(next.clone());
                        }
                    }
                }
            }

            component.sort();
            components.push(component);
        }

        components.sort();
        components
    }

    /// PageRank with deterministic iteration order and uniform redistribution of dangling mass.
    pub fn pagerank(
        &self,
        iterations: usize,
        damping: f64,
    ) -> Result<BTreeMap<String, f64>, GraphError> {
        if iterations == 0
            || !damping.is_finite()
            || damping <= 0.0
            || damping >= 1.0
            || self.nodes.is_empty()
        {
            return Err(GraphError::InvalidParameter);
        }
        let n = self.nodes.len() as f64;
        let mut scores: BTreeMap<String, f64> = self
            .nodes
            .iter()
            .map(|node| (node.clone(), 1.0 / n))
            .collect();
        let outgoing_counts: BTreeMap<String, usize> = self
            .nodes
            .iter()
            .map(|node| (node.clone(), self.outgoing(node).len()))
            .collect();
        for _ in 0..iterations {
            let dangling: f64 = self
                .nodes
                .iter()
                .filter(|node| outgoing_counts[*node] == 0)
                .map(|node| scores[node])
                .sum();
            let base = (1.0 - damping) / n + damping * dangling / n;
            let mut next: BTreeMap<String, f64> =
                self.nodes.iter().map(|node| (node.clone(), base)).collect();
            for edge in &self.edges {
                let count = outgoing_counts[&edge.from];
                if count > 0 {
                    *next
                        .get_mut(&edge.to)
                        .expect("all edge endpoints are nodes") +=
                        damping * scores[&edge.from] / count as f64;
                }
            }
            scores = next;
        }
        let sum: f64 = scores.values().sum();
        if !sum.is_finite() || sum <= 0.0 {
            return Err(GraphError::InvalidParameter);
        }
        for value in scores.values_mut() {
            *value /= sum;
        }
        Ok(scores)
    }

    /// PageRank that stops when the L1 score delta reaches `tolerance`.
    ///
    /// `max_iterations` is a strict upper bound. Failure to converge is
    /// reported rather than silently returning the last iterate.
    pub fn pagerank_until_converged(
        &self,
        max_iterations: usize,
        damping: f64,
        tolerance: f64,
    ) -> Result<BTreeMap<String, f64>, GraphError> {
        if max_iterations == 0
            || !damping.is_finite()
            || damping <= 0.0
            || damping >= 1.0
            || !tolerance.is_finite()
            || tolerance <= 0.0
        {
            return Err(GraphError::InvalidParameter);
        }

        if self.nodes.is_empty() {
            return Ok(BTreeMap::new());
        }

        let n = self.nodes.len() as f64;
        let mut scores: BTreeMap<String, f64> = self
            .nodes
            .iter()
            .map(|node| (node.clone(), 1.0 / n))
            .collect();

        let outgoing_counts: BTreeMap<String, usize> = self
            .nodes
            .iter()
            .map(|node| (node.clone(), self.outgoing(node).len()))
            .collect();

        for _ in 0..max_iterations {
            let dangling_mass: f64 = self
                .nodes
                .iter()
                .filter(|node| outgoing_counts[*node] == 0)
                .map(|node| scores[node])
                .sum();

            let base = (1.0 - damping + damping * dangling_mass) / n;
            let mut next: BTreeMap<String, f64> =
                self.nodes.iter().map(|node| (node.clone(), base)).collect();

            for edge in &self.edges {
                let count = outgoing_counts[&edge.from];
                if count > 0 {
                    *next
                        .get_mut(&edge.to)
                        .expect("every edge endpoint is a graph node") +=
                        damping * scores[&edge.from] / count as f64;
                }
            }

            let delta: f64 = self
                .nodes
                .iter()
                .map(|node| (next[node] - scores[node]).abs())
                .sum();

            scores = next;

            if delta <= tolerance {
                let total: f64 = scores.values().sum();
                if !total.is_finite() || total <= 0.0 {
                    return Err(GraphError::InvalidParameter);
                }

                for score in scores.values_mut() {
                    *score /= total;
                }
                return Ok(scores);
            }
        }

        Err(GraphError::PageRankDidNotConverge)
    }

    /// Edmonds-Karp max flow over non-negative edge capacities.
    pub fn max_flow(&self, source: &str, sink: &str) -> Result<f64, GraphError> {
        let source = source.trim();
        let sink = sink.trim();
        self.require_node(source)?;
        self.require_node(sink)?;
        if source == sink {
            return Err(GraphError::InvalidParameter);
        }
        let mut residual: BTreeMap<(String, String), f64> = BTreeMap::new();
        let mut adjacency: BTreeMap<String, BTreeSet<String>> = self
            .nodes
            .iter()
            .map(|node| (node.clone(), BTreeSet::new()))
            .collect();
        for edge in &self.edges {
            let forward = residual
                .entry((edge.from.clone(), edge.to.clone()))
                .or_default();
            *forward += edge.capacity;
            if !forward.is_finite() {
                return Err(GraphError::InvalidEdgeWeight);
            }
            adjacency
                .entry(edge.from.clone())
                .or_default()
                .insert(edge.to.clone());
            adjacency
                .entry(edge.to.clone())
                .or_default()
                .insert(edge.from.clone());
            residual
                .entry((edge.to.clone(), edge.from.clone()))
                .or_insert(0.0);
        }
        let mut total = 0.0;
        loop {
            let mut parent: BTreeMap<String, String> = BTreeMap::new();
            let mut queue = VecDeque::from([source.to_owned()]);
            let mut visited = BTreeSet::from([source.to_owned()]);
            while let Some(node) = queue.pop_front() {
                for next in adjacency.get(&node).into_iter().flatten() {
                    if visited.contains(next)
                        || residual
                            .get(&(node.clone(), next.clone()))
                            .copied()
                            .unwrap_or(0.0)
                            <= 0.0
                    {
                        continue;
                    }
                    visited.insert(next.clone());
                    parent.insert(next.clone(), node.clone());
                    if next == sink {
                        break;
                    }
                    queue.push_back(next.clone());
                }
                if visited.contains(sink) {
                    break;
                }
            }
            if !visited.contains(sink) {
                break;
            }
            let mut increment = f64::INFINITY;
            let mut current = sink.to_owned();
            while current != source {
                let previous = parent
                    .get(&current)
                    .ok_or(GraphError::InvalidParameter)?
                    .clone();
                increment = increment.min(residual[&(previous.clone(), current.clone())]);
                current = previous;
            }
            if !increment.is_finite() || increment <= 0.0 {
                break;
            }
            current = sink.to_owned();
            while current != source {
                let previous = parent
                    .get(&current)
                    .ok_or(GraphError::InvalidParameter)?
                    .clone();
                *residual
                    .entry((previous.clone(), current.clone()))
                    .or_default() -= increment;
                *residual
                    .entry((current.clone(), previous.clone()))
                    .or_default() += increment;
                current = previous;
            }
            total += increment;
            if !total.is_finite() {
                return Err(GraphError::InvalidEdgeWeight);
            }
        }
        Ok(total)
    }
}

#[cfg(test)]
mod tests {
    use super::{DirectedGraph, GraphError};

    fn chain() -> DirectedGraph {
        let mut graph = DirectedGraph::new();
        graph.add_edge("a", "b", 1.0, 0.9, 0.4).unwrap();
        graph.add_edge("b", "c", 2.0, 0.9, 0.4).unwrap();
        graph.add_edge("a", "c", 10.0, 0.3, 0.0).unwrap();
        graph.add_node("isolated").unwrap();
        graph
    }

    #[test]
    fn traversal_and_shortest_path_are_deterministic() {
        let graph = chain();
        assert_eq!(
            graph.breadth_first("a").unwrap(),
            vec!["b".to_owned(), "c".to_owned()]
        );
        let path = graph.shortest_path("a", "c").unwrap().unwrap();
        assert_eq!(
            path.nodes,
            vec!["a".to_owned(), "b".to_owned(), "c".to_owned()]
        );
        assert_eq!(path.score, 3.0);
    }

    #[test]
    fn shortest_path_ignores_overflowing_alternative_when_finite_path_exists() {
        let mut graph = DirectedGraph::new();

        graph.add_edge("s", "a", 9.0e307, 1.0, 1.0).unwrap();
        graph.add_edge("a", "b", 9.0e307, 1.0, 1.0).unwrap();
        graph.add_edge("s", "goal", 1.5e308, 1.0, 1.0).unwrap();

        let result = graph.shortest_path("s", "goal").unwrap().unwrap();
        assert_eq!(result.nodes, vec!["s", "goal"]);
        assert_eq!(result.score, 1.5e308);
    }

    #[test]
    fn reliable_path_optimizes_product_not_additive_cost() {
        let path = chain().most_reliable_path("a", "c").unwrap().unwrap();
        assert_eq!(
            path.nodes,
            vec!["a".to_owned(), "b".to_owned(), "c".to_owned()]
        );
        assert!((path.score - 0.81).abs() < 1e-12);
    }

    #[test]
    fn strongly_connected_components_handles_deep_graph_iteratively() {
        const NODE_COUNT: usize = 10_000;
        let mut graph = DirectedGraph::new();

        for index in 0..(NODE_COUNT - 1) {
            let from = format!("node-{index:05}");
            let to = format!("node-{:05}", index + 1);
            graph.add_edge(&from, &to, 1.0, 1.0, 1.0).unwrap();
        }

        let components = graph.strongly_connected_components();
        assert_eq!(components.len(), NODE_COUNT);
        assert_eq!(components.first().unwrap(), &vec!["node-00000".to_owned()]);
        assert_eq!(components.last().unwrap(), &vec!["node-09999".to_owned()]);
    }

    #[test]
    fn connectivity_and_pagerank_obey_deterministic_invariants() {
        let graph = chain();
        assert_eq!(
            graph.weak_components(),
            vec![
                vec!["a".to_owned(), "b".to_owned(), "c".to_owned()],
                vec!["isolated".to_owned()]
            ]
        );
        assert_eq!(graph.strongly_connected_components().len(), 4);
        let scores = graph.pagerank(100, 0.85).unwrap();
        let sum: f64 = scores.values().sum();
        assert!((sum - 1.0).abs() < 1e-12);
        assert!(scores
            .values()
            .all(|score| *score >= 0.0 && score.is_finite()));
    }

    #[test]
    fn edge_insertion_order_does_not_change_canonical_graph_state_or_results() {
        let edges = [
            ("a", "c", 4.0, 0.4, 1.0),
            ("a", "b", 1.0, 0.9, 2.0),
            ("b", "c", 2.0, 0.9, 2.0),
            ("a", "b", 1.0, 0.8, 3.0),
        ];
        let mut first = DirectedGraph::new();
        for (from, to, cost, reliability, capacity) in edges {
            first
                .add_edge(from, to, cost, reliability, capacity)
                .unwrap();
        }
        let mut second = DirectedGraph::new();
        for (from, to, cost, reliability, capacity) in edges.into_iter().rev() {
            second
                .add_edge(from, to, cost, reliability, capacity)
                .unwrap();
        }
        assert_eq!(first, second);
        assert_eq!(
            first.shortest_path("a", "c").unwrap(),
            second.shortest_path("a", "c").unwrap()
        );
        assert_eq!(
            first.most_reliable_path("a", "c").unwrap(),
            second.most_reliable_path("a", "c").unwrap()
        );
    }

    #[test]
    fn pagerank_converges_and_validates_parameters() {
        let graph = chain();

        let scores = graph.pagerank_until_converged(200, 0.85, 1e-10).unwrap();

        assert_eq!(scores.len(), graph.node_count());
        let total: f64 = scores.values().sum();
        assert!((total - 1.0).abs() < 1e-12);

        assert!(matches!(
            graph.pagerank(5, 0.0),
            Err(GraphError::InvalidParameter)
        ));
        assert!(matches!(
            graph.pagerank_until_converged(20, 0.0, 1e-10),
            Err(GraphError::InvalidParameter)
        ));
        assert!(matches!(
            graph.pagerank_until_converged(20, 0.85, 0.0),
            Err(GraphError::InvalidParameter)
        ));
        assert!(matches!(
            graph.pagerank_until_converged(1, 0.85, 1e-30),
            Err(GraphError::PageRankDidNotConverge)
        ));
        assert!(DirectedGraph::new()
            .pagerank_until_converged(20, 0.85, 1e-10)
            .unwrap()
            .is_empty());
    }

    #[test]
    fn max_flow_handles_antiparallel_edges() {
        let mut graph = DirectedGraph::new();

        graph.add_edge("s", "a", 0.0, 1.0, 3.0).unwrap();
        graph.add_edge("a", "s", 0.0, 1.0, 2.0).unwrap();
        graph.add_edge("a", "t", 0.0, 1.0, 2.0).unwrap();
        graph.add_edge("s", "t", 0.0, 1.0, 1.0).unwrap();

        // One unit flows directly and two flow through a.
        assert_eq!(graph.max_flow("s", "t").unwrap(), 3.0);
    }

    #[test]
    fn max_flow_reroutes_an_earlier_augmentation() {
        let mut graph = DirectedGraph::new();

        graph.add_edge("s", "a", 0.0, 1.0, 1.0).unwrap();
        graph.add_edge("s", "b", 0.0, 1.0, 1.0).unwrap();
        graph.add_edge("a", "x", 0.0, 1.0, 1.0).unwrap();
        graph.add_edge("a", "y", 0.0, 1.0, 1.0).unwrap();
        graph.add_edge("b", "x", 0.0, 1.0, 1.0).unwrap();
        graph.add_edge("x", "t", 0.0, 1.0, 1.0).unwrap();
        graph.add_edge("y", "t", 0.0, 1.0, 1.0).unwrap();

        // The second augmentation must use a reverse residual edge to
        // reroute the first path and achieve the maximum flow of two.
        assert_eq!(graph.max_flow("s", "t").unwrap(), 2.0);
    }

    #[test]
    fn maximum_flow_handles_parallel_channels_and_shared_sink() {
        let mut graph = DirectedGraph::new();
        graph.add_edge("s", "a", 1.0, 1.0, 0.4).unwrap();
        graph.add_edge("s", "b", 1.0, 1.0, 0.4).unwrap();
        graph.add_edge("a", "t", 1.0, 1.0, 0.4).unwrap();
        graph.add_edge("b", "t", 1.0, 1.0, 0.4).unwrap();
        assert!((graph.max_flow("s", "t").unwrap() - 0.8).abs() < 1e-12);
    }

    #[test]
    fn rejects_bad_edge_metrics_and_unknown_start() {
        let mut graph = DirectedGraph::new();
        assert!(graph.add_edge("a", "b", -1.0, 0.5, 1.0).is_err());
        assert!(graph.breadth_first("missing").is_err());
    }
}
