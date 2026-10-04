# Changelog

All notable changes to Seraph Guard should be documented here.

The project is currently in beta/pre-release development. Version history should describe user-visible changes and release-level security or compatibility information rather than internal development notes.

## [Unreleased]

### Added

- Public-release documentation and community health files.
- Public contribution, support, security, citation, and code-of-conduct guidance.

### Changed

- Documentation is being aligned with the public Seraph Guard product surface.
- Public claims are explicitly bounded by the evidence available for the corresponding source revision.

### Security

- Public release preparation includes review of repository contents, generated artifacts, secrets, GitHub Actions, and dependency/security configuration.

## [0.3.0.dev0]

### Status

- Beta/pre-release development line.
- Python support: `>=3.12,<3.15`.
- Package name: `seraph-guard`.
- Apache License 2.0.

### Product surface

The current development line includes security scanning and intelligence components covering, as applicable:

- secrets;
- dependencies and SBOM;
- IaC;
- containers;
- code and bounded taint analysis;
- policy;
- repository topology;
- reachability;
- structural impact;
- prioritization;
- explanation;
- suppression;
- adaptive learning;
- fixing;
- CI/CD;
- LSP;
- JSON, SARIF, JUnit, and GitHub-oriented output paths.

### Validation

Seraph Guard uses staged engineering gates covering foundation, correctness, detection/regression, external validation, intelligence/impact, adversarial/differential validation, scale/performance, remediation/developer experience, and integration/enterprise concerns.

Gate results are source-revision-specific and should not be interpreted as universal security claims.

## Release policy

Future release entries should document:

- added functionality;
- changed behavior;
- fixed defects;
- security fixes;
- compatibility changes;
- important validation changes.

Security fixes should be described without unnecessarily exposing exploit details before coordinated disclosure is complete.
