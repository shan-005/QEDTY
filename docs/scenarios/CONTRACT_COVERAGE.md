# Scenario contract coverage

| Concept | Python | JSON Schema | Protobuf | Arrow | RDF | SHACL | Golden vectors |
|---|---|---|---|---|---|---|---|
| Scenario | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| StatePatch | ✅ | ✅ | ✅ | — | ✅ | ✅ | ✅ |
| Shock | ✅ | ✅ | ✅ | — | ✅ | ✅ | ✅ |
| Intervention | ✅ | ✅ | ✅ | — | ✅ | ✅ | ✅ |
| ScenarioState | ✅ | ✅ | ✅ | — | — | — | ✅ |
| ScenarioRun | ✅ | ✅ | ✅ | — | — | — | ✅ |
| ScenarioGuard | ✅ | ✅ | — | — | — | — | ✅ |
| ScenarioBranch | ✅ | ✅ | — | — | — | — | ✅ |
| ScenarioTree | ✅ | ✅ | — | — | — | — | ✅ |

Contract version: `seraph-scenarios@1.0.0`

### Conformance principles

The same canonical inputs must produce the same semantic state and digest across Python and future Rust implementations. Floating-point tolerance may be introduced only where an algorithm genuinely requires it; identity, ordering, timestamps, enumerations, and contract field meanings are exact.
