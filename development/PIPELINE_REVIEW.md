# Coding-pipeline integration review

> **2026-10-30 policy note:** this remains the original snapshot review, not a re-run of its full test suite. The user now permits necessary focused backend repairs under [BACKEND_MAINTENANCE.md](BACKEND_MAINTENANCE.md), with [the root audit](../coding_pipeline_changes.md). The recommendation to leave a functioning backend unchanged still applies; the repair exception does not retroactively alter these findings. Current coordination additions were checked separately in [WORKFLOW_UPDATE_CHECKS.md](review/WORKFLOW_UPDATE_CHECKS.md).

## 1. Scope, source identity, and conclusion

The supplied repository implements **CWI — Codex Workflow Controller**. Its public source launcher is `coding_pipeline/bin/agentic-flow`.

Review coverage includes the complete 98-file inventory, Python static parsing, public documentation, all nine prompt templates, detailed integration-critical source paths, and execution of all 45 discovered test modules. The file inventory records exact content identities. This is a behavior/integration review and test report, not a proof of every code path or a complete security audit.

| Identity | Value |
| --- | --- |
| Archive SHA-256 | `2cc5d50f4e411418a2f0439b4d1e0b7a5d4fb4fdfd23448d708ac750b4af6d67` |
| Archive-comment revision | `122f86588f829387ea460a1e2a997a87ce325c53` |
| Revision verification | Reported by archive comment; not independently checked against a remote Git repository |
| Regular files / text lines | 98 / 50,420 |
| Code changes during review | None; original member hashes checked afterward |
| Live Codex execution | Not available in this review environment |

**Architectural recommendation:** use the existing backend unchanged as a separately pinned development dependency, subject to local readiness checks. Put a thin outer coordinator and human-readable checkpoints around its supported CLI rather than building another orchestration layer or changing its internals to fit the research project. Known test failures and real-CLI compatibility must be handled explicitly; this recommendation is not a blanket assertion that the backend passed all tests.

Read [TEST_RESULTS.md](review/TEST_RESULTS.md) before interpreting test coverage. All 1,031 discovered test cases were attempted across module shards: 1,000 passed, 17 skipped, 7 failed assertions and 7 errors. Follow-up experiments narrowed causes but did not turn that run into a clean pass.

## 2. Public execution model

CWI creates a private linked Git worktree, freezes the request/configuration/validation/runtime identities, and runs the roles Designer, Architect, Writer, and Reviewer. The Writer changes source; the controller creates and identifies provisional candidates, executes checks, handles bounded repair and clarification, records milestone acceptance, and performs final whole-change validation/review. It can then leave an accepted branch unmerged or apply originally authorized integration.

A project-level phase is not a CWI milestone. The CLI executes the bounded internal roadmap rather than exposing a public pause after every milestone. Use one scoped request per externally meaningful development slice.

| CLI surface | Meaning / constraint |
| --- | --- |
| `start --request FILE` | Required UTF-8 assignment; creates a new run |
| repeated `--check COMMAND` | Explicit validation argv parsed with POSIX quoting; no shell |
| `--context DIR` | Optional bounded UTF-8 reference input; not a general opaque-document ingestion interface |
| `--target BRANCH` | Asserts the currently checked-out target branch; does not switch it |
| `--model`, `--reasoning` | Freeze selection; check actual locally supported values |
| `--max-milestones`, repair ceilings | Bound internal work, not monetary spending by themselves |
| `--agent-timeout`, `--validation-timeout` | Per-invocation ceilings, not total workflow duration guarantees |
| `--merge` | Integration authorization fixed at start |
| `status`, `diagnose`, `reconstruct` | Read-only inspection of the actual persisted run ID |
| `resume RUN_ID` | Conservative reconciliation under frozen identities |

There is no public `--config`, `--state-root`, `pause`, `stop-after-milestone`, `merge RUN_ID`, or cleanup command in the reviewed CLI. Do not invent those interfaces in a coordinator prompt.

`start` and `resume` return zero only for terminal accepted-unmerged/merged success. Inspection commands may return zero for a stopped incomplete run. Interpret fields and retained evidence, not exit code alone. `accepted_head` can still identify the original base in an incomplete run; its presence by itself is not final acceptance.

## 3. Exact nested-clone requirement

