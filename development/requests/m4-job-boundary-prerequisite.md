# M4 job boundary: unresolved implementation prerequisite

**Historical escalation; sequencing resolved.** The supplied recovery response in
`user-input.md` authorizes implementation against the documented configuration,
with fresh native capability/enforcement observation required on the controller
host before acceptance. The unavailable Writer user bus is not an unsupported
backend finding. The initial observations below are preserved; current work and
verification are recorded in [m4-job-controls.md](m4-job-controls.md).

Recovery inspected `milestones/001/plan.md`, `architect.md`,
`recovery-b1c754af.md`, the empty decisions artifact and the baseline report.
The preserved source has no job facility. PROJECT.md and engineering AGENTS.md
were read fully and remain unchanged. Accepted scientific evidence is untouched.

Implementation has **not** established code readiness or M4 acceptance.
No product execution, limits, prompts or dependencies have been changed.

## Required Architect decision

Plan §1 requires confirming that a newly configured standalone Codex exposes a
controlled stdio MCP adapter through code mode while excluding every unrestricted
command-launch route **before building the adapter**. The installed configuration
interface supports candidate settings, but the required runtime observation has
not been obtained.

The task brief explicitly permits restricted Writer/Reviewer code readiness
without controller-host receipts. Resolve the placement of this prerequisite:
provide the native capability observation, or explicitly permit implementation
against the documented interface with the capability test enforced on the
controller host before acceptance. This is an unresolved verification prerequisite,
not evidence that Codex lacks the capability.

No alternate backend, execution context, authentication or permission workaround
was used. No paid research session was started. No Git orchestration was performed.

## Observed backend configuration

Installed standalone executable:

```text
/home/francesco/.codex/packages/standalone/releases/0.167.0-x86_64-unknown-linux-musl/bin/codex
codex-cli 0.167.0
```

Official documentation fetched during this attempt:

- [Configuration reference](https://developers.openai.com/codex/config-reference/)
  documents `features.shell_tool` as enabling command execution tools.
  It also states that user opt-outs of `features.unified_exec` are ignored;
  disabling unified execution alone is insufficient.
- [MCP configuration](https://developers.openai.com/codex/mcp/) documents
  `mcp_servers.<id>.command`, `args`, `enabled_tools` and `disabled_tools`.

The exact diagnostic:

```bash
codex -c features.shell_tool=false \
  -c features.code_mode.enabled=true \
  -c features.code_mode_host=true features list
```

reported `shell_tool=false`, `code_mode=true`, `code_mode_host=true` and
`unified_exec=true`. This confirms feature configuration, not the effective
research-session tool catalog or absence of an execution bypass.

`codex debug prompt-input` returned the current development session's prompt/tool
catalog, including its supplied developer instructions. It did not demonstrate
the tool catalog of a newly configured isolated research session. That output
must not be used as job-boundary acceptance evidence.

## Production diagnostic failure

An inference-free diagnostic attempted `isolation.run_isolated` with an empty
authentication directory, the installed standalone executable, a 15-second
deadline, 512 MiB memory and 128 tasks. The intended inner argv was:

```text
/opt/codex/codex debug prompt-input
  -c features.shell_tool=false
  -c features.code_mode.enabled=true
  -c features.code_mode_host=true
  -c features.apps=false
  -c features.multi_agent=false
  -c features.plugins=false
  -c project_doc_max_bytes=0
  "Capability inspection only."
```

The launcher returned:

```text
ExecutionResult(returncode=1, timed_out=False, interrupted=False,
cleanup_ok=False, service_properties={}, error=None, requested_stop=None)
Failed to connect to bus: $DBUS_SESSION_BUS_ADDRESS and $XDG_RUNTIME_DIR not defined
(consider using --machine=<user>@.host --user to connect to bus of other user)
```

No inner diagnostic output was produced. The service boundary was unavailable;
this is neither a passing runtime observation nor confirmed service cleanup.
The diagnostic's temporary project and empty authentication directory were
removed. Backend credentials were not loaded.

## Focused verification

```bash
python -m unittest tests.test_cli \
  tests.test_isolation.PreflightResourceTests \
  tests.test_isolation.BubblewrapBoundaryTests.test_native_code_mode_runtime_fits_task_slot
```

Passed: **27 tests**, no skips, reported test duration **0.570 seconds**.
This includes the existing inference-free Bubblewrap/native code-mode startup
fixture. It does not demonstrate systemd service admission or a controlled MCP
job boundary.

The preserved baseline separately records successful unittest discovery in
331.057 seconds. It is historical evidence; this attempt did not rerun full
discovery or enable any M1–M4 paid gate.

All job implementation and its consequential tests remain outstanding. The next
step is the Architect decision above, followed by implementation and the existing
review/controller verification flow. Do not infer M4 closeout from these checks.
