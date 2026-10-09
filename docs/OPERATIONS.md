# Operations

Use locked dependencies in CI. Keep raw evidence outside Git. Record licensing and provenance for every external dataset. Publish signed artifacts and checksums. Do not treat a clean smoke test as proof of universal correctness.

## Repository change control

As checked on 2026-10-09, the active `main` ruleset prevents branch deletion and non-fast-forward updates, requires pull requests, and requires the `quality (3.12)`, `quality (3.13)`, `native`, `package` and `review` checks. It does not require an approving review or CODEOWNERS approval. This is a single-maintainer limitation, not independent review.

Until independent reviewers are configured, the maintainer should self-review the complete diff, verify every required check belongs to the proposed head SHA, record the rationale for security/contract/release changes, and ensure relevant contracts, schemas, vectors, implementation and docs move together. Do not describe that process as an independent approval. When independent reviewers become available, update the active GitHub ruleset and this policy together to require CODEOWNERS approval for high-risk files and at least one approving review.

The active GitHub ruleset is the actual control plane; a policy YAML requirement by itself does not configure GitHub protection. Re-check the live ruleset after governance or maintainer changes.
