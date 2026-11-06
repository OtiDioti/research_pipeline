# Local setup and CWI runbook

Provides setup and operational commands for authorized CWI work, including current role-specific flags and exact integration controls.

This runbook describes the current role-specific launch contract. The supplied-snapshot review and historical run records retain their original contract. Confirm the [review](PIPELINE_REVIEW.md), your actual clone revision, and `start --help` before using a materially different version. Replace the repository URL placeholders; do not execute them literally. Continuous progression, authority, model selection, and focused backend repair are defined in [AUTONOMY.md](AUTONOMY.md), [AUTHORIZATION.md](AUTHORIZATION.md), [MODEL_POLICY.md](MODEL_POLICY.md), and [BACKEND_MAINTENANCE.md](BACKEND_MAINTENANCE.md).

## 1. Install the documentation without losing the specification

For a new repository, clone the target project normally and copy the documentation kit into that root. For an already-started repository, follow [UPDATE_GUIDE.md](UPDATE_GUIDE.md) instead; do not overwrite its progress records or apply this update during a live/base-bound run. The kit intentionally contains no `project_description.md`; keep your existing file. Its README is intended to replace the currently empty README, not overwrite later custom material indiscriminately.

Confirm the root contains Markdown and directories only, plus Git's administrative entry. Do not create a root packaging manifest or root `.gitignore`.

## 2. Establish local exclusions before cloning the backend

Run this from the target root, while no CWI run is active:

```bash
python3 - <<'PY'
from pathlib import Path
import subprocess

# Git supplies the correct local exclude path, including linked-worktree cases.
path = Path(subprocess.check_output(
    ['git', 'rev-parse', '--git-path', 'info/exclude'], text=True
).strip())
path.parent.mkdir(parents=True, exist_ok=True)
existing = path.read_text(encoding='utf-8') if path.exists() else ''
rules = ['/coding_pipeline/', '/workflow_logs/', '/local/*',
         '!/local/README.md', '/.obsidian/']
missing = [rule for rule in rules if rule not in existing.splitlines()]
if missing:
    separator = '' if not existing or existing.endswith('\n') else '\n'
    path.write_text(existing + separator + '\n'.join(missing) + '\n',
                    encoding='utf-8')
PY
```

This modifies local Git administration, not tracked source. It preserves existing rules and keeps the local README trackable. CWI independently manages its required controller/log exclusions at startup; the explicit preparation prevents an accidental `git add` of the nested clone before the first run.

```bash
git clone YOUR_CODING_PIPELINE_REPOSITORY_URL coding_pipeline
git -C coding_pipeline rev-parse HEAD
git -C coding_pipeline status --short
./coding_pipeline/bin/agentic-flow --help
./coding_pipeline/bin/agentic-flow start --help
```

Use `coding_pipeline` as the local directory name. Do not use a submodule, symlink, `tools/coding_pipeline`, or a tracked vendored copy. The reviewed source launcher specifically recognizes its real direct-child checkout.

## 3. Prepare the environment

Use Python 3.11+, a capable Git, and an authenticated compatible Codex CLI. The supplied backend verifies Linux; do not assume its macOS or Windows behavior was tested here.

```bash
python3 --version
git --version
git worktree list --porcelain -z >/dev/null
codex --version
codex login status
```

Run `codex login` normally if authentication is absent. CWI's own compatibility probe is the authority for its additional required flags; a working interactive Codex session does not by itself establish CWI compatibility.

Configure Git identity if not already set. Install product/build/test dependencies before starting CWI. Its private worktree does not automatically contain your ignored `.venv` or other installation folders. An absolute environment interpreter is usable from the worktree, but an editable installation pointing at the original source can make tests misleading; the product validator must explicitly use current-worktree source.

For backend verification, the README's development command is:

```bash
(cd coding_pipeline && PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v)
```

Packaging tests also need the documented build prerequisites available in that environment. See [TEST_RESULTS.md](review/TEST_RESULTS.md) for the supplied-snapshot findings, including Codex-fixture prerequisites, one-second session deadlines, and a pytest virtual-environment fixture issue. Do not relabel an unexplained failure as a pass. Authenticated integrations are separately opt-in.

## 4. Define a stable launch environment

The following is a shell helper, not a product implementation or a tracked script. Recreate it with the same values on resume. Record the non-secret choices in [ENVIRONMENT.md](ENVIRONMENT.md) and retain private paths locally.

