# M4 reference retrieval: implementation readiness

This implements supplied milestone 1 only: explicit reference authorization,
navigation, actual full-text retrieval, read-only scientific access and qualified
reuse continuity. It does not establish whole-M4 acceptance. Tool description,
validation/registration/execution and the opt-in real Codex reuse demonstration
belong to the subsequent supplied increment. No paid M1–M3 gate was rerun.

## Decisions and behavior

- The target's human-controlled `.research_pipeline/references.json` holds only
  version-1 alias-to-absolute-path authorizations. Public `reference add`, `remove`,
  `list`, `browse`, `search` and `read` commands return JSON. Registration works before
  first start; later mutations reuse the investigation lock, stale-owner recovery
  and cleanup confirmation. Conflicting aliases, invalid roots, overlap, links and
  special exposed files fail without replacing the previous registry.
- `references.py` uses the standard library and runs unchanged as an isolated
  standalone retrieval helper. No index service, dependency, claim registry or
  automatic qualification system was introduced. Search streams all actual UTF-8
  contents, including Markdown, scripts and structured text, with literal,
  case-sensitive matching. Results include original source identity, relative file,
  one-based location and bounded excerpt. Reads paginate numbered lines, hash the
  full observed file and reject unstable/disappeared versions.
- Binary/PDF extraction and OCR are unsupported. UTF-8 failures, binary/NUL content,
  unreadable files, unavailable references and result/error clipping are explicit.
  Incomplete search cannot establish an exhaustive absence. Missing sources remain
  registered; other sources and saved science remain usable.
- Every activation refreshes references under its existing preparation deadline.
  Each available source exposes only individual non-hidden top-level entries,
  with regular-tree validation and no symlink following. Hidden controller/backend
  roots are excluded. Bubblewrap mounts scientific entries, the immutable catalog
  and helper read-only under `/references` and `/run`. Native working paths,
  drafts, authentication, Codex instruction-discovery controls, frozen verifier
  inputs, ownership, cleanup and cumulative grants retain their existing behavior.
- Intake/checkpoint snapshots retain authorizations and availability; registry
  fingerprints enter normal current-input reconciliation. Source projects are not
  recursively hashed or treated as target instructions. Source changes cannot
  automatically upgrade scientific verification status.
- Prompts require source qualifications and applicability assessment. Material reuse
  is documented by the researcher in `sources/REUSE.md` (or task-local `REUSE.md`),
  through existing scoped drafts and human-edit preservation. Entries retain
  source links/hash, assumptions, source verification and basis, uncertainty,
  intended use/applicability and checks. Exact external evidence needed by a
  verifier must be copied into permitted local science and explicitly included in
  the existing frozen packet. Live references do not replace frozen inputs.

No scope deviation was needed. An existing
rollover test double was updated to accept the preparation deadline. New tests use
engineering fixtures/doubles, not prewritten scientific findings or model receipts.
PROJECT.md, engineering AGENTS.md and manager STATUS.md remain unchanged.

## Review repair

The review identified two consequential preparation defects, both corrected:

- Reference enumeration/validation now polls and cancels through the existing
  foreground preparation callback. Intake, catalog refresh and mount assembly all
  receive it; `scandir` polls between enumerated entries instead of first collecting
  a whole large directory. The coordinator installs its task control before intake,
  services running contexts during traversal and publishes a reserved successor's
  current status before early callbacks. Preparing tasks have no context countdown
  until running. Primary continuation between contexts also honors pause during
  reference traversal and settles its existing pending interval on cancellation.
- Schema-2 resume now persists a recoverable `resume_preparation_pending` interval
  before intake. On success, the next durable activation takes ownership of that
  same interval; failed preparation settles elapsed work against the saved remaining
  allowance. Timeout and interruption persist their outcomes without launching a
  backend. Recovery of a killed preparation charges once, conservatively bounded
  by the original remaining allowance, without cleaning already-stopped historical
  services or rewriting the previous model session/usage.

Regression fixtures simulate slow source filesystem operations while a live parent
needs rollover, a whole-owner pause during mount assembly, and a pause between
primary contexts. Accounting checks cover exhaustion preventing another allocation,
failure/interruption with retry, successful transfer without double charging and a
SIGKILL before activation registration followed by repeated recovery. These are
engineering tests, not paid scientific demonstrations.

Final repair verification used the ordinary discovery command below with all paid
gates disabled: **178 tests passed, four expected skips** (disabled M1/M2/M3 paid
gates and the unavailable systemd user-service test class). This includes all six
new regressions plus the existing actual Bubblewrap boundary checks. Full service
enforcement still requires the controller host's existing enabled verification;
no host capability or broader M4 acceptance is claimed by these repair checks.

## Initial validation

With all paid gates disabled:

```sh
env RESEARCH_PIPELINE_M1_LIVE=0 RESEARCH_PIPELINE_M2_LIVE=0 \
  RESEARCH_PIPELINE_M3_LIVE=0 RESEARCH_PIPELINE_M4_LIVE=0 \
  python -m unittest discover -s tests
```

Ordinary discovery passed: **172 tests, four skips** (the three disabled paid gates
and the systemd-user-service test class). The actual Bubblewrap boundary checks
passed, including reference/helper/catalog write, create, unlink and rename refusal;
hidden source controls absent; full-text helper search/read; permitted target
computation; unchanged source files/indexes and protected-input fingerprints.

Focused retrieval, continuity, rollover, isolation, collaboration and independent
verification checks passed: **101 tests, one skip**. A verbose isolation run passed
**nine tests, one skip**, confirming
actual mount enforcement, task/frozen-evidence boundaries and native code-mode
runtime startup. M4 now participates in enabled prerequisite-failure checks.

Tests cover deep full-text discovery beyond the 256 KiB intake limit, scientific
script/structured-text formats, pagination/clipping, source version changes,
authorization boundaries, malformed registries preventing launch, unavailable
sources alongside usable ones, realistic decoding/binary/unreadable failures,
reference refresh across all roles and fresh primary contexts, source instructions
remaining evidence, qualified reuse notes and concurrent human edits. Existing
M1–M3 engineering checks retain cumulative budgets, independent verification,
whole-owner cleanup and suspension coverage.

This Writer host lacks the required systemd user bus. Full production-service
cgroup/lifetime enforcement remains unverified here; no alternate bus, execution
context or unisolated scientific fallback was used. Enabled controller-host final
verification must establish those capabilities. `RESEARCH_PIPELINE_M4_LIVE=1`
cannot silently skip missing isolation prerequisites. The real M4 Codex test itself
is intentionally outstanding until the tool-reuse increment.

## Remaining M4 work and known control/reporting gaps

Tool registration and sufficient intended-use checks must distinguish user-supplied
and agent-developed tools without trusting discovery. Reuse/adaptation will need
permitted working copies and explicit dependencies/invocation; source scripts must
never run directly on the controller or gain authority through descriptions.
The subsequent real new-investigation demonstration, independent checking where
consequential, private receipts, bounded isolated reproduction, controller final
checks, review and pipeline-confirmed local integration remain required.

Existing limitations are concrete: no backend hard model-spending cap or reliable
context-occupancy control; fixed session durations cannot guarantee exact 60%
occupancy; CPU fraction and aggregate CPU time are uncapped; missing model usage
telemetry remains unknown despite cumulative observed totals; per-file limits do
not impose an aggregate workspace disk quota. Reporting/resource-control closeout
must assess these gaps separately within M4. This change supplies no broader
controls and does not reset investigation grants or claim M4/M5 completion.
