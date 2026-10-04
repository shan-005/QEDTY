# Security Policy

## Reporting a vulnerability

Seraph Guard is a security-sensitive project. Please do **not** report an undisclosed security vulnerability through a public GitHub issue, pull request, discussion, or other public channel.

For a public GitHub repository, maintainers should enable GitHub's **private vulnerability reporting** feature. When that feature is enabled, use the repository's **Report a vulnerability** mechanism.

If private vulnerability reporting is temporarily unavailable, use the private security contact mechanism explicitly configured by the repository maintainers. Do not disclose the vulnerability publicly while waiting for a response.

## What to include

A useful report should contain, where safely possible:

- affected version, tag, or commit;
- affected component or file;
- vulnerability type;
- clear description of the security impact;
- reproducible steps;
- minimal proof of concept;
- expected behavior;
- actual behavior;
- relevant logs or stack traces;
- suggested remediation, if known.

Please do not include live credentials, personal data, customer information, or unrelated sensitive material.

## Scope

Security reports may include vulnerabilities in:

- Seraph Guard source code;
- the CLI;
- scanner implementations;
- intelligence and prioritization logic;
- repository parsing or graph construction;
- output serialization;
- policy processing;
- suppression and learning behavior;
- fixers;
- LSP functionality;
- CI/release automation;
- packaging and distribution;
- security-sensitive dependencies introduced by the project.

## Coordinated disclosure

Please allow maintainers reasonable time to:

1. validate the report;
2. determine affected versions;
3. develop and test a fix;
4. prepare release guidance;
5. coordinate disclosure where appropriate.

Do not publicly disclose a vulnerability before a fix or coordinated disclosure decision unless disclosure is required by an applicable policy or law.

## Security advisories

When appropriate, maintainers may use GitHub repository security advisories to privately coordinate a fix and later publish the advisory.

A published advisory should identify affected versions and, where possible, the fixed version.

## Supported versions

The security status of a version depends on the release and maintenance policy stated in its release documentation.

Users should keep Seraph Guard and its dependencies updated.

For a pre-release or beta version, security fixes may be prioritized according to severity and reproducibility, but no beta release should be interpreted as having a guarantee of vulnerability-free operation.

## Security design principles

Seraph Guard aims to follow these principles:

- least privilege;
- deterministic behavior where practical;
- explicit evidence provenance;
- conservative interpretation of uncertain evidence;
- no secret leakage through explanations or outputs;
- safe handling of untrusted repositories;
- reproducible validation;
- explicit limitations;
- secure CI/CD practices.

The project does not claim that these principles make the software invulnerable.

## Reporting suspected secret exposure

If you discover that a credential or secret has been committed:

1. Do not reuse or publish the secret.
2. Treat it as compromised.
3. Report the exposure privately.
4. The maintainer should revoke/rotate the credential immediately.
5. History remediation should be considered where appropriate.

Deleting a secret from the latest commit does not necessarily remove it from Git history.

## Security researchers

Responsible security research is welcome.

Please avoid actions that:

- access data that you do not own;
- disrupt services;
- destroy or modify third-party data;
- exfiltrate secrets;
- create unnecessary operational risk.

When a vulnerability can be demonstrated using a local test repository or synthetic fixture, prefer that approach.