```bash
# Define once from the target root, after activating the intended Python environment.
CWI_ROOT="$PWD"
CWI_HOME="$HOME"
CWI_PATH="$PATH"
CWI_CODEX_HOME="${CODEX_HOME:-$HOME/.codex}"

cwi() {
    env -i \
        HOME="$CWI_HOME" \
        PATH="$CWI_PATH" \
        CODEX_HOME="$CWI_CODEX_HOME" \
        LANG=C.UTF-8 LC_ALL=C.UTF-8 TERM=dumb \
        PYTHONDONTWRITEBYTECODE=1 \
        "$CWI_ROOT/coding_pipeline/bin/agentic-flow" "$@"
}
```

Keep the working directory at `CWI_ROOT` for `start`. Restore the same root, PATH, HOME, and CODEX_HOME values on resume. `env -i` avoids unrelated changing Codex-session variables being included in CWI's exact launch-environment digest. This Linux-oriented example may need fixed certificate/proxy or other required variables in a particular installation; review those needs, add them explicitly, and preserve them unchanged. Do not publish secret values.

`TERM=dumb` deliberately disables terminal animation; JSON status and logs remain available. An approved trusted command execution may be required when launching this helper from outer Codex, because CWI manages Git and writes outside the project into its account-state root. Do not use a blanket sandbox bypass.

## 4.1. Verify all four role selections before launch

Follow [MODEL_POLICY.md](MODEL_POLICY.md). The 2026-11-04 human amendment approves Designer `gpt-6-astra` / `xhigh`, Architect `gpt-6.1-sol` / `xhigh`, Writer `gpt-6.1-sol` / `high`, and Reviewer `gpt-6.1-sol` / `high`. Verify the actual selected Codex executable, account access, both model identifiers and supported efforts before any new model-dependent run. If a selection is unavailable, stop and report the blocker; do not substitute a model, effort or global default.

Every new start must pass all eight role flags shown below. No model-selection environment variables are required. Keep the recorded launch map unchanged. Child configuration is isolated; setting the outer Codex model is insufficient. All four selections freeze in schema-revision-2 state and remain immutable on resume. No revision-1 migration or automatic historical resume is authorized; retain the original backend revision for read-only historical inspection.

The launch examples are templates for new, unfrozen requests after readiness and authority checks. Do not relaunch the historical commissioning request or reuse a frozen request's old model envelope. The 2026-11-04 maintenance session ended at its documented checkpoint without starting product development; later sessions follow their current human instructions and recorded grant.

Apply the replacement/removal and CWI review-delegation boundaries in [AGENTS.md](../AGENTS.md) §2 while following these operational steps. The runbook supplies commands and checks, not a second copy of the standing coordinator policy.

## 5. Commit the prelaunch state

Complete D00, confirm the bootstrap request, and update STATUS to the intended first run. Stage explicit paths, not the embedded clone:

```bash
git add README.md project_description.md AGENTS.md DEVELOPMENT.md ROADMAP.md \
  STATUS.md BACKLOG.md DECISIONS.md CHANGELOG.md coding_pipeline_changes.md development implementation/README.md \
  docs/README.md examples/README.md local/README.md
git diff --cached --stat
git commit -m "docs: establish controlled development workflow"
git status --porcelain
```

The last command must produce no unexpected changes. Existing tracked files are preserved; inspect the staged administrative Markdown diff before committing. Do not use `git add .` as a shortcut around exclusion mistakes.

Create a local attempt directory **before** starting. The local attempt label is not the future CWI run ID:

```bash
ATTEMPT_DIR="local/attempts/D01-001"
mkdir -p "$ATTEMPT_DIR"
```

Use a fresh attempt directory rather than overwriting prior reports. Ensure it is already ignored with `git check-ignore "$ATTEMPT_DIR/"`.

## 6. Launch the first implementation run

Follow [BOOTSTRAP.md](BOOTSTRAP.md), which constructs `BOOTSTRAP_CHECK` without placing executable source in the target. Then:

```bash
if cwi start \
  --request development/requests/REQ-D01-001.md \
  --check "$BOOTSTRAP_CHECK" \
  --designer-model gpt-6-astra \
  --designer-reasoning xhigh \
  --architect-model gpt-6.1-sol \
  --architect-reasoning xhigh \
  --writer-model gpt-6.1-sol \
  --writer-reasoning high \
  --reviewer-model gpt-6.1-sol \
  --reviewer-reasoning high \
  --max-milestones 1 \
  --max-repairs-per-review 2 \
  --max-repairs-per-run 6 \
  --agent-timeout 2700 \
  --validation-timeout 2700 \
  > "$ATTEMPT_DIR/start-report.json" \
  2> "$ATTEMPT_DIR/start-stderr.log"
then
  RUN_EXIT=0
else
  RUN_EXIT=$?
fi
printf 'CWI command exit: %s\n' "$RUN_EXIT"
```

