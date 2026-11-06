# Development model and reasoning policy

Defines approved development-role selections, reasoning limits, fresh-access verification and immutable historical settings.

## Effective decision — 2026-11-04

The human explicitly authorized these selections for new CWI runs under [AUTHORIZATION.md](AUTHORIZATION.md) revision 7:

| Role | Exact model identifier | Reasoning |
| --- | --- | --- |
| Designer | `gpt-6-astra` | `xhigh` |
| Architect | `gpt-6.1-sol` | `xhigh` |
| Writer | `gpt-6.1-sol` | `high` |
| Reviewer | `gpt-6.1-sol` | `high` |

Use all eight explicit start flags, with no global selection or fallback:

```text
--designer-model gpt-6-astra --designer-reasoning xhigh
--architect-model gpt-6.1-sol --architect-reasoning xhigh
--writer-model gpt-6.1-sol --writer-reasoning high
--reviewer-model gpt-6.1-sol --reviewer-reasoning high
```

These are development-agent selections. They do not make Codex or either model a mandatory runtime provider for the scientific product. The amendment changes no spending, start, repair, recovery, milestone, deadline, service, or scientific authorization.

## Readiness and evidence

Before a new model-dependent run, inspect the actual compatible Codex executable, account/provider access, supported model catalog and reasoning levels. Record stable identity/environment changes in [ENVIRONMENT.md](ENVIRONMENT.md). Put dated authentication, catalog and readiness observations in the relevant local attempt evidence and owning run record. The local catalog fetched `2026-11-04T16:39:43.361492207Z` advertises both exact identifiers and `high`/`xhigh`; the selected installed Codex is 0.166.0. This is advertised support, not live execution or a guarantee of future access. Fresh readiness remains required before product development resumes.

If an approved selection cannot be established, record `MODEL_SELECTION_REQUIRED` and stop model-dependent work. Read-only inspection and administrative preparation may continue. Do not invent aliases, silently substitute a model/effort, or accept a fallback. Changing this approved allocation requires actual human authorization.

Only supported reasoning values `low`, `medium`, `high`, and `xhigh` are permitted by the backend contract. **Extra-high means `xhigh`; it is the hard ceiling.** The current grant selects the exact values above, not arbitrary values from that allow-list. Never use `max`, `ultra`, or a higher implicit default.

The adapter isolates child configuration. Setting the outer session's model, changing a normal Codex profile or adding prompt text does not configure CWI's child roles. Inspect frozen role selections and available actual invocation arguments for every role, including resumed persistent sessions. A model's textual self-identification is not evidence of its backend identity. Report any absence of effective-model telemetry separately from verified requested settings.

## Frozen state and historical runs

The modernized backend uses schema revision 2 and freezes all four model/effort pairs. They remain immutable on resume; resume does not accept replacement selections. No migration of revision-1 state is authorized or supplied. Keep historical state, receipts, prompts and invocation evidence unchanged. Preserve the exact original backend revision and environment for historical inspection; do not automatically resume an old run using either backend. Any later recovery requires its own supported diagnosis and explicit disposition.

All eight values are explicit argv, not exported model-selection variables. Preserve the recorded stable launch environment; adding variables during an unfinished run can change its frozen digest. Backend parsing enforces required role flags and supported effort spellings; local/provider readiness and the exact human-approved allocation still require coordinator verification. Acceptance of a model string by the CLI does not establish service support.

## Historical decisions and original backend contract

The original request named “Astra 6.1.” The official catalog inspected on 2026-10-30 listed GPT-6 Astra (`gpt-6-astra`) and GPT-6.1 Sol (`gpt-6.1-sol`), without establishing an exact “Astra 6.1” identifier. The human then explicitly approved GPT-6 Astra under authorization revision 2. That decision authorized only `gpt-6-astra`; revision 7 now separately authorizes the role allocation above. The commissioning request selected `medium`.

The originally reviewed revision-1 backend accepted `start --model NAME --reasoning EFFORT` and froze one pair for the whole run. It passed the model to Codex `--model` and effort via `-c model_reasoning_effort=...`; state consistency required them unchanged on resume. These are historical facts from `cwi/cli.py`, `cwi/codex_cli.py`, `cwi/state.py` and `cwi/state_store.py`, not current launch instructions. Historical requests and runs retain their original settings.

## Official references inspected on 2026-10-30

- OpenAI model catalog: https://developers.openai.com/api/docs/models
- OpenAI reasoning guide: https://developers.openai.com/api/docs/guides/reasoning
- Codex configuration reference: https://developers.openai.com/codex/config-reference
- Codex non-interactive execution and session resume: https://developers.openai.com/codex/noninteractive

These references document the earlier inspection, not a new online availability check. Recheck readiness before future execution without changing any frozen run's environment to match newer documentation.