The source-launch exception accepts an untracked, real, direct child named `coding_pipeline/`. A folder named `code_pipeline/`, a clone under `tools/`, a symlink, or a tracked submodule is not the supported exception. The launcher finds the parent target; preflight verifies both the embedded checkout and target conditions.

Use local Git common-directory `info/exclude` entries for `/coding_pipeline/` and `/workflow_logs/`. CWI manages those exclusions and preserves existing patterns; the setup adds the separate local observation area. This meets the Markdown-only root requirement without adding a root `.gitignore`. Record the clone's remote and commit because it is not carried by the parent Git history.

The target needs an initial commit, a checked-out local branch, and a clean working tree. Tracked submodules are rejected. Ignored dependencies, environments and the controller clone are not automatically present in the candidate worktree. Do not rely on them being copied.

## 4. Critical integration hazards and their treatment

### 4.1 Recursive delegation

An unqualified root instruction saying “use coding_pipeline for every change” can also be read by its delegated Writer. The supplied `AGENTS.md` therefore distinguishes the outer coordinator from CWI roles before any other workflow rule. The Writer directly implements its prescription; that is already implementation through CWI. It must not launch a second controller, create worktrees or commit changes itself.

CWI's role policy and frozen contract outrank repository task data. This separation is a coordination instruction, not a claim that Markdown itself enforces an OS security boundary.

### 4.2 Dirty-target status updates

CWI binds work to the original branch/base and checks source/target conditions. An outer coordinator committing a status update during the run can break those assumptions. Tracked documentation is therefore committed before launch and after safe integration. Live observations are kept under an already-excluded `local/` area, with retained CWI state as authority.

Do not start a second workflow in the original repository, change branches, update dependencies/controller source, or perform unrelated commits while a run is active or awaiting original-base integration.

### 4.3 Starting from Markdown only

The native automatic test-discovery path does not infer a supported suite from an all-Markdown repository. It also rejects ambiguous/unsupported nested runner configuration. Explicit `--check` overrides automatic discovery and its native test-free execution-count gate.

The setup therefore provides a narrowly scoped bootstrap check. It admits only the exact documentation-only base; every changed candidate must establish the specified package and run real non-skipped tests. The first Writer creates the product validator through CWI. Later runs use that normal validator, never `true`, an absent-test fallback, or a permanent bootstrap exemption.

The exact-base branch also permits a literal no-op at that same source identity, so final D01 acceptance additionally requires a non-baseline source and satisfied implementation criteria. This limitation is explicit rather than hidden behind an apparently universal mechanical gate.

### 4.4 Environment and executable continuity

Preflight hashes the entire inherited environment map. Resume checks that identity, along with the selected Codex executable and other frozen inputs. A harmless-looking PATH, virtualenv, terminal/session variable, or credential change can therefore block continuation. The proposed launch helper starts with a deliberate small environment and requires the same values on resume.

CWI selects the newest stable locally discovered Codex binary, freezes its path/version/content identity, and probes its required command capabilities. It does not install, update, or silently downgrade the CLI. Keep the selected executable and controller source unchanged during an unfinished run. Pinning the controller's own source is an operator discipline; do not assume the Codex-binary check also pins every controller file.

### 4.5 Two layers of permissions

The outer Codex session must be allowed to invoke CWI, manipulate the relevant Git administration through approved commands, and let CWI write its account-state directory and launch its own child transports. A workspace-only outer sandbox may prevent some of those operations. Use specific command approval or a human-operated terminal where required, rather than claiming that a prompt grants permission or recommending blanket unrestricted execution.

CWI itself isolates delegated roles, disables ambient configurations and tool integrations, uses structured response schemas, and grants workspace write only where prescribed. Outer-session plugins, skills, network access, and MCP integrations must not be assumed available to its child agents. Dependencies and references needed for a run should be prepared deliberately before freezing its environment.

### 4.6 Automatic integration and ignored files

Automatic merge is opt-in at the original start. With an embedded checkout or ignored local artifacts, the reviewed gate rejects changes whose basename is `.gitignore`, including a nested `.gitignore`. It also binds merge observations to relevant ignored content. Therefore the initial policy is accepted-unmerged followed by deliberate exact fast-forward integration after review.

