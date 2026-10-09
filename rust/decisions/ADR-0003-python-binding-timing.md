# ADR-0003: Delay PyO3 and maturin integration

- **Status:** Proposed for review in this bundle
- **Decision:** Do not switch the Python build backend or expose a native extension in the initial workspace/conformance scaffold.
- **Context:** The current Python package uses `setuptools.build_meta`, declares Python `>=3.12,<3.14`, and lists maturin in optional native/development dependencies. A real extension requires a stable Rust API, module naming, wheel matrix, editable-install behavior, packaging policy, and fallback strategy.
- **Consequences:** pure Rust kernels and conformance can mature independently. When binding work starts, create a narrow prototype with PyO3 + maturin in a separate PR/ADR; test Python 3.12/3.13 wheel builds on each supported OS and assess `abi3` versus per-interpreter wheels before deciding the project's backend.
- **Revisit when:** at least one kernel passes its conformance exit criteria and benchmarks establish material benefit from crossing the Python/Rust boundary.
