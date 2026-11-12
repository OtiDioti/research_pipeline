# V0-L2 measured context continuity

Implemented in pipeline run `20261112T214235_70d09e50`, milestone 001. Independent
review, trusted final/combined native verification and integration reference are
pending. This report does not establish L2 acceptance. Accepted L1 integration is
`542ac0dbfa7a9fa13b99773f19e876054f035e54`; it supplies the unchanged allocation,
isolation, native authentication and durable job boundary.

Logical tasks now continue ordinary completed turns. Each primary, delegated
researcher, verifier and opponent uses its own measured 55% trigger, restricted
checkpoint, validated immutable handoff, confirmed closure and fresh native thread.
Task identity/objective/workspace/parent/role/phase/slot and cumulative observations
persist. Opponent history and objections are scientific Markdown, without L4
invocation or terminal decision authority. No compaction, thread resume, replay,
scientific work timer or new resource grant substitutes for rollover.

The small normalization module adapts the existing controller calculation from
`/home/francesco/Desktop/gits/codex_controller/codex_tui/policy.py`. Installed schema
was inspected using:

```sh
codex app-server generate-json-schema --out /home/francesco/Desktop/gits/research_project/research_pipeline/coding_pipeline/logs/20261112T214235_70d09e50/runtime/tmp/l2-schema
```

Actual fields are `thread/tokenUsage/updated.params.{threadId,turnId,tokenUsage}`;
`tokenUsage.last.totalTokens` measures current length, `modelContextWindow` is the
reported model window, and `tokenUsage.total` contains cumulative counters. Native
counts are int64 integers. The controller's usable/display convention subtracts
12,000 tokens from both length and window, with a zero floor on adjusted length;
windows at most 12,000 use the raw ratio. Exact integer comparison triggers at
55%. Unlike the controller, L2 does not clamp observations above 100%. First trigger,
latest raw measurement, native provenance/time/identities and maximum occupancy
survive checkpointing. Repeated cumulative notifications are not summed; counters
are retained per context and summed across predecessors. Inconsistent/missing
accounting is explicitly incomplete. Injected occupancy cannot update native
spending. Monetary spending and account quota remain unknown, separately reported.

The RPC reader only observes/signals lifecycle work. The runner handles active-turn
interruption outside that reader, including early notifications and simultaneous
completion/threshold observation. Closing resolves outstanding turn waiters with
an operational outcome. Intake/recovery admits no new jobs/assignments and must
obtain native telemetry within a 90-second operational bound. Every ordinary turn
boundary requires a new native observation. Missing/invalid telemetry permits one
focused measurement recovery; an unchanged valid measurement during a long job
wait has no wall-time expiry. Checkpoint turns also have a 90-second bound, one
handoff repair and a 15-second interruption-completion bound. These are operational
failure bounds, never scientific completion or investigation allowances.

Handoffs validate exact metadata, substantive required sections, accessible saved
artifacts, opponent history and surviving job references/guidance. Multiline
objectives can be blockquoted to preserve embedded Markdown headings. Validation
runs before closure and against exact captured versions afterward. Successor
intake receives the complete handoff ID/hash/text and artifact version map even
when the default 32-document listing omits them. Earlier immutable versions use
`document:ID` links. Ordinary artifact hashes are bounded file observations,
explicitly distinguished from immutable snapshots and changing job outputs.
Current human instructions/questions/feedback are reread; input changes are
compared with that logical task's predecessor rather than another agent's intake.
Canonical publication still waits for all writers to stop and preserves human edits.

Owned-job reconciliation waits for settling admissions under the existing job
lock and checks every active/uncertain ID, rather than relying on the bounded
summary. Runtime `job-handoff.json` and successor intake retain authoritative
command/cwd/status/original deadline/service/output records; scientist handoffs
supply purpose and inspection/wait/cancellation guidance. New computations remain
blocked until the successor inspects inherited active jobs. Job/delegation admission
rechecks lifecycle state inside the lock. Successful rollover never cancels or
relaunches jobs. Unrecoverable task failure blocks its admissions, retains science
and records, and attempts its owned cleanup while unrelated work remains active.
Unconfirmed context cleanup retains reservations and blocks successor admission.
Operational failures never write scientific COMPLETE/STOP. Schema 5 requires fresh
operational state; no migration was added.

