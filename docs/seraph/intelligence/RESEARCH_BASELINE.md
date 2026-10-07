# Intelligence research baseline

The selected architecture draws from robust statistics, anomaly detection, dynamic graph learning, forecast combination, and provenance-aware explanation. The repository implementation uses lightweight deterministic equivalents rather than importing heavyweight ML stacks into the semantic reference core.

The 2024 JMLR comparison of 33 unsupervised anomaly detectors over 52 real-world datasets found method performance varies by anomaly regime and that Extended Isolation Forest and kNN were strong choices in different regimes. SERAPH therefore exposes explicit method labels and does not treat a single anomaly detector as universally optimal.

Temporal Graph Networks demonstrate that dynamic graphs benefit from time-aware representations; SERAPH keeps the graph API deterministic and treats learned temporal models as optional accelerators.

Forecast combination research motivates ensemble-friendly interfaces and explicit interval semantics. No forecast is represented as an observed fact.