The timeouts are proposed per-invocation ceilings, not estimates or monetary caps. Choose them within your operating envelope before starting. All four approved role selections must be verified and explicitly supplied; each pair is frozen for this run. Do not add `--merge`; the default workflow integrates through the coordinator after inspection. The commissioning prompt allows at most three start attempts of this same request, with a diagnosed correction and safe disposition before replacement; it does not allow three competing runs or blind retries.

CWI is synchronous. A supervising tool's shorter timeout must not repeatedly kill and restart it. Keep ownership and the run ID recoverable; do not launch another run while the first may be active.

`start` prints a final JSON report when it can. A failed preflight may create no run; a killed process may leave no complete final report. Recover the exact run ID from retained local observations, CWI logs/state, and their source/request identities; do not simply assume the newest unrelated directory is your run.

## 7. Inspect the exact run

Use the backend revision compatible with the retained run's schema. Revision-1 historical inspection uses the preserved original backend, not the modernized revision-2 loader; neither route authorizes automatic resume. Keep the recorded source/environment identities intact.

```bash
RUN_ID='THE_ACTUAL_CWI_UUID'
cwi status "$RUN_ID" > "$ATTEMPT_DIR/status.json"
cwi diagnose "$RUN_ID" > "$ATTEMPT_DIR/diagnosis.txt"
cwi reconstruct "$RUN_ID" --json > "$ATTEMPT_DIR/reconstruction.json"
```

These inspection commands do not invoke agents or repair state. Their exit code says whether inspection succeeded, not whether the workflow completed. Read `phase`, `outcome`, `accepted_head`, `provisional_source`, `final_receipt_path`, findings, and recovery guidance.

The Linux authoritative directory is `<OS-account-home>/.local/state/cwi/runs/<run-id>/`, including state, events, immutable artifacts, and the private worktree. The OS account database determines this home. Changing HOME or XDG_STATE_HOME does not relocate it. There is no public `--state-root` option.

Logs are in `workflow_logs/<run-id>/` in the original checkout. Preserve both evidence layers when making a protected backup; logs alone cannot resume a run. A normal Git clone does not transfer the external run database or automatically recreate local exclusions and the nested controller.

## 8. Integrate an accepted result

The default result is `ACCEPTED_UNMERGED`. Verify final acceptance evidence, completed criterion assessments and CWI’s complete-diff review against the exact accepted commit/tree. Check task understanding through Designer outputs; consult Architect outputs only when necessary. Do not routinely reread Writer code, tests or substantive diffs. Do not merge a provisional candidate, a partially accepted run, or a branch selected merely by its name.

After human authorization for the first integration (or an explicit first-run preauthorization), obtain `base_commit` and `accepted_head` from the inspected report. Later integrations use the already-recorded continuous grant when applicable, without a new human prompt. If approval is new while the target remains at the bound base, capture it locally first; do not commit tracked authorization before integrating. Confirm the original checkout is still on the recorded branch, clean, and at the recorded base. Use those actual hashes in the commands below:

```bash
# Fill these only from inspected final evidence and the applicable integration grant.
BASE_COMMIT='RECORDED_BASE_COMMIT'
ACCEPTED_COMMIT='EXACT_FINALLY_ACCEPTED_COMMIT'
TARGET_BRANCH='RECORDED_TARGET_BRANCH'
(
  # Abort this entire integration block at its first failed precondition.
  set -eu
  test "$(git symbolic-ref --quiet --short HEAD)" = "$TARGET_BRANCH"
  test "$(git rev-parse HEAD)" = "$BASE_COMMIT"
  test -z "$(git status --porcelain)"
  # The first foundation must not be a no-op at the documentation baseline.
  test "$ACCEPTED_COMMIT" != "$BASE_COMMIT"
  git diff --check "$BASE_COMMIT" "$ACCEPTED_COMMIT"
  git diff --stat "$BASE_COMMIT" "$ACCEPTED_COMMIT"
  # Verify the receipt, exact Git identities and bound CWI complete-diff review evidence first.
  # The mechanical formatting/stat checks above support integration safety, not code review.
  git merge --ff-only "$ACCEPTED_COMMIT"
  test "$(git rev-parse HEAD)" = "$ACCEPTED_COMMIT"
  test -z "$(git status --porcelain)"
)
```