Validation commands and evidence:

```sh
export PYTHONPATH=src:/home/francesco/Desktop/gits/research_project/research_pipeline/coding_pipeline/logs/20261111T063907_2732fff6/runtime/tmp/test-dependencies
RESEARCH_PIPELINE_M1_LIVE=0 RESEARCH_PIPELINE_M2_LIVE=0 \
RESEARCH_PIPELINE_M3_LIVE=0 RESEARCH_PIPELINE_M4_LIVE=0 \
RESEARCH_PIPELINE_M5_LIVE=0 RESEARCH_PIPELINE_V0_L1_NATIVE=0 \
RESEARCH_PIPELINE_V0_L2_NATIVE=0 \
/home/francesco/miniconda3/bin/python -W error::ResourceWarning -m unittest discover -s tests -v
```

Writer routine result: **148 tests discovered: 142 passed, six opt-in gates skipped**. Full output:
`coding_pipeline/logs/20261112T214235_70d09e50/runtime/tmp/l2-final-routine-tests.txt`.
Consequential fixtures cover all roles, exact/below/above thresholds, independent
occupancy/cumulative usage, early completion, active interruption and closure,
normal second turns, recovery, malformed/missing telemetry, handoff repair failure,
wrong metadata/unsafe artifacts, pagination/integrity, snapshot/successor/closure
failures, settling admission and delegation races. A synchronized **real local
process**, with explicitly doubled backend/service reconciliation, survives
automatic replacement while a second logical agent remains active; it retains
job identity, launch count, service record, deadline and output. This fixture is
not production isolation or native scientific inference evidence.

The enabled Writer invocation was:

```sh
RESEARCH_PIPELINE_V0_L2_NATIVE=1 \
RESEARCH_PIPELINE_V0_L2_OUTPUT_DIR=/home/francesco/Desktop/gits/research_project/research_pipeline/coding_pipeline/logs/20261112T214235_70d09e50/runtime/tmp/l2-writer-native \
/home/francesco/miniconda3/bin/python -W error::ResourceWarning -m unittest tests.test_v0_l2_native -v
```

It **failed before launching any service or inference**:
`systemd user bus unavailable: XDG_RUNTIME_DIR and DBUS_SESSION_BUS_ADDRESS must already be set in the authorized host environment`.
Neither variable was present. Retained failure receipt:
`coding_pipeline/logs/20261112T214235_70d09e50/runtime/tmp/l2-writer-native/receipt.json`.
It records zero commands/scenarios; no owned processes required cleanup. There is
no replacement bus/authentication/isolation path and no claim of live science.
An unpaid regression verifies separate failed receipts retain earlier failures.
After the final immutable-read and native-fixture edits,
`python -W error::ResourceWarning -m unittest tests.test_pending_documents tests.test_v0_l2_native -q`
with the same Python/PYTHONPATH and L2 gate disabled also passed: 11 discovered,
10 passed and the native gate skipped. The accepted L1 gate remains disabled;
its low-level fixture now explicitly verifies telemetry before granting working
admission, matching L2 intake without repeating accepted paid demonstrations.

Required trusted host invocation retains the inherited
`RESEARCH_PIPELINE_V0_L2_OUTPUT_DIR` and existing authorized bus/native credentials:

```sh
RESEARCH_PIPELINE_V0_L2_NATIVE=1 \
/home/francesco/miniconda3/bin/python -W error::ResourceWarning -m unittest tests.test_v0_l2_native -v
```

