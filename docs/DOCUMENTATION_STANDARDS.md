# QEDTY Documentation Standards

This document defines how Markdown documentation is written, reviewed, organized, and maintained in QEDTY.

The goal is documentation that is technically accurate, easy to navigate, useful to contributors, and consistent with the state of the repository. These rules apply to new and substantially revised Markdown files. Existing documents are migrated in controlled batches.

## 1. Documentation principles

QEDTY documentation follows these principles:

1. **Accuracy before presentation.** A document must distinguish implemented behavior from proposals, plans, assumptions, and research.
2. **One document, one primary purpose.** Do not combine a tutorial, architecture proposal, release record, and research survey into one file.
3. **Source of truth over duplication.** Keep detailed facts in one authoritative document and link to them elsewhere.
4. **Code and documentation evolve together.** Changes to public behavior, contracts, commands, or supported environments require corresponding documentation updates.
5. **Readable source.** Prefer ordinary GitHub Flavored Markdown over embedded HTML, decorative formatting, or complex tables.
6. **Traceable claims.** Link implementation, contracts, tests, issues, pull requests, decisions, and external references where they support a claim.
7. **Useful to its audience.** Explain what a reader needs to understand or do; remove material that does not serve the document's purpose.
8. **Maintainable over time.** Date time-sensitive research and status records. Remove stale instructions instead of allowing them to look current.

## 2. Documentation types

Choose the document type before writing. Use the corresponding structure rather than applying one template to every file.

| Type | Primary purpose | Recommended location |
|---|---|---|
| Repository README | Explain the project, current state, installation, quick start, and navigation | `README.md` |
| Documentation index | Help readers find the right document | `docs/README.md` |
| Concept | Explain a domain concept and its boundaries | `docs/<domain>/` |
| Architecture | Explain system structure, responsibilities, and data flow | `docs/ARCHITECTURE.md` |
| Architecture decision record (ADR) | Record one decision and its consequences | `docs/decisions/` or an established component decision directory |
| Contract reference | Define normative schemas, invariants, compatibility, and examples | `contracts/` and linked reference docs |
| How-to guide | Help a reader complete one task | `docs/how-to/` |
| Tutorial | Teach a complete workflow through a working example | `docs/tutorials/` |
| Operations guide | Explain deployment, diagnosis, recovery, and maintenance | `docs/operations/` |
| Research baseline | Record prior art, standards, evidence, gaps, and design implications | Existing domain research directories |
| Engineering record | Record implementation scope, decisions, validation, and remaining work | `docs/engineering/` |
| Release notes | Record user-visible changes by release | `CHANGELOG.md` |
| Contribution guide | Explain how to propose, implement, test, and submit changes | `CONTRIBUTING.md` |

Do not create a new document when an existing authoritative document can be improved without making it unfocused.

## 3. Standard document structure

Use this structure when it fits the document type:

```markdown
# Descriptive document title

One short paragraph stating what this document covers and who it is for.

## Scope

State what is covered and, where useful, what is out of scope.

## Main content

Organize the material around the reader's questions or tasks.

## Related documents

Link to the authoritative related documents.
```

Not every document needs every section. Short references should stay short. Do not add empty headings or boilerplate sections simply to satisfy a template.

### Titles and headings

- Use one level-one heading (`#`) for the document title.
- Use level-two headings (`##`) for main sections and level-three headings (`###`) for subsections.
- Do not skip heading levels to obtain a visual size.
- Use descriptive, specific headings. Avoid vague headings such as "Overview", "Details", or "More" when a more precise title is possible.
- Use sentence case for headings.
- Keep the first heading aligned with the filename.
- Leave a blank line before and after headings.

### Paragraphs and lists

- Keep paragraphs focused on one idea.
- Prefer active voice and direct wording.
- Define an acronym on first use unless it is universally understood by the intended audience.
- Use numbered lists for ordered procedures and unordered lists for unordered items.
- Use parallel grammatical structure within lists.
- Avoid repeating a paragraph as a table and then again as a summary.

### Tables

Use tables for compact comparisons or structured reference data. Do not use them for long prose, procedures, or content that must be read linearly. Keep tables narrow enough to render on common screens.

### Code and commands

- Use fenced code blocks with a language identifier.
- Commands must be runnable from the stated working directory.
- State prerequisites and expected effects when they are not obvious.
- Use placeholders such as `<path>` only when clearly explained.
- Never include secrets, personal access tokens, private endpoints, or machine-specific paths as if they were portable defaults.
- Distinguish illustrative snippets from executable examples.

### Links and images

- Use descriptive link text that makes sense out of context.
- Prefer relative links for files within this repository.
- Link to a specific source, issue, pull request, commit, or standard when making a traceable claim.
- Add meaningful alt text to informative images. Do not use images as a substitute for essential text.

### Markdown portability

