# Local setup and CWI runbook

This runbook targets the supplied controller snapshot. Confirm the [review](PIPELINE_REVIEW.md), your actual clone revision, and `start --help` before using a materially different version. Replace the repository URL placeholders; do not execute them literally. Continuous progression, authority, model selection, and focused backend repair are defined in [AUTONOMY.md](AUTONOMY.md), [AUTHORIZATION.md](AUTHORIZATION.md), [MODEL_POLICY.md](MODEL_POLICY.md), and [BACKEND_MAINTENANCE.md](BACKEND_MAINTENANCE.md).

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

## 4.1. Resolve the development model and reasoning before launch

Follow [MODEL_POLICY.md](MODEL_POLICY.md). The requested display name is Astra 6.1; the official catalog checked for this update did not establish that exact identifier. Inspect local account/provider evidence and get an explicit correction if required. Do not put an invented model slug into the command or silently select another model.

Set `CWI_MODEL` to the **verified** exact identifier, and `CWI_REASONING` to the supported chosen value before using either launch example. Do not export these new variables into an existing frozen environment. The following check is an operator shell guard, not an installed product feature:

```bash
: "${CWI_MODEL:?Set the verified, authorized exact model ID first}"
: "${CWI_REASONING:?Choose an explicitly supported effort first}"
case "$CWI_REASONING" in
  low|medium|high|xhigh) ;;
  *) printf 'Reasoning effort must be supported and no higher than xhigh.\n' >&2; exit 1 ;;
esac
```

The allow-list enforces this policy's ceiling, not provider availability; verify that separately. Run it in the same launching shell (or an abort-on-failure launch block), and do not continue after failure. Use explicit flags below for every start. CWI's child configuration is isolated; merely setting the outer Codex model is insufficient. Resume uses its frozen values and has no model-override option.

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

The last command must produce no unexpected changes. Existing tracked files are preserved; inspect the staged diff before committing. Do not use `git add .` as a shortcut around exclusion mistakes.

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
  --model "${CWI_MODEL:?verified model required}" \
  --reasoning "${CWI_REASONING:?explicit supported effort required}" \
  --max-milestones 1 \
  --max-repairs-per-review 2 \
  --max-repairs-per-run 6 \
  --agent-timeout 900 \
  --validation-timeout 900 \
  > "$ATTEMPT_DIR/start-report.json" \
  2> "$ATTEMPT_DIR/start-stderr.log"
then
  RUN_EXIT=0
else
  RUN_EXIT=$?
fi
printf 'CWI command exit: %s\n' "$RUN_EXIT"
```

The timeouts are proposed per-invocation ceilings, not estimates or monetary caps. Choose them within your operating envelope before starting. Explicit model/effort resolution is required, and one pair is frozen for all roles in this run. Do not add `--merge`; the default workflow integrates through the coordinator after inspection. The commissioning prompt allows at most three start attempts of this same request, with a diagnosed correction and safe disposition before replacement; it does not allow three competing runs or blind retries.

CWI is synchronous. A supervising tool's shorter timeout must not repeatedly kill and restart it. Keep ownership and the run ID recoverable; do not launch another run while the first may be active.

`start` prints a final JSON report when it can. A failed preflight may create no run; a killed process may leave no complete final report. Recover the exact run ID from retained local observations, CWI logs/state, and their source/request identities; do not simply assume the newest unrelated directory is your run.

## 7. Inspect the exact run

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

The default result is `ACCEPTED_UNMERGED`. Inspect the final acceptance evidence and complete diff. Do not merge a provisional candidate, a partially accepted run, or a branch selected merely by its name.

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
  # The substantive diff and receipt must already have been inspected.
  git merge --ff-only "$ACCEPTED_COMMIT"
  test "$(git rev-parse HEAD)" = "$ACCEPTED_COMMIT"
  test -z "$(git status --porcelain)"
)
```

Stop if any precondition fails; do not force, reset, rebase, or cherry-pick merely to fit the command. Review locally configured Git hooks and any ignored-path collision before integration. If manual integration changes content, the new source is not the exact accepted candidate and needs separate validation/review.

Run the documented read-only post-integration validator, then create the run record and post-integration documentation checkpoint. Record any newly issued grant at that checkpoint, together with consumed allowances and the next action. A failed post-integration check is a real defect to diagnose, not permission for a forced reset or a false completion statement. Its new commit may follow the accepted implementation commit; retain both identities. CWI's historical state can correctly remain `ACCEPTED_UNMERGED` after an external manual merge. Do not edit its receipt or state to make it say `MERGED`.

