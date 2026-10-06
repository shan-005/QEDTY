# Migration from the legacy tree

Removed from the canonical architecture:

- `src/seraph/guard/`
- `src/seraph/sources/repository/scanners/`
- scanner-native `Finding`, `Scanner`, `ScanContext`, `UFIC`, suppression-first scheduler semantics
- security-only SARIF/JUnit output as the platform's primary output model

Repository security functionality is retained only as an adapter under `src/seraph/sources/repository_security/`.