Stop if any precondition fails; do not force, reset, rebase, or cherry-pick merely to fit the command. Review locally configured Git hooks and any ignored-path collision before integration. If manual integration changes content, the new source is not the exact accepted candidate and needs separate validation/review.

Run the required documented read-only post-integration validator without additional routine reruns of successful CWI checks, then create the run record and post-integration documentation checkpoint. Record any newly issued grant at that checkpoint, together with consumed allowances and the next action. A failed post-integration check is a real defect to diagnose, not permission for a forced reset or a false completion statement. Its new commit may follow the accepted implementation commit; retain both identities. CWI's historical state can correctly remain `ACCEPTED_UNMERGED` after an external manual merge. Do not edit its receipt or state to make it say `MERGED`.

CWI can merge automatically only when `--merge` was authorized in the original start command. Its automatic gate rejects changes to any `.gitignore` while ignored local artifacts/the embedded clone are present. This includes nested `.gitignore` files. Manual integration is therefore the clearer initial policy; it still requires collision and source checks. Do not keep changing local live files across an automatically controlled merge, whose pre-state binds ignored content too.

## 9. Subsequent implementation runs

After D01 has actually established and validated the normal check, use a fresh bounded request and a clean prelaunch commit. Under a continuous grant, repeat this process across ready requirements and phases without routine approval pauses. Verify and pass the four approved role selections before each run and retain them unchanged on resume. Count start attempts before execution and retain final output in a fresh ignored attempt directory as for bootstrap. Example:

```bash
cwi start \
  --request development/requests/REQ-Dxx-nnn.md \
  --check 'python3 -B implementation/scripts/validate.py' \
  --designer-model gpt-6-astra \
  --designer-reasoning xhigh \
  --architect-model gpt-6.1-sol \
  --architect-reasoning xhigh \
  --writer-model gpt-6.1-sol \
  --writer-reasoning high \
  --reviewer-model gpt-6.1-sol \
  --reviewer-reasoning high \
  --max-milestones 2 \
  --max-repairs-per-review 2 \
  --max-repairs-per-run 6 \
  --agent-timeout 2700 \
  --validation-timeout 2700
```

`REQ-Dxx-nnn.md` is a placeholder for a new committed bounded request, not a ready request. CWI must not be invoked against a nonexistent request or validator. The validation command resolves `python3` through the deliberately frozen PATH; an explicitly quoted absolute interpreter is also valid.

All checks run from the worktree root and are parsed into argv without a shell. `--check 'cd implementation && pytest'` is not a supported way to change directory. Use a real validation entry point or Python's explicit arguments instead. Supplying `--check` bypasses automatic runner selection and its native test-free execution-count requirement.

Do not pass a public `--config`: this CLI has none. It generates its own frozen configuration. `--target` asserts the already-checked-out branch; it does not switch it. There is no `pause`, `stop-after-milestone`, `merge RUN_ID`, or cleanup command in the reviewed CLI. Use bounded requests for human-visible stopping boundaries.

## 10. Resume, pause, and changed plans

```bash
cwi status "$RUN_ID"
cwi diagnose "$RUN_ID"
# Only for a revision-2 run when diagnosis permits and its exact environment/backend is restored:
cwi resume "$RUN_ID"
```

Never turn a failed check into a new `start` loop. Resume uses frozen request/context/checks and all four role selections, and verifies the launch environment and executable identity. Revision-1 state is not migrated; use the preserved original backend revision for historical inspection, without automatically resuming old runs. To change these, first resolve the previous run safely and prepare a new request.

Follow `wait_for_controller`, `manual_quarantine_intervention`, or `new_run_after_manual_salvage` literally. A missing PID does not prove all descendants or external effects ended. Never delete a live lease, blindly remove quarantine, rewrite snapshots, or reset managed worktrees.

When stopping the outer session while CWI remains active, keep the original checkout unchanged and leave the run ID plus next inspection action in the ignored local handoff. Once a safe boundary exists, reconcile the tracked checkpoint.

## 11. Starting Codex

From the repository root:

```bash
codex --sandbox workspace-write --ask-for-approval on-request
```

For this commissioned repository, use the [continuation prompt](CODEX_START.md) after explicit human resumption. A genuinely unstarted repository uses the [commissioning form](templates/COMMISSIONING.md). The outer agent will load root `AGENTS.md`; it should also explicitly read the operating documents named there. Delegated CWI agents follow their frozen role context and must not recursively call the pipeline.

