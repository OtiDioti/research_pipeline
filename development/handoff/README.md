# Restart development on another machine

This handoff was captured on 2026-11-13. It preserves the interrupted L5
development run and explains how to restore its checkpoint in a new clone.
Read [the current status](../../STATUS.md) first. STATUS.md remains the
authoritative account of what is accepted and what remains unfinished.

**Restoration does not start work.** It creates an inspectable checkpoint and
worktree. Starting the manager is a separate action. No native research or paid
validation was started to produce this handoff.

## What to recover

| Source | Meaning |
| --- | --- |
| `main` | Accepted L1-L4 implementation, project requirements and this handoff. |
| `cwi/20261113T063709_7f21ba4a` at `2e3e7b3e95714e9aa08d84b1d11f7bea01707105` | Reviewed L5 implementation; final verification is interrupted. Keep it unaccepted until the required gates pass. |
| `cwi/20261111T063907_2732fff6` at `1b70aea25f6c5f8496acdea12e9a27c6f3d4ecbd` | Inactive historical M5 candidate. Preserve it; do not resume or merge it. |

The next action is **L5 final verification**, after reconciling ownership and
setting up real native prerequisites. It is not another implementation request.
After L5 acceptance, the recorded follow-ups are the confirmed C1-C3 portability
issues, L6 integrated validation, and eventually a new M5 attempt. Human scientific
acceptance of M5 remains mandatory.

## Files in this handoff

- [MANAGER_BRIEF.md](MANAGER_BRIEF.md): the recovery instructions to give the next manager.
- [l5/README.md](l5/README.md): current L5 evidence and the meaning of earlier failures.
- [l5/request.md](l5/request.md), [l5/config.toml](l5/config.toml) and
  [l5/roadmap.md](l5/roadmap.md): unchanged frozen inputs and roadmap.
- [acceptance/README.md](acceptance/README.md): selected L1-L4 acceptance records.
- [restore_l5.py](restore_l5.py): offline restoration into a fresh clone.
- [CONTENTS.json](CONTENTS.json): original locations and hashes of copied records,
  including each archived file. Historical absolute paths identify the old host.
- [SHA256SUMS](SHA256SUMS): checksums for all published handoff files.
- [VALIDATION.md](VALIDATION.md): what was actually checked while packaging this handoff.

The checkpoint archive contains the L5 state, roadmap, milestone reports, diffs
and test output. It excludes the old Git worktree, process locks, credentials and
disposable model runtime. A separate archive preserves final-006's interrupted
native science as historical evidence; it is never restored as a live process.
This is a selected recovery package, not a backup of every old pipeline run.

## 1. Clone the project and the recorded components

Use a Linux host with Git, Python 3.11 or later, venv and pip. Install a compatible
standalone Codex executable and authenticate on the new machine through its native
file credential store. Credentials and model sessions are not in this handoff.

These are the component revisions used by the preserved run. Do not substitute
the latest component `main` branches during recovery.

| Repository | Revision |
| --- | --- |
| `git@github.com:OtiDioti/coding_pipeline.git` | `5bc0fbb04ad4e104f252f0dbd61361f62f3085d5` |
| `git@github.com:OtiDioti/codex_controller.git` | `80063c7a7bbcc615146385b543ea6f921873ccaf` |
| `git@github.com:OtiDioti/project_manager.git` | `1b13f917f94af5b20accc27bdf64c4f6b7403d41` |

Run the following in one shell, choosing a new empty workspace:

```sh
WORKSPACE="$HOME/research-restart"
mkdir -p "$WORKSPACE"
git clone git@github.com:OtiDioti/research_pipeline.git "$WORKSPACE/research_pipeline"
PROJECT="$WORKSPACE/research_pipeline"
CONTROLLER="$WORKSPACE/research_pipeline.codex_controller"

git clone git@github.com:OtiDioti/coding_pipeline.git "$PROJECT/coding_pipeline"
git -C "$PROJECT/coding_pipeline" checkout --detach 5bc0fbb04ad4e104f252f0dbd61361f62f3085d5
git clone git@github.com:OtiDioti/codex_controller.git "$CONTROLLER"
git -C "$CONTROLLER" checkout -b handoff-local-setup 80063c7a7bbcc615146385b543ea6f921873ccaf
git clone git@github.com:OtiDioti/project_manager.git "$WORKSPACE/project_manager"
git -C "$WORKSPACE/project_manager" checkout --detach 1b13f917f94af5b20accc27bdf64c4f6b7403d41

python3.11 -m venv "$WORKSPACE/research-env"
PYTHON="$WORKSPACE/research-env/bin/python"
"$PYTHON" -m pip install -e "$PROJECT" -e "$PROJECT/coding_pipeline" \
  -r "$CONTROLLER/requirements.txt" 'mcp==1.30.0'

cd "$PROJECT/development/handoff"
sha256sum --check SHA256SUMS
cd "$PROJECT"
```

The environment is outside the project so it does not make the target dirty.
MCP 1.30.0 and prompt_toolkit 3.0.52 were present on the capture host. The original
host used Python 3.11.15, `codex-cli 0.167.2`, Bubblewrap 0.6.1 and systemd 249.
Those observations are not a lockfile for the host operating system. The Codex
binary is not distributed here; its required exec/app-server interfaces must pass
the component checks on the new host.

