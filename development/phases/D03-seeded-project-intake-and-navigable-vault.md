# D03 — Seeded project intake and navigable vault

**State:** NOT_STARTED. This plan is a proposed scope, not execution evidence.

**Goal:** Create a usable research project from supplied scientific material, with an Obsidian-compatible human view.

**Dependencies:** D02

**Specification:** [project_description.md](../../project_description.md), with exact references to be reconciled in [REQUIREMENTS.md](../REQUIREMENTS.md) during D00.

## Outcomes

1. Preserve original seeds; inventory and bound inspection; record exact origins, content versions, unread material, and provisional interpretations.
2. Build the specification’s scientific vault structure, folder indexes, relative Markdown links, notation records, draft/commit distinction, and read-only/generated views.
3. Import notes and paper captures as unverified starting material. Support conflicts and partial coverage rather than requiring every item to be understood first.
4. Preserve human edits before regeneration. Keep live research vaults separate from the software repository.

## Acceptance obligations

- [ ] A mixed seed fixture creates a navigable project without changing originals or accepting their claims by default.
- [ ] A human can follow a claim to its context and exact sources; missing/broken links are reported.
- [ ] Unexpected edits to generated views are preserved or block replacement. Large intake can stop with explicit partial coverage.

## Important failure cases

- An input path escapes the project, a symlink targets an unrelated file, or a source contains hostile instructions.
- Duplicate paper versions are conflated or a generated index overwrites a human draft.
- The product refuses a useful but incomplete seed collection.

## Execution and evidence

Before execution, divide these outcomes into the smallest coherent requests with independently testable results. Do not invent every function signature months ahead of its dependencies. The active request fixes its public interfaces, exact changed paths, validation, scope, and stop conditions before CWI starts. A phase may require multiple runs. Record each final receipt/source pair, integration commit, requirement evidence, limitations, and newly deferred items.

Operational details: [runbook](../RUNBOOK.md), [request template](../templates/REQUEST.md), [run record](../templates/RUN.md).