Current OpenAI documentation describes `AGENTS.md` instruction discovery and separates sandbox permissions from approval policy. A repository instruction is guidance, not a filesystem security boundary. See the official-source references in [the review](PIPELINE_REVIEW.md).

## 12. Continuous operation, focused repairs, and final handoff

For first-time use, select the separate [commissioning](templates/COMMISSIONING.md) and [activation](templates/ACTIVATION.md) forms; actual human grants are recorded separately and linked from [AUTHORIZATION.md](AUTHORIZATION.md). For an existing active grant, use [continuation](CODEX_START.md), preserving all consumption and stop instructions. That grant permits repeated requests and coordinator-controlled exact integrations; it does not remove receipt/diff/checkpoint gates or grant new OS permissions.

Once a request is integrated and its administrative checkpoint is committed, continue immediately if authorized work is ready. Refresh requirement coverage at phase boundaries; do not treat reaching one as an automatic stop. Counters survive new sessions. Preserve a single writer/coordinator owner and reconcile current CWI state before another session takes over.

For a demonstrated backend failure, use [BACKEND_MAINTENANCE.md](BACKEND_MAINTENANCE.md). The top-level coordinator may make a narrow, tested backend-source repair under the user's exception. It must not edit a running controller, invalidate a frozen run silently, loosen a guard, or implement research-product code directly. Keep pending audit material local until parent changes are safe, then update [the root audit](../coding_pipeline_changes.md).

The kit supplies no background supervisor. A manual continuation prompt can resume the same grant after session limits. Automated session renewal is a separately implemented/tested feature, not a shell loop that blindly restarts on exit zero.

Finish against the completion gate in [AUTONOMY.md](AUTONOMY.md). Report partial implementation, pending live-provider evidence, and required scientific/human review separately. A declared hold always includes the exact preserved state and one next safe action.

Current deadline authority: AUTH revision 5 explicitly permits 2,700 seconds per agent and per validation for newly frozen runs. Earlier 900-second runs remain unchanged and cannot be silently resumed under new settings. This does not reset attempts or other resource counters.

## Recorded descriptor prerequisite for current product validation

From the REQ-D03-001 integration checkpoint, launch new CWI and validation processes with `RLIMIT_NOFILE` soft=4096 within the existing hard limit (observed 1048576). Inspect the limits first; in the launch-only shell, `ulimit -Sn 4096` sets the process soft limit and its children inherit it. Do not change system configuration, an existing live process or frozen-run launch conditions. If the hard limit cannot support this prerequisite, record the resource blocker instead of skipping the 1024-file test. Retain the resource setting alongside the stable non-secret environment map. The request still uses the unchanged `python3 -B implementation/scripts/validate.py` check; all tests execute. Historical runs without a recorded descriptor limit retain that uncertainty.

## REQ-D03-002 formatting observation

The coordinator recorded one exact nonsemantic terminal empty line in a new test as nonblocking cosmetic debt while preserving the finally accepted source; DEV-036 and its run evidence bind the specific diagnostic/hash and AST check. This does not authorize ignoring other failed checks. REQ-D03-003 delegates removal to its Writer. Future requests must inspect git diff --check against the complete committed request-base-to-candidate range, including newly added files; working-tree-only checks can miss new-file formatting. Capture test/example input directories must explicitly satisfy existing owner-only safety requirements without changing launch umask or production guards.

## Project-intake checkpoint and explicit synthetic input permissions

REQ-D03-003's Writer removed the exact earlier test_corpus.py terminal empty line; its complete base-to-candidate diff check passes. DEV-036/B-015 is resolved, with no general formatting exception. Continue complete-diff checks including new files.

For synthetic capture tests/examples, explicitly use private directories0700 and files0600, plus available supplied_local provenance/exact locator for each selected file, including supplied extraction outputs. Do not rely on inherited umask or copied partial provenance. Existing security guards and original-versus-derived distinctions stay intact. Writer sandbox failures do not excuse actual controller fixture defects; retain both evidence layers.

## Bind the required complete-diff result — DEV-039

For future requests requiring complete-base formatting, pass a second explicit --check alongside the permanent validator: `git diff --check ACTUAL_COMMITTED_LAUNCH_BASE HEAD --`, substituting the exact launch-base SHA before start. CWI parses argv without a shell. The whole committed range includes new files, and check-2 must appear in frozen baseline/candidate/final results. The coordinator verifies this bound formatting result and the complete-diff review evidence; routine substantive diff inspection is not required. Neither integration checks nor review evidence can substitute for a controller-bound criterion. The formatting check supplements meaningful test execution; it never replaces it. Do not alter a live profile or the permanent validator to retrofit evidence.