Prepare the new controller's paths and prompts. This command makes no model
calls, preserves the project's STATUS.md, and may create a local controller
configuration commit in the **new** component clone:

```sh
"$PYTHON" "$WORKSPACE/project_manager/prepare.py" "$PROJECT" \
  --controller-dir "$CONTROLLER" --refresh-prompts
git -C "$PROJECT" status --short
```

The final command should print nothing. If preparation fails, resolve its named
prerequisite before continuing. Do not apply speculative component upgrades.

## 2. Restore and inspect L5 without executing it

First ensure the old machine's manager and workers remain stopped. A receipt from
2026-11-13 describes that shutdown; it does not prove that nobody restarted them.

```sh
"$PYTHON" "$PROJECT/development/handoff/restore_l5.py" "$PROJECT"

flow() { "$PYTHON" "$PROJECT/coding_pipeline/bin/agentic-flow" "$@"; }
flow discover "$PROJECT" --request-id v0-l5-continuity-20261113T063510Z-a187c3d5
flow status 20261113T063709_7f21ba4a
flow report 20261113T063709_7f21ba4a
```

Expected: one interrupted run in phase `final`, milestone 5, integration attempt
3, with source head `2e3e7b3`. The worktree should exist. Historical verification
may still say `regression`: that saved result describes final-005, whose defect
received the reviewed repair. It does not describe a completed final-006.

The restorer verifies the checkpoint checksum and pinned pipeline revision,
creates a new Git worktree and its pipeline ownership record, updates active
checkpoint paths and selects the Python interpreter that invoked it. Frozen
request text, configuration and historical command records retain their original
meaning. A restoration record identifies the changes. The original archive stays
unchanged. An existing run or manager directory is refused; it is never replaced.
If restoration fails after creating files, inspect the partial destination or
retry in another fresh clone. Do not delete unknown work to make a retry pass.

The inactive M5 branch remains available from GitHub. Its old pipeline worktree
and checkpoint are not restored by this command.

## 3. Start the recovered workflow only when prerequisites are ready

Native L5 validation needs Bubblewrap, an authorized systemd user bus, `busctl`,
cgroup v2 memory/swap/tasks controls, native file authentication, and actual
sufficient weekly quota. Re-establish these on the new host. Do not copy old
PIDs, services, cgroup identities or authentication files into active ownership.
Do not invent another user's bus address or relax isolation to make a gate pass.

The saved configuration has **`auto_merge = true`**. A later `flow resume` can
merge L5 after successful final and combined verification. Restoration itself
does not authorize acceptance, merge, push or new scientific work. Confirm that
automatic integration is intended before starting the manager.

Disable historical gates and enable both required L5 gates through their shared
switch. The tests reserve distinct output directories beneath the configured
prefix for fresh final and combined results:

```sh
export RESEARCH_PIPELINE_M1_LIVE=0 RESEARCH_PIPELINE_M2_LIVE=0
export RESEARCH_PIPELINE_M3_LIVE=0 RESEARCH_PIPELINE_M4_LIVE=0 RESEARCH_PIPELINE_M5_LIVE=0
export RESEARCH_PIPELINE_V0_L1_NATIVE=0 RESEARCH_PIPELINE_V0_L2_NATIVE=0
export RESEARCH_PIPELINE_V0_L3_NATIVE=0 RESEARCH_PIPELINE_V0_L4_NATIVE=0
export RESEARCH_PIPELINE_V0_L5_NATIVE=1
export RESEARCH_PIPELINE_V0_L5_OUTPUT_DIR="$PROJECT/coding_pipeline/logs/manager/v0-l5-continuity-20261113T063510Z-a187c3d5/native-host"
```

After installing the editable package, fresh test processes can import the source
without the old machine's temporary MCP dependency directory. Avoid stale
PYTHONPATH overrides from that machine. Normal authentication and the authorized
user bus must be inherited by the controller and its test processes.

Combine the newly generated generic manager instructions with this handoff's
recovery brief, then launch in an interactive terminal:

```sh
PROMPT="$PROJECT/coding_pipeline/logs/manager/restart-startup.md"
cat "$CONTROLLER/startup_prompt.txt" "$PROJECT/development/handoff/MANAGER_BRIEF.md" > "$PROMPT"
"$PYTHON" "$CONTROLLER/codex_controller.py" \
  --project-dir "$PROJECT" --stop-file "$PROJECT/COMPLETE" \
  --startup-prompt "$PROMPT"
```

This launch leaves Git publication disabled. Add the controller's exact `--push`
flag only when publication is explicitly authorized for that new invocation.
The manager should reconcile the restored state, then use ordinary
`flow resume 20261113T063709_7f21ba4a`. Do not send the old final-005 failure back
for duplicate repair with an unconditional `--retry`.

## Maintaining the handoff

After further development, update STATUS.md first. If the recovery checkpoint
changes, capture a new, clearly dated handoff and regenerate its checksums.
Keep the original evidence hashes and outcomes. Do not overwrite these historical
receipts with later successful results or treat this capture as a live checkpoint.
