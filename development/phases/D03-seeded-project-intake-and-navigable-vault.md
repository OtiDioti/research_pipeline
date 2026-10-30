# D03 — Seeded project intake and navigable vault

**State:** PREPARED for REQ-D03-001 local-source-capture subset. D02 work-product authoring predecessor is evidenced; D03 intake/vault outcomes remain incomplete.

**Goal:** Create a usable research project from supplied scientific material, with an Obsidian-compatible human view.

**Dependencies:** D02 engineering contracts actually needed by the next request; empirical acceptance is tracked separately.

**Specification:** [project_description.md](../../project_description.md), v1.4, reconciled in [REQUIREMENTS.md](../REQUIREMENTS.md).

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

## Current v1.4 gate — Nonempty intake and protected snapshot views

**Requirement ownership:** R-020–R-031, R-040, R-082, R-092. All constituent obligations in those rows and cited original sections apply; no product evidence exists yet.

Enforce awaiting_materials/readiness with relevant inspected substantive material. Preserve original corpus/path mapping, partial inspection and candidate exposure. Implement the full §9.7 layout and §9.8 README contract; snapshots publish consistently, immutable artifacts have no writable hard links, and direct human edits/renames survive regeneration. Test archive confinement, imported configuration nonactivation, typed-link authority and ordinary Markdown portability.

- [ ] Link each owned obligation to executed checks/reviews and exact accepted/integrated source.
- [ ] Preserve any missing live, expert or human evidence as an explicit blocker; do not infer it from fixture success.

## Engineering and scientific acceptance tracked separately

Under specification v1.4, relevant implemented predecessor contracts and deterministic/fault evidence gate engineering. M0-E is evidenced per consumed contract, not completed by this plan. M0-S (R-001–R-003) and live interoperability remain pending until actual approvals/evidence exist; they block only the affected scientific evaluations, qualification claims and final release. An engineering-complete subset may enable subsequent independent work while the whole mixed phase remains partial. No exposed development fixture becomes held-out evidence, and scientific standards must precede scored evaluation.

## Historical pre-REQ-D02-006 checkpoint, 2026-10-30

D02 storage/backups, schema evolution and six typed scientific/assessment contracts are evidenced. REQ-D02-006 commissions work-product manifests and safe draft checkout/import as a concrete D03 dependency; it is prepared, not yet implemented. D03 intake, consistent navigable snapshots and human-edit protection are not claimed complete. Independent authoring infrastructure does not require scientific pilot approval, while readiness/qualification still require their specific judgments.

## Current predecessor and bounded request

REQ-D02-006 is now accepted/exact-integrated at a56111f3 with 291/291 tests, closing its manifest/checkout/preview/import subset. Generated-view refresh and direct-edit/rename protection remain unimplemented. [REQ-D03-001](../requests/REQ-D03-001.md) commissions strict versioned sources and bounded explicit local ingestion with immutable originals, exact lineage, attributed coverage and saved CAS proposals. This prepares real intake inputs without claiming readiness, source understanding, faithful extraction, expert audit or live acquisition. At most two CWI milestones; unchanged AUTH revision 5. D02's remaining eligibility/authority work and M0-S do not block this independent storage boundary, and remain owned/pending.
