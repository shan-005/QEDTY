# Support

Seraph Guard is an open-source security project. Please use the appropriate channel for the type of request.

## Documentation

Start with:

- `README.md`
- `docs/`
- command help:

```bash
seraph-guard --help
seraph-guard <command> --help
```

## Bug reports

Use the repository's **Bug Report** issue template.

A useful bug report should include:

- Seraph Guard version;
- Python version;
- operating system/environment;
- command executed;
- relevant configuration;
- expected behavior;
- actual behavior;
- minimal reproducible example where possible;
- sanitized logs or output.

Do not post credentials, private source code, customer information, or other sensitive data.

## Feature requests

Use the repository's **Feature Request** issue template.

Explain:

- the problem;
- the desired outcome;
- why the current behavior is insufficient;
- the proposed workflow;
- any compatibility considerations.

Feature requests are evaluated against the project's architecture, security model, maintenance cost, and scope.

## Security vulnerabilities

Do **not** use public issues for undisclosed security vulnerabilities.

Follow `SECURITY.md` and use GitHub's private vulnerability reporting mechanism when enabled.

## Questions and discussions

For general questions, use the public discussion/support mechanism configured on the repository.

Before opening a new request, search existing issues and discussions for the same problem.

## Good support requests

The fastest way to receive useful help is to provide:

```text
Seraph version:
Python version:
OS:
Command:
Expected:
Actual:
Reproduction:
Relevant sanitized output:
```

Do not include:

- passwords;
- API tokens;
- private keys;
- proprietary source;
- customer data;
- private repository contents.

## Scope

Seraph Guard is an open-source project and does not guarantee:

- production incident response;
- emergency security operations;
- forensic investigation;
- guaranteed compatibility with every repository;
- guaranteed detection of every vulnerability;
- guaranteed remediation of every finding.

For security-critical deployments, validate Seraph against the specific environment and workflow in which it will be used.