Final/combined discovery must also inherit the enabled gate. Every invocation
reserves fresh private output/receipt. The gate runs role scenarios sequentially
under two agents, 2048 MiB, zero swap, 128 tasks and one job. Native researchers
derive and continue a public trapezoidal-error analysis. A real controlled numerical
job with an original 7200-second timeout is held across automatic replacement;
an unrelated native agent writes further science before its release, and the
successor reads predecessor versions and collects/interprets the same job. Its
55% crossing is explicitly injected through the normal observation path; native
measurements/accounting and scientific reasoning remain distinct. Receipts retain
identities, actual caps/services/deadlines, handoff versions, observations,
scientific notes, outputs and explicit pause/cleanup. Structural checks do not
certify scientific correctness or prescribe reviewer agreement. Host evidence is
still required; none is anticipated here.

Human-owned PROJECT.md, AGENTS.md and the complete lifecycle amendment match their
source bytes. Protected inputs, retained M5 branch/worktree at
`1b70aea25f6c5f8496acdea12e9a27c6f3d4ecbd`, historical science/receipts and components
were untouched. No Git orchestration, remote publication or private investigation
was performed. README, current status and affected directory indexes describe the
new state. After reviewed host acceptance, **L3 centralized weekly reserve and
secondary staleness** is the next dependency; L4–L6 and human M5 acceptance remain.


**Review repair, attempt 1.** Corrected both requested findings. Measurement
freshness now uses the existing session-bound native request trace's
`inference_started.payload.request_payload.path` references as inference boundaries,
including calls whose tool declarations are unchanged. Every inference event is
ownership-checked before catalog deduplication; duplicate request references do
not create additional boundaries. Distinct valid native usage reports cover
pending starts without crediting later starts already buffered ahead of the RPC
reader. Duplicate and injected reports provide no such credit. A following start
without its predecessor's measurement blocks admissions and signals interruption
outside the reader, followed by the existing bounded recovery or truthful failure.
Job admission refreshes this evidence before acquiring the job lock. Disappearing
or regressing inference evidence fails closed instead of resetting coverage. A fully
measured completed recovery turn reestablishes coverage after earlier notification
loss. Completed turns also reject partially missing inference measurements.
Inference counts check telemetry delivery, never estimate context occupancy or
create an unmeasured fallback allowance. Idle `job_wait` introduces no new inference
boundary and no wall-time expiry. Native trace/telemetry correlation still requires
the pending trusted host final/combined checks; fixtures are explicitly labelled.

Deferred publication now validates pending batches, then selects the latest valid
descendant's draft per path within the same logical task's predecessor chain.
Superseded ancestor writes are skipped, so they cannot alter the canonical baseline
under their successors. Earlier scientific snapshots remain immutable. Genuine
human edits still preserve canonical text and retain the latest conflicting
proposal. Invalid descendant batches cannot suppress valid predecessor science.
Directory indexes refresh once per logical task after publication, avoiding false
attribution of the runtime's own index updates as human edits.

Added local-process JSON-RPC/native-schema trace regressions for a continuing
multi-tool turn losing usage notifications, actual interruption with admissions
already blocked, successful recovery, persistent-loss failure/cleanup, idle job waits, and loss
of previously recorded native boundary evidence. Added automatic-rollover/pause checks for latest canonical notes and
handoff, preserved human edits/proposals, absence of spurious conflict/index
preservation, retained predecessor snapshots and an invalid descendant batch.
Native catalog checks cover equal declarations, duplicate events and inference
count retention; usage duplicates/injection cannot hide delivery gaps.

Focused verification used the same Python and dependency path above:
`python -W error::ResourceWarning -m unittest tests.test_v0_l2 tests.test_native_catalog tests.test_pending_documents tests.test_review_repairs -q`
passed 44 tests before the final interruption-state assertions. The subsequent
full routine command above passed **156 discovered: 150 passed, six gates skipped**.
Final output is retained at
`coding_pipeline/logs/20261112T214235_70d09e50/runtime/tmp/l2-review-repair-verified-tests.txt`.

Rechecked the enabled L2 module with the same Python/PYTHONPATH, historical gates
and L1 native gate disabled, and these environment settings:

