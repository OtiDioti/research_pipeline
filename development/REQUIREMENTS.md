# Specification-to-evidence crosswalk

**Initial state: reconciliation required.** The existing `project_description.md` was not part of the supplied coding-pipeline archive and is deliberately not reproduced by this kit. The table below is a conceptual coverage map drawn from the conversation, not proof that the full local specification has been exhaustively mapped.

At D00, read the entire exact file and assign a stable ID to each mandatory, independently verifiable obligation. Record its source heading and a short exact quotation or unambiguous description. Split broad rows below where needed. Record the specification content hash or source commit. Preserve prior mappings when the specification changes.

| Provisional group | Obligation family | Proposed phase | Exact local source | Evidence / implementation |
| --- | --- | --- | --- | --- |
| RG-01 | Scientific usefulness, scoped claims, honest unresolved outcomes | D00, D06, D10 | To reconcile | Not implemented |
| RG-02 | Versioned assumptions, claims, justifications, alternative support, evidence and objections | D02 | To reconcile | Not implemented |
| RG-03 | Separate scientific graph and task graph; transactional authority | D02, D04 | To reconcile | Not implemented |
| RG-04 | Seed preservation, bounded intake, existing notes/papers, provisional interpretation | D03 | To reconcile | Not implemented |
| RG-05 | Obsidian-compatible vault, folder indexes, links, drafts, safe human editing | D03, D09 | To reconcile | Not implemented |
| RG-06 | Tool-agnostic capability registry, qualification, permissions and provenance | D05 | To reconcile | Not implemented |
| RG-07 | Research notes, exact derivations, LaTeX/PDF dependencies, executable computations | D06 | To reconcile | Not implemented |
| RG-08 | Source acquisition, versioned paper captures, critical reports, search coverage | D06 | To reconcile | Not implemented |
| RG-09 | Coherent research sessions, checkpoint memory and context assembly | D04, D06 | To reconcile | Not implemented |
| RG-10 | Coordinator/controller division, dynamic roles and recorded communication | D04, D08 | To reconcile | Not implemented |
| RG-11 | Blind reconstruction, restricted visibility, targeted review and disputes | D07 | To reconcile | Not implemented |
| RG-12 | Mathematical, numerical, physical, formal and novelty assessments | D07 | To reconcile | Not implemented |
| RG-13 | Scoped promotion, current support, revision impacts and human decisions | D02, D07 | To reconcile | Not implemented |
| RG-14 | Budgets, uncertain liabilities, nested tasks, interruption and recovery | D04, D05 | To reconcile | Not implemented |
| RG-15 | Synthesis, reporting, export, backup/restore and navigability | D09 | To reconcile | Not implemented |
| RG-16 | Scientific evaluation, strong baseline, useful outputs and falsification tasks | D10 | To reconcile | Not implemented |
| RG-17 | Security, untrusted documents, isolation, credentials and data policy | D03–D09 | To reconcile | Not implemented |

## Required form after reconciliation

For each actual requirement record: ID; source version and location; requirement; priority and dependencies; owning phase; active/future request; state; test or review evidence; exact accepted source and integrated source; limitations; and authorized deferral where applicable. Keep long records in linked files if the table becomes unreadable.

Permitted states are `UNMAPPED`, `PLANNED`, `IN_PROGRESS`, `EVIDENCED_NOT_INTEGRATED`, `INTEGRATED`, `DEFERRED_AUTHORIZED`, and `BLOCKED`. They describe development obligations, not scientific truth.

A test passing is evidence only for the behavior it actually exercises. Review text, source provenance, and human assessment may also be required. Do not mark a broad scientific feature established by a mock response or a test of a JSON schema alone.

## Whole-scope completion audit

At phase boundaries and before declaring completion, reconcile this map against the actual specification revision and integrated source. Every mandatory obligation needs real evidence or an explicit unresolved state. A coordinator may not redefine a mandatory requirement as optional to satisfy the continuous-development completion gate. Authorized scope reduction must identify the narrower delivered scope without claiming the original project is complete.
