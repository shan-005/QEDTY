# Release readiness

This architecture rebuild is a development baseline, not a production-certification claim. Before release:

1. Generate and commit `uv.lock` with the project's pinned uv version.
2. Run the full multi-platform CI matrix.
3. Expand integration tests against representative space, geospatial, economic and infrastructure datasets.
4. Validate source-specific licenses and parser conformance.
5. Validate model calibration and uncertainty assumptions using held-out data.
6. Remove/keep all repository-security adapters only where they are intentionally scoped.
7. Build and attest the exact release artifacts.
