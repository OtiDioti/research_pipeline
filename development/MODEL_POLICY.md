# Development model and reasoning policy

## User requirement and current ambiguity

The requested development model is **“Astra 6.1.”** Do not silently replace it with another model, infer an API identifier from the display label, or fall back to the user's ordinary Codex default.

On 2026-10-30, the official OpenAI model catalog inspected for this update listed **GPT-6 Astra (`gpt-6-astra`)** and **GPT-6.1 Sol (`gpt-6.1-sol`)**. I did not verify an official identifier for “Astra 6.1.” This is a model-selection ambiguity, not authorization to choose either listed alternative. The installed client's authenticated model list may supply additional evidence; a local alias must be traced to its actual provider/model mapping. Never create a misleading alias merely to satisfy the requested name.

Before launching any CWI model-dependent run:

1. Inspect the actual compatible Codex installation, account access, selected provider, supported model catalog, and supported reasoning levels.
2. Record the exact requested name, verified model identifier, evidence, and effective provider in [ENVIRONMENT.md](ENVIRONMENT.md).
3. If the requested model cannot be established, record `MODEL_SELECTION_REQUIRED` and ask the human to identify/approve the available model. Read-only inspection and administrative preparation may continue, but do not run implementation with a substitute.
4. Any human-approved alternative becomes an explicit model-policy decision, not a silent correction of this document.

This governs **development agents**. It does not make that model or Codex a mandatory runtime provider of the finished scientific product. Runtime adapter choices remain separate product decisions.

## Reasoning effort

Use only supported values from `low`, `medium`, `high`, and `xhigh`. **Extra-high means `xhigh`; it is the hard ceiling.** Do not use `max`, `ultra`, auto-escalation above the ceiling, or a hidden higher default.

| Workload | Suggested effort |
| --- | --- |
| Routine constrained work with little ambiguity | low or medium |
| Normal feature development, interface work, tests | medium |
| Architecture, provenance/recovery, security-sensitive changes, difficult debugging | high |
| Demonstrably difficult reasoning after lower effort proved inadequate | xhigh, with a recorded reason |

Choose effort for the hardest consequential responsibility in the request, not only the Writer's easiest task. Lower effort is not permission to skip verification. If the model does not support a chosen level, select a supported level at or below the ceiling before launch; do not accept an undocumented fallback.

## What the reviewed CWI backend actually supports

The supplied backend accepts `start --model NAME --reasoning EFFORT`. It freezes **one model and one effort for the entire run**, including its role invocations. It passes the model to Codex `--model` and the effort through `-c model_reasoning_effort=...`. Its state consistency checks require those values to remain unchanged on resume. These facts come from `cwi/cli.py`, `cwi/codex_cli.py`, `cwi/state.py`, and `cwi/state_store.py` in the reviewed archive.

Therefore adapt effort **between bounded runs**, not by editing a running session or claiming unsupported per-role settings. Split substantially different workloads when that produces a coherent independent request. Do not patch the backend just to add a desired optimization that is not needed for correctness.

The adapter deliberately ignores user configuration and disables other discovery paths. Setting the outer session's model, adding text to a prompt, or changing a normal Codex profile alone does not configure CWI's child roles. Always pass explicit flags and inspect frozen state and retained invocation evidence. A model's textual self-identification is not verification of its backend identity. If effective-model telemetry is unavailable, report that limitation separately from verified requested settings.

## Launch contract

Set non-secret shell variables only after resolution, for example `CWI_MODEL` to the verified identifier and `CWI_REASONING` to `medium`. They need not be exported: the runbook passes their values explicitly to CWI. Exporting new variables during an unfinished run can change its inherited-environment digest.

Before launch, the coordinator enforces:

- Nonempty, verified model identifier with no unapproved substitution.
- An explicitly selected effort in the supported allow-list, never above `xhigh`.
- Compatibility of the actual installed Codex with CWI's required parser/security flags.
- Permission and resource allowance for the actual authenticated billing mode.

The CLI's acceptance of a string is not proof that the service supports it. The current backend does not independently enforce this project's model identity or effort ceiling; these are checked coordination rules, not a claim of an installed hard gate. A future machine-enforced launcher must be implemented and tested through CWI if required.

An older unfinished run with incompatible frozen model settings must not be silently resumed under the new policy or altered in place. Inspect it, preserve it, and seek an explicit disposition under the recovery procedure.

## Official references checked for this update

- OpenAI model catalog: https://developers.openai.com/api/docs/models
- OpenAI reasoning guide: https://developers.openai.com/api/docs/guides/reasoning
- Codex configuration reference: https://developers.openai.com/codex/config-reference
- Codex non-interactive execution and session resume: https://developers.openai.com/codex/noninteractive

Availability and supported settings can change. Recheck when selecting a new installation/model, but never upgrade or change a frozen run's environment merely to match newer documentation.