- Prefer GitHub Flavored Markdown and CommonMark-compatible syntax.
- Prefer standard Markdown over raw HTML.
- Avoid emoji, decorative badges, excessive bold text, and presentation-only separators in engineering documentation.
- Keep prose lines near 80–100 characters where practical. Long links, tables, and code lines are reasonable exceptions.
- Use consistent list markers and fenced-code formatting within a document.

## 4. QEDTY status and evidence language

Every document that describes implementation or project status must make the status clear. Use these terms consistently:

| Term | Meaning |
|---|---|
| Implemented | Code or artifacts exist in the repository |
| Tested | A named test or verification procedure has been run |
| Conformant | The implementation passed a specified, bounded contract or conformance suite |
| Validated | Evidence supports the stated behavior within an explicitly defined scope |
| Planned | Accepted future work that is not implemented |
| Proposed | A design idea that has not been accepted as committed work |
| Deferred | Deliberately postponed work, with the reason recorded where material |
| Unsupported | Explicitly outside the current implementation or compatibility promise |

Do not use "complete", "production-ready", "planetary-scale", "real-time", "causal", "AI-powered", or "fully integrated" without defining the scope and evidence behind the claim.

For test claims, record:
- the exact commit or pull request head;
- the command or workflow;
- the relevant result;
- the scope and known exclusions.

A test count without a commit and test scope is historical context, not current verification. A passing CI run is not production certification.

## 5. QEDTY architecture and contract documentation

Architecture documents must identify:

- the component's responsibility;
- inputs and outputs;
- authoritative data and semantic ownership;
- dependencies and integration boundaries;
- invariants and failure behavior;
- implementation status;
- relevant contracts, tests, and decisions;
- known limitations and deferred work.

Contract documents are normative only when they explicitly say so. Identify the schema or contract version, compatibility policy, validation mechanism, and authoritative fixtures. Do not let explanatory prose silently override executable schemas or tests.

Keep the Python semantic/reference authority, Rust implementation scope, and future execution targets distinct. Do not describe a planned language, service, connector, or deployment target as implemented until its source and verification evidence exist.

## 6. Research documentation

Research documents must be reproducible enough for another engineer to understand why a design choice was made.

Include, as applicable:

1. Research question and scope.
2. Sources, links, publication dates, and access dates.
3. Relevant standards, specifications, and versions.
4. Findings supported by those sources.
5. Conflicting evidence and limitations.
6. QEDTY design implications.
7. Open questions and follow-up work.

Separate source facts from interpretation and QEDTY decisions. Do not cite a product page as proof of standards conformance. Do not retain dead links or undated claims as current facts.

## 7. Engineering records and phase documents

An engineering record should answer:

- What problem or gap was addressed?
- What exact scope was accepted?
- What changed?
- Which contracts and implementations are involved?
- How was it tested?
- Which commit, pull request, and hosted checks provide evidence?
- What remains out of scope or unresolved?

A phase or milestone document must distinguish its objective, entry criteria, deliverables, acceptance criteria, current status, and dependencies. A roadmap is not evidence that its planned work exists.

Do not silently rewrite historical acceptance records when later work changes the current state. Add a dated follow-up or update the current-status section while preserving the historical record.

## 8. README requirements

The root README is the repository's front door. It should answer, in this order:

1. What QEDTY is.
2. What problem it addresses.
3. What is implemented today.
4. How to install and run a minimal example.
5. How to run the relevant tests and validation.
6. Where to find architecture, contracts, research, roadmap, and contribution guidance.
7. What is explicitly not yet implemented.

Keep detailed implementation histories, large inventories, and research literature in their own documents. Link to them from the README.

Package-level READMEs should explain the package's purpose, status, key entry points, basic usage, tests, and links to deeper documentation.

## 9. Review checklist

Before merging a documentation change, verify:

- [ ] The document has one clear audience and purpose.
- [ ] The title and headings describe the content.
- [ ] Implemented, tested, validated, planned, and proposed work are not conflated.
- [ ] Technical claims agree with code, contracts, and current verification.
- [ ] Links resolve and point to the intended source.
- [ ] Commands and examples are accurate for the stated environment.
- [ ] No secrets, private paths, or machine-specific assumptions were introduced.
- [ ] The change removes duplication or links to the source of truth.
- [ ] Markdown renders correctly on GitHub.
- [ ] Related documentation was updated where behavior or interfaces changed.

## 10. Reference standards

These references inform the QEDTY documentation policy:

- [GitHub Docs style guide](https://docs.github.com/en/contributing/style-guide-and-content-model/style-guide)
- [GitHub Docs best practices](https://docs.github.com/en/contributing/writing-for-github-docs/best-practices-for-github-docs)
- [Google Markdown style guide](https://google.github.io/styleguide/docguide/style.html)
- [Google README guide](https://google.github.io/styleguide/docguide/READMEs.html)
- [Google documentation best practices](https://google.github.io/styleguide/docguide/best_practices.html)
- [Google developer documentation style guide](https://developers.google.com/style)
- [CommonMark specification](https://commonmark.org/)
- [GitHub Flavored Markdown specification](https://github.github.com/gfm/)