```sh
RESEARCH_PIPELINE_V0_L2_NATIVE=1 \
RESEARCH_PIPELINE_V0_L2_OUTPUT_DIR=/home/francesco/Desktop/gits/research_project/research_pipeline/coding_pipeline/logs/20261112T214235_70d09e50/runtime/tmp/l2-review-repair-native \
/home/francesco/miniconda3/bin/python -W error::ResourceWarning -m unittest tests.test_v0_l2_native -v
```

Result: two discovered, the unpaid receipt regression passed and the native
scenario failed on the same missing authorized user bus before any service or
inference launch. Fresh receipt:
`coding_pipeline/logs/20261112T214235_70d09e50/runtime/tmp/l2-review-repair-native/receipt.json`;
command output: `runtime/tmp/l2-review-repair-native-tests.txt` under that pipeline
run. Zero commands/scenarios were launched and no processes needed cleanup. The
original failure receipt is unchanged. Independent rereview and trusted native
final/combined verification remain required; no live inference or L2 acceptance
is claimed by this repair.


**Review repair, attempt 2 (2026-11-13).** Addressed both new P1 findings. A
telemetry recovery state now takes precedence over ordinary continuation, even if
a late valid report restores the measurement before interrupted completion. The
interruption event remains latched throughout restricted recovery and clears only
on success. New real JSON-RPC fixtures send valid usage between gap detection and
interrupted completion, then verify one interruption, a fresh bounded recovery,
normal continuation and an unlatched event. A second case loses the recovery
measurement and confirms truthful failure/cleanup despite the late prior report.

Successor attachment now compares canonical scientific fingerprints with its
predecessor's expected published state, separately from protected-input changes.
It carries unresolved external Markdown changes across pending successors and
includes them in `input_changes` and `science_changes`, with original/current
hashes. Known runtime publications and derived indexes do not become purported
human changes. A successor capturing the changed canonical file as its baseline
therefore cannot silently acknowledge it. Unresolved paths stay protected even if
content later returns to its original hash.

Added `control(action="incorporate_edit", path=..., sha256=...)` within the existing
controlled MCP tool, with one optional hash argument. The scientist first inspects
current canonical text and saves an incorporated draft. The operation validates
ownership, the current human version and the exact saved draft hash. It grants no
access to protected inputs/frozen evidence or another task's workspace. Publication
accepts only that bound revision and preserves the human text using the existing
`handoffs/preserved/` mechanism. Changed drafts require a fresh acknowledgement;
later human changes retain canonical precedence and a conflicting proposal.
These checks record explicit incorporation, not scientific certification or L4
terminal authority. No allocation, native authentication or job deadline changed.

Regressions cover human edits made while the predecessor is still active, intake
through the production attach path with explicit backend/service doubles, multiple
pending successors, explicit incorporation, stale hash rejection, changed drafts,
further human changes and return to original content. A real local Unix RPC test
verifies scope denials and the version-bound incorporation operation. Earlier
immutable scientific snapshots and human versions remain retained.

Using the existing Python/PYTHONPATH and all historical/L1/L2 gates disabled, the
routine discovery command above passed **165 discovered: 159 passed, six gates
skipped**. Final output:
`coding_pipeline/logs/20261112T214235_70d09e50/runtime/tmp/l2-review-repair-2-final-tests.txt`.
Focused `tests.test_v0_l2 tests.test_pending_documents tests.test_v0_l1` also passed
76 tests before the final version-cycle and event-latch assertions; full discovery
includes those final assertions.

The enabled invocation used the same native module command above with fresh
`RESEARCH_PIPELINE_V0_L2_OUTPUT_DIR=/home/francesco/Desktop/gits/research_project/research_pipeline/coding_pipeline/logs/20261112T214235_70d09e50/runtime/tmp/l2-review-repair-2-native`.
It again failed preflight on absent `XDG_RUNTIME_DIR`/`DBUS_SESSION_BUS_ADDRESS`,
before launching any service or inference. The unpaid receipt test passed; the
native scenario failed. Fresh receipt: `runtime/tmp/l2-review-repair-2-native/receipt.json`
under this run; command output: `runtime/tmp/l2-review-repair-2-native-tests.txt`.
Earlier receipts are unchanged. Required trusted native final/combined checks and
independent rereview remain pending; this repair claims no live scientific evidence
or L2 acceptance. Human-owned requirements, retained M5 work and components remain
unchanged; L3 remains the next dependency after L2 acceptance.

