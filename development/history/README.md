# Historical development records

Explains how to inspect past decisions, grants and execution checkpoints without loading them during normal session startup.

## Reading layers

- Current state and instructions stay at their established root/development paths.
- Topic snapshots retain the complete earlier narratives with rebased links and explicit historical labels.
- authorization/ contains every original authority/amendment/checkpoint section separately; dates and actual supersession govern effect.
- requirements/ indexes individual evidence checkpoints by topic and referenced requirement IDs.
- changelog/ groups preserved and subsequent change entries by date, linking their owning evidence.
- Individual DEV definitions live under development/decisions/ and are indexed by DECISIONS.md.
- originals/2026-11-06/ retains all 164 initial Markdown inputs losslessly (163 plain-text originals and the specification in deterministic gzip form); MANIFEST.md records paths,bytes and SHA-256.

## Authority and preservation

Archived instructions describe their recorded context and never override current human authority or AGENTS.md. Raw copies preserve original relative links exactly; use topic views or indexes for navigation. Frozen requests,the specification,product files,CWI-owned state and backend remain at their original locations and unchanged.

Future current-state updates replace the appropriate view and link to owning run/decision records. Preserve superseded administrative material in dated history when needed; do not reconstruct old evidence from a summary or duplicate raw controller logs into this tree.

## Migration evidence

[Reference cleanup](reference-cleanup-2026-11-06/README.md) records the subsequent semantic-role corrections and exact pre-cleanup versions. [Verification](VERIFICATION.md) records the original migration checks. [DEV-094](../decisions/ADR-094-development-records.md) records the authorized scope and validation. [MANIFEST](MANIFEST.md) enables exact recovery of every original input. [FOLDER_CONTENT](FOLDER_CONTENT.md) describes immediate children.
