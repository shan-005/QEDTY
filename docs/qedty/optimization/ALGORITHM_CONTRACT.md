# Optimization algorithm contract

The reference optimizer is deterministic and budget-feasible. It ranks interventions by counterfactual continuity gain and cost efficiency, then selects a portfolio using an exact 0/1 knapsack solver for small portfolios and a deterministic greedy fallback for larger portfolios.

Robustness utilities expose worst-case floor, lower-tail CVaR, and dominance stability. These scores are decision criteria, not guarantees of future outcomes.

Research/platform anchors:
- Bertsimas, Brown & Caramanis (2011), *Theory and Applications of Robust Optimization*, SIAM Review: https://epubs.siam.org/doi/10.1137/080734510
- Rahimian & Mehrotra (2019), *Distributionally Robust Optimization: A Review*: https://arxiv.org/abs/1908.05659
- Google OR-Tools supports LP/MIP/CP-SAT and routing models: https://developers.google.com/optimization
- HiGHS provides high-performance sparse LP/MIP/QP solvers: https://highs.dev/
- SciPy's MILP interface is a deterministic wrapper around HiGHS: https://docs.scipy.org/doc/scipy/reference/generated/scipy.optimize.milp.html
