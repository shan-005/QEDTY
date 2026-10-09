# ADR-0001: Python remains semantic authority

- **Status:** Accepted for Rust architecture
- **Decision:** Python remains the QEDTY reference/semantic implementation. Rust is a conformant deterministic compute implementation, not a second authority.
- **Context:** QEDTY's domain behavior is expressed across Python models, contracts, and shared golden vectors. A Rust implementation can easily diverge on identity, intervals, units, spatial boundaries, epistemic states or deterministic ordering if those behaviors are copied from memory.
- **Consequences:** every migrated kernel identifies its Python reference and vectors; contract behavior must be explicitly reviewed before changing expected outputs; performance does not waive conformance.
- **Revisit when:** a formal language-neutral normative specification replaces Python as the semantic authority, with migration/version policy and cross-language governance approved.