**Bounded recovery repair (2026-11-13).** Reproduced the remaining P1 before
changing production code: a human correction made before successor attachment
was silently overwritten by a successor-owned job whose preparation baseline
already contained that correction. The failing assertion and exact test name
are retained in `runtime/tmp/l2-recovery-job-reproduction.txt` under this run.

Removed the separate job publication path. The coordinator now validates job and
context batches together, selects successor versions, and applies the existing
logical-owner unresolved-edit and version-bound incorporation checks once.
Context drafts take precedence over their own jobs at the same path; successor
jobs can replace predecessor context drafts. Invalid batches cannot suppress
valid earlier science. Job-only publications use the latest owner's unresolved
changes, including across another successor. Publication retains human versions
and conflicting proposals through the existing ordinary-file mechanisms. Known
successful job publications also enter successor intake, avoiding false attribution
of the runtime's own writes as new human edits. No new control operation, revision
framework, telemetry policy, allocation or job deadline was introduced.

Nine added regressions use actual job preparation/admission and saved draft files
with explicit native/service doubles. They cover the reported reproduction,
another successor, ordinary conflict-free job updates, incorporation and preserved
human text, changed drafts, later human edits, job salvage from invalid context
batches with exact-hash enforcement, and invalid job batches retaining predecessor
science. Existing real JSON-RPC telemetry-loss/recovery-latch and context-publication
regressions still pass. These fixtures make no production-isolation or native
scientific-inference claim.

With the same Python/PYTHONPATH and disabled historical/L1/L2 gates specified above,
`python -W error::ResourceWarning -m unittest tests.test_pending_documents tests.test_v0_l2 tests.test_v0_l1 tests.test_review_repairs -q`
passed 95 tests before the final invalid-job regression. The final full discovery
command above passed **174 discovered: 168 passed, six gates skipped**, exit 0.
Logs: `runtime/tmp/l2-recovery-focused-tests.txt` and
`runtime/tmp/l2-recovery-final-tests.txt` under this run.

The enabled native module invocation above was repeated with fresh
`RESEARCH_PIPELINE_V0_L2_OUTPUT_DIR=/home/francesco/Desktop/gits/research_project/research_pipeline/coding_pipeline/logs/20261112T214235_70d09e50/runtime/tmp/l2-recovery-native`.
Exit 1: the unpaid receipt regression passed; the native test failed preflight
because both `XDG_RUNTIME_DIR` and `DBUS_SESSION_BUS_ADDRESS` are absent.
`runtime/tmp/l2-recovery-native/receipt.json` and
`runtime/tmp/l2-recovery-native-tests.txt` retain the exact failure: no commands,
scenarios, services or inference launched, and no owned-process cleanup was needed.
Earlier receipts were retained unchanged.

Fresh independent review must assess the repaired complete diff. Required trusted
final/combined discovery must still inherit `RESEARCH_PIPELINE_V0_L2_NATIVE=1`,
the original private output destination, the supplied dependency path and the
existing authorized host user bus. No passing host evidence or integration is
claimed here. L2 acceptance remains pending; L3 reserve/staleness is next afterward.

**Post-attachment publication repair (attempt 1).** Reproduced the review's
ordering for both initial and successor contexts: attach against unchanged science,
receive a human correction, prepare a job against that corrected canonical text,
then publish without an acknowledgement or a competing context draft. Both cases
failed before the repair; assertions are retained in
`runtime/tmp/l2-post-attach-reproduction.txt` under this run.