REQ-D03-004 demonstrates the terminal missing-check case. After verified owner/lease/quarantine resolution, preserve exact unaccepted CWI Writer output under ignored local context with hashes, prepare a new bounded request and use supported --context. Only the new delegated Writer may reuse/modify the draft in its assigned worktree. Never merge/transplant unaccepted source, rewrite old receipts/state, or resume a run whose diagnosis forbids it. Count the original failed start, its repairs and the distinct recovery across sessions.


## Salvage references and combined role-prompt limits

The supported --context input aggregate allowance is distinct from the assembled role-prompt budget. Repeating full retained source bodies beside the mandatory complete candidate diff can exceed the review limit even when preflight accepts each input. R2/ b63e2b5e demonstrated this at1,497,360bytes against1MiB; R3 resolved it without backend changes.

When a preserved candidate already exists in local Git objects, freeze a compact exact commit/tree/per-path blob/mode/length/SHA-256 manifest plus essential recovery notes. Verify object availability before launch. Only the new delegated Writer installs those verified bytes into its assigned worktree after prescription, using read-only immutable Git-object extraction. Never substitute a mutable branch tip, copy from an old mutable working tree, transplant unaccepted source into the parent, or manipulate refs/index to bypass CWI.

Where retained complete review evidence is available, measure the actual proposed request/context with the unchanged read-only prompt composer and retain margin for final receipts/findings. Do not save altered controller state, raise guards, truncate mandatory diff/evidence or modify a live run to fit. R3 actual milestone/final prompts596043/591401bytes retained all required evidence and passed both reviews.

## Current aggregate start allowance — AUTHrevision6, 2026-11-03

The human increased continuous CWI start attempts to100. Read AUTHORIZATION.md for the actual grant and STATUS.md for consumed/remaining counts; failed preflights/replacements count and session renewal resets nothing. This is a coordinator allowance, not a CWI CLI/configuration flag. Do not change max-milestones/max-repairs to represent it. Startup prompts and autonomy settings now use100; old frozen launch records keep their historical50 denominator. All other current limits/permissions remain unchanged.


## Concurrent full validation and targeted extra review — integrated 2026-11-03

Keep the existing permanent full-check command and complete committed-base diff check. The product validator automatically discovers existing/future standard unittest modules and derives fixture-safe groups; no manual worker list or selective required-test filter. Effective affinity/quota/cpuset capacity is sampled for each drained wave: `C=min(T//2,max(0,A-2))`, concurrency at most2*C, and C0 uses intact sequential execution. Child-only CPU masks preserve parent/machine settings. Exceptional shared dependencies and pending/unknown process-global module cleanups choose conservative exclusive traversal; opaque or inconsistent execution fails validation. See [validator guide](../docs/test-validation.md) for metadata, Linux/fresh-process limits, exact accounting, cleanup and failure behavior.

Run the full permanent validator after authorized exact integration, under the existing stable launch map, FD4096 and2700s/16MiB bounds. Do not run an editable original installation from a candidate worktree. A comparison with `python3 -B implementation/scripts/validate.py --sequential` still runs every discovered test; compare exact inventories/dispositions and equivalent environments before claiming acceleration. No successful-result cache, replay after uncertain side effects, limit expansion or detached execution. [Recorded benchmark](benchmarks/concurrent-validation-20261103.md) includes CPU/memory/startup costs and the practical limits of sampled measurements.

Backendb6a2e052 changes only Reviewer prompt policy: use current bound full controller results; run additional diagnostics only when necessary and permitted for affected behavior/callers/dependencies/helpers/fixtures/findings. The Reviewer does not rerun the complete suite/full-suite command. This does not remove or filter any mandatory controller baseline/candidate/final or target check, reduce final-diff review, or create new validation IDs. Preserve failures/inadequate evidence via normal repair/stop. Clarification remains non-executing. Before a future launch recover the clean backend identity, exact Codex/model/effort, environment and actual run ownership; never silently resume an old frozen run under changed backend code. [CP-002 audit/patch](../coding_pipeline_changes.md).

This human-priority optimization/prompt follow-up ends at the final documented safe checkpoint. Do not initiate an unrelated request this session. Recover STATUS, local/live.md and actual Git/CWI evidence in a new session before preparing the next ready scope; no installed automatic restart supervisor is implied.
