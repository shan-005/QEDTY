# Contract and schema registry

The `contracts/` tree contains versioned, language-neutral contract artifacts and
interoperability profiles used by QEDTY. The Python semantic/reference implementation owns
current domain meaning; schemas and transport representations must preserve that meaning.

## Contract surfaces

- **JSON Schema** defines structural validation for supported document boundaries.
- **Protobuf** defines typed service and control-plane messages.
- **Arrow** defines selected columnar interchange representations.
- **RDF / OWL / JSON-LD** provide semantic-web representations and mappings.
- **SHACL** provides bounded validation for supported RDF graph profiles.
- **Golden vectors** define deterministic expected behavior for shared implementations.

The presence of a mapping does not establish complete conformance to every feature of an
external standard. Each contract and profile defines its supported scope and limitations.

## Domain contracts

- [Evidence contracts](evidence/README.md)
- [Temporal contracts](temporal/README.md)
- [Protobuf boundary](protobuf/README.md)
- [Contract coverage](CONTRACT_COVERAGE.md)

## Change policy

A semantic contract change requires review of affected schemas, implementations, fixtures,
conformance tests, compatibility/versioning policy, and documentation. Golden-vector
changes are contract changes, not routine test maintenance. Preserve backward compatibility
or document an explicit migration path.