CWI can merge automatically only when `--merge` was authorized in the original start command. Its automatic gate rejects changes to any `.gitignore` while ignored local artifacts/the embedded clone are present. This includes nested `.gitignore` files. Manual integration is therefore the clearer initial policy; it still requires collision and source checks. Do not keep changing local live files across an automatically controlled merge, whose pre-state binds ignored content too.

## 9. Subsequent implementation runs

After D01 has actually established and validated the normal check, use a fresh bounded request and a clean prelaunch commit. Under a continuous grant, repeat this process across ready requirements and phases without routine approval pauses. Choose effort before each run and retain it unchanged on resume. Count start attempts before execution and retain final output in a fresh ignored attempt directory as for bootstrap. Example:

```bash
cwi start \
  --request development/requests/REQ-D02-001.md \
  --check 'python3 -B implementation/scripts/validate.py' \
  --model "${CWI_MODEL:?verified model required}" \
  --reasoning "${CWI_REASONING:?explicit supported effort required}" \
  --max-milestones 2 \
  --max-repairs-per-review 2 \
  --max-repairs-per-run 6 \
  --agent-timeout 900 \
  --validation-timeout 900
```

`REQ-D02-001.md` is a future request, not supplied or ready yet. CWI must not be invoked against a nonexistent request or validator. The validation command resolves `python3` through the deliberately frozen PATH; an explicitly quoted absolute interpreter is also valid.

All checks run from the worktree root and are parsed into argv without a shell. `--check 'cd implementation && pytest'` is not a supported way to change directory. Use a real validation entry point or Python's explicit arguments instead. Supplying `--check` bypasses automatic runner selection and its native test-free execution-count requirement.

Do not pass a public `--config`: this CLI has none. It generates its own frozen configuration. `--target` asserts the already-checked-out branch; it does not switch it. There is no `pause`, `stop-after-milestone`, `merge RUN_ID`, or cleanup command in the reviewed CLI. Use bounded requests for human-visible stopping boundaries.

## 10. Resume, pause, and changed plans

```bash
cwi status "$RUN_ID"
cwi diagnose "$RUN_ID"
# Only when diagnosis permits and the original environment/installation is restored:
cwi resume "$RUN_ID"
```

Never turn a failed check into a new `start` loop. Resume uses frozen request/context/checks and verifies the launch environment and executable identity. To change these, first resolve the previous run safely and prepare a new request.

Follow `wait_for_controller`, `manual_quarantine_intervention`, or `new_run_after_manual_salvage` literally. A missing PID does not prove all descendants or external effects ended. Never delete a live lease, blindly remove quarantine, rewrite snapshots, or reset managed worktrees.

When stopping the outer session while CWI remains active, keep the original checkout unchanged and leave the run ID plus next inspection action in the ignored local handoff. Once a safe boundary exists, reconcile the tracked checkpoint.

## 11. Starting Codex

From the repository root:

```bash
codex --sandbox workspace-write --ask-for-approval on-request
```

Paste the [startup prompt](CODEX_START.md). The outer agent will load root `AGENTS.md`; it should also explicitly read the operating documents named there. Delegated CWI agents follow their frozen role context and must not recursively call the pipeline.

Current OpenAI documentation describes `AGENTS.md` instruction discovery and separates sandbox permissions from approval policy. A repository instruction is guidance, not a filesystem security boundary. See the official-source references in [the review](PIPELINE_REVIEW.md).

## 12. Continuous operation, focused repairs, and final handoff

Use the commissioning and activation prompts in [CODEX_START.md](CODEX_START.md), with the actual grant captured in [AUTHORIZATION.md](AUTHORIZATION.md). That grant permits repeated requests and coordinator-controlled exact integrations; it does not remove receipt/diff/checkpoint gates or grant new OS permissions.

Once a request is integrated and its administrative checkpoint is committed, continue immediately if authorized work is ready. Refresh requirement coverage at phase boundaries; do not treat reaching one as an automatic stop. Counters survive new sessions. Preserve a single writer/coordinator owner and reconcile current CWI state before another session takes over.

For a demonstrated backend failure, use [BACKEND_MAINTENANCE.md](BACKEND_MAINTENANCE.md). The top-level coordinator may make a narrow, tested backend-source repair under the user's exception. It must not edit a running controller, invalidate a frozen run silently, loosen a guard, or implement research-product code directly. Keep pending audit material local until parent changes are safe, then update [the root audit](../coding_pipeline_changes.md).

The kit supplies no background supervisor. A manual continuation prompt can resume the same grant after session limits. Automated session renewal is a separately implemented/tested feature, not a shell loop that blindly restarts on exit zero.

Finish against the completion gate in [AUTONOMY.md](AUTONOMY.md). Report partial implementation, pending live-provider evidence, and required scientific/human review separately. A declared hold always includes the exact preserved state and one next safe action.
