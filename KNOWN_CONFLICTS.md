# Known behavioral and design conflicts

Updated 2026-11-13. This report follows the human's request to audit behavior and overengineering risks while the pipeline advances. These findings are confirmed in accepted L4 source (`3a23c69`) and remain in the reviewed first L5 increment (`738bbe3`); they are not attributed to the current unfinished pause/crash-recovery changes. No product source or historical scientific artifact was changed by this audit.

The existing L5 request remains active. These are material follow-up findings, with minimal correction directions rather than an instruction to build another subsystem. Pipeline reports still establish the scope of prior engineering acceptance; they did not test these portability and input-format cases.

## C1 — Scientific artifacts depend on runtime-only link resolution

**Confirmed; material portability conflict.** PROJECT.md §§4.2, 5 and 5.2 require ordinary portable directories, Markdown links and scientific artifacts intelligible without agent logs or a proprietary database.

`Coordinator.finalize_publications()` passes draft text to `workspace.publish_drafts()`, which writes it unchanged. Scientific intake and checkpoint instructions encourage `document:ID` links. There is no publication step converting those references or sandbox-absolute `/project/...` links into navigable links relative to the published file. Frozen packets also use `/project/...` links.

Actual passed L4 native evidence contains:

- `work/FINDINGS.md`: one `document:` link and two `/project/...` links.
- `work/NUMERICAL_CHECK.md`: two `/project/...` links.
- `handoffs/primary.md`: three `document:` links.

The scientific content exists, but ordinary editors cannot follow these links after opening or relocating the project. Understanding an immutable reference requires runtime lookup despite the file-based scientific workspace requirement.

**Smallest direction:** retain exact evidence versions while exposing ordinary relative links to retained files. Preserve reviewed hashes and raw immutable records; avoid a new resolver service, export framework or universal provenance graph. Include a plain-directory navigation check in the eventual pipeline repair.

Source: [publication](src/research_pipeline/collaboration.py), [draft writes](src/research_pipeline/workspace.py), [snapshot storage](src/research_pipeline/documents.py), [packet link rewriting](src/research_pipeline/verification.py), [agent instructions](src/research_pipeline/codex.py). Relevant functions: `finalize_publications`, `publish_drafts`, `freeze`, `checkpoint_prompt`.

## C2 — Terminal scientific handoffs mirror complete operational state

**Confirmed; material documentation/complexity conflict.** PROJECT.md §§4.2, 5.3 and 6.1 call for artifact-centered provenance and concise scientific handoffs, keeping operational diagnostics separate from scientific notes.

`save_scientific_terminal()` serializes all tasks, jobs, contexts and documents into the decision Markdown, including retained job stdout and telemetry. It writes the same body to the terminal marker; the acknowledgement copies it again. This grows with the investigation's entire retained runtime history rather than the information needed to understand a decision or continue useful science.

For the small passed L4 native example, the generated decision handoff is **83,011 bytes / 1,081 lines**, with five embedded stdout records and native telemetry. Its primary scientific handoff is 3,175 bytes / 44 lines. The raw dump duplicates material already retained in ordinary scientific files and private runtime records.

**Smallest direction:** render a concise account of reasons, opponent findings, unresolved questions, artifact links and actual cleanup/job outcomes. Keep full command output and operational records in their existing diagnostic storage. Preserve truthful failure reporting and useful partial work without adding a general reporting framework or deleting historical evidence.

Source: `Coordinator.save_scientific_terminal()` in [collaboration.py](src/research_pipeline/collaboration.py). This audit observes duplicated operational records; it does not claim full conversation replay or exponential growth.

## C3 — Ordinary authoritative-input navigation becomes mandatory evidence structure

**Confirmed; material scientific-input/lifecycle conflict.** PROJECT.md §§3.1 and 5.1 accept natural-language questions and optional human-owned instructions, which agents cannot edit. Scientific rigor requires freezing relevant evidence; it does not require the human to format all navigation as a verification packet.

`propose_decision()` automatically includes questions, `AGENTS.md` and feedback in `freeze()`. The freezer interprets Markdown links in these authoritative input copies as required scientific dependencies. Consequently, a harmless instruction link such as `[project notes](README.md)` can reject the terminal packet because the root README is outside the restricted scientific-path whitelist. The researcher cannot repair the protected instructions.

An isolated reproduction held the proposal and derivation fixed:

| Human instructions | Result |
| --- | --- |
| Plain instructions | Packet accepted |
| Same instructions with a link to project README | `InputError: Verification input must be scientific, not operational` |

This is also consistent with the historical L4 fixture failure where an illustrative `document:ID` in protected instructions blocked proposal freezing. That fixture repair changed its wording; it did not remove the underlying coupling.

**Smallest direction:** preserve authoritative input bytes and version binding without treating every illustrative/navigation link as declared scientific evidence. Continue validating the actual submitted scientific evidence and its required dependencies. Avoid expanding this into a universal Markdown parser or dependency engine.

Source: `Coordinator.propose_decision()` in [collaboration.py](src/research_pipeline/collaboration.py), `freeze()` / `link_path()` / `scientific_path()` in [verification.py](src/research_pipeline/verification.py).

## Audit evidence and boundaries

Private engineering receipts are in `coding_pipeline/logs/manager/v0-l5-continuity-20261113T063510Z-a187c3d5/`: `audit-conflicts.json` and `audit-input-link-reproduction.json`. The public native artifacts are retained under the L4 request's `native-host-2i4gtxur/project/`; they were read, not changed. The synthetic input fixture was removed after reproduction. No native inference, scientific job, extra implementation request or component repair was launched for this audit.

The original PROJECT.md M2 and the lifecycle amendment's L5 overlap intentionally; the amendment explicitly resolves older conflicting timers, thresholds and reopening rules. The pipeline's internal second L5 step is pause/crash recovery, not the original M2. This naming ambiguity is clarified in STATUS.md and is not an unresolved product-requirements conflict.