The shared publication boundary now reuses `science_intake()` to compare canonical
science with the latest logical context's expected state, including known runtime
publications. It refreshes unresolved changes and their current hashes once per
task before any batch writes, so a later job baseline cannot hide a human edit.
The existing exact human/draft hash checks still govern incorporation and preserve
the human version. Detection errors retain the existing visible publication failure
behavior. No new watcher, revision mechanism or control operation was added.

Six new regressions cover both context types, successful acknowledged job revisions
with human preservation, changed revisions and later human corrections. Valid jobs
also retain their protections when a context batch is invalid. Existing conflict-free
updates, immutable documents, ownership/cleanup and late-telemetry recovery tests pass.

Using the Python/PYTHONPATH and disabled historical/L1/L2 gates documented above,
`python -W error::ResourceWarning -m unittest tests.test_pending_documents tests.test_v0_l2 tests.test_v0_l1 tests.test_review_repairs -q`
passed **102 tests**. Final
`python -W error::ResourceWarning -m unittest discover -s tests -v`
passed **180 discovered: 174 passed, six gates skipped**, exit 0. Logs:
`runtime/tmp/l2-post-attach-focused-tests.txt` and
`runtime/tmp/l2-post-attach-final-tests.txt`.

Native inference was not repeated: `XDG_RUNTIME_DIR` and
`DBUS_SESSION_BUS_ADDRESS` are still absent in this Writer environment. The prior
enabled failure receipt and all earlier evidence remain unchanged. Independent
review and required trusted final/combined native discovery remain pending using
the enabled L2 gate and inherited authorized host environment; no L2 acceptance
or integration is claimed.

**Integration repair (milestone 002, attempt 1; 2026-11-13).** Read the complete
`tests/final-002.txt.commands/0001.txt` and retained host handoff/receipt. The only
integrated failure was primary rollover: the validator rejected an otherwise usable
handoff because its Artifacts section contained both `[BEFORE.md](../work/BEFORE.md)`
and `[primary.md](primary.md)`. Saved science contained substantive finite-sum and
panel-integral derivations. The original host receipt remains failed with confirmed
cleanup; it is not passing native evidence.

Self-navigation now contributes no artifact evidence or immutable dependency;
validation continues through the remaining links and still requires at least one
accessible saved scientific artifact. The researcher prompt makes that requirement
explicit. Two regressions exercise relative, absolute `/project/` and URL-encoded
fragment self-links, before closure and against final immutable snapshots. A mixed
handoff retains only the science artifact/version; self-only handoffs are rejected
and never recorded as validated. No native gate, retry bound, threshold, allocation
or scientific decision behavior changed.

Using the Python/PYTHONPATH and disabled gates in the routine command above:

```sh
/home/francesco/miniconda3/bin/python -W error::ResourceWarning -m unittest tests.test_v0_l2 tests.test_pending_documents tests.test_review_repairs -q
/home/francesco/miniconda3/bin/python -W error::ResourceWarning -m unittest discover -s tests -v
```

Focused result: **67 tests passed**. Full routine discovery: **182 tests,
176 passed and six opt-in gates skipped**, exit 0. Full output:
`runtime/tmp/l2-integration-1-routine-tests.txt` under this pipeline run.
The enabled native module invocation documented above was also run with fresh
`RESEARCH_PIPELINE_V0_L2_OUTPUT_DIR=/home/francesco/Desktop/gits/research_project/research_pipeline/coding_pipeline/logs/20261112T214235_70d09e50/runtime/tmp/l2-integration-1-native`.
Its unpaid receipt regression passed; native preflight failed because
`XDG_RUNTIME_DIR` and `DBUS_SESSION_BUS_ADDRESS` are absent. No services, inference,
commands or scenarios launched. Fresh retained evidence is
`runtime/tmp/l2-integration-1-native/receipt.json` and
`runtime/tmp/l2-integration-1-native-tests.txt`. Prior receipts are unchanged.
The repaired native continuation still requires trusted final/combined discovery
with the inherited enabled L2 gate, authorized host bus and a fresh receipt.
No L2 acceptance is claimed; L3 remains the next dependency afterward.
