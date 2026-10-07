# Intelligence algorithm contract

SERAPH intelligence is an **evidence-bounded** layer. It may score, rank, detect, forecast, fuse, or explain inputs, but must not change their epistemic status merely because a model produced a number.

Deterministic primitives include robust median/MAD anomaly scores, EWMA and two-sided CUSUM, damped Holt-style forecasting with MAD uncertainty, evidence-weighted fusion with an explicit conflict penalty, graph dependency concentration, and structured explanations.

The implementation intentionally avoids silently claiming that a black-box model is installed or trained. Heavy implementations such as Extended Isolation Forest, Temporal GNNs, probabilistic forecasting, or vector databases can be plugged in later behind these contracts. This keeps the Python reference layer reproducible.

Research anchors:
- Bouman, Bukhsh & Heskes (2024), *Unsupervised Anomaly Detection Algorithms on Real-world Data*, JMLR: https://www.jmlr.org/papers/v25/23-0570.html
- Rossi et al. (2020), *Temporal Graph Networks for Deep Learning on Dynamic Graphs*: https://arxiv.org/abs/2006.10637
- Li, Kang & Li (2021), Bayesian forecast combination: https://arxiv.org/abs/2108.02082
- GluonTS provides a reference platform for probabilistic time-series forecasting and anomaly detection: https://www.jmlr.org/papers/v21/19-820.html