Manual integration is not permission to force or bypass a conflict. Inspect the accepted final source, original branch/base, cleanliness, ignored-path collisions, hooks, and complete diff. If you modify/rebase/cherry-pick source, the result is no longer the exact accepted candidate and needs its own validation/review. A manual merge may correctly leave CWI's historical outcome as `ACCEPTED_UNMERGED`.

## 5. Storage, logging and recovery

On Linux the authoritative run root is `<OS-account-home>/.local/state/cwi/runs/<run-id>/`. The OS account database determines the home; changing HOME or XDG_STATE_HOME does not relocate this authority. It contains state/events, immutable evidence, runtime metadata, and the private worktree. Diagnostic logs live under the target's ignored `workflow_logs/<run-id>/`.

Logs are useful observations, not substitutes for recovery state and exact receipts. A normal Git clone carries neither external run state nor ignored controller checkout nor local exclusion configuration. Backup and restart procedures must distinguish these layers and protect any private source/prompt data they contain.

CWI uses repository coordination and conservative in-flight recovery. Some uncertain operations stop under quarantine rather than being replayed. Follow its diagnosed recovery action; do not delete leases, rewrite snapshots, reset worktrees or remove quarantine because an outer session timed out. An interrupted subprocess may still have descendants or effects.

## 6. Component map and source anchors

Line references below are for this snapshot only; verify them after any update. The full inventory also covers support modules, packaging, CI, benchmarks and tests.

| Concern | Primary source anchors |
| --- | --- |
| Operating contract | `README.md`: 44–200 prerequisites/discovery; 278–421 start/merge/state/recovery/trust |
| Source launch and CLI | `bin/agentic-flow`; `cwi/cli.py`: `build_parser`, `main` |
| Target/clone constraints | `cwi/preflight.py`: 625–695, including `_embedded_checkout` |
| Exact environment continuity | `cwi/preflight.py`: 168–172, 376–382, `_environment_digest` |
| Fixed account-state path | `cwi/preflight.py`: `_fixed_state_root`; `cwi/state_store.py` |
| Validation discovery/bootstrap | `cwi/test_discovery.py`: 48–113; `cwi/test_execution.py`; `cwi/validation.py` |
| Runtime selection and isolation | `cwi/codex_runtime.py`; `cwi/codex_cli.py`: `_command`, compatibility checks |
| Start/report/resume | `cwi/orchestration.py`: `StatusReport`, `start`, `status`, `resume` |
| Roles and frozen context | `cwi/context.py`; all `cwi/prompts/` files; `cwi/response_schemas.py` |
| Milestone source and acceptance | `cwi/controller.py`: 589–723; `cwi/milestone.py`; `cwi/repair.py` |
| Whole-change acceptance | `cwi/finalization.py`: 39–183, 289–329 |
| Git and ignore collision rules | `cwi/git_workspace.py`: 1433–1475 and surrounding merge logic |
| Diagnostic versus authority | `cwi/diagnostics.py`; `cwi/reconstruction.py`; logging modules; `cwi/state_store.py` |

## 7. Local readiness gate

Before the first real product run, verify the exact clone revision, Python/Git requirements, the selected Codex CLI's required flags and authenticated operation, known backend test findings, stable environment, approved execution permissions, and baseline checker behavior. Do not label this step complete merely because `agentic-flow --help` prints usage.

The reviewed controller runtime requires Python 3.11+ and no third-party Python runtime library, but packaging tests and optional pytest paths have additional environment needs. Linux is the supplied project's verified target; Windows support is not claimed and macOS is not verified by this review. A local reproducible unresolved backend failure must be reported, not silently ignored. If maintenance is needed, keep it a separate authorized change in the backend repository and re-pin the assessed revision before starting new research-product work.

## 8. Official Codex references

These references were checked on 2026-10-29; the installed CLI's own help and CWI capability probes still determine actual local compatibility.

- [AGENTS.md instructions](https://developers.openai.com/codex/guides/agents-md): project instruction discovery; root instructions should stay concise and explicitly direct reading of larger documents.
- [CLI reference](https://developers.openai.com/codex/cli/reference): interactive sandbox/approval flags and command interfaces.
- [Running Codex safely](https://openai.com/index/running-codex-safely/): separation of approval and execution boundaries.

These official sources describe Codex. Claims about CWI above come from the supplied repository, not from the OpenAI documentation.
