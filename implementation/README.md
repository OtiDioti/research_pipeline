# Research workbench foundation

This directory contains the `theoretical-research-pipeline` distribution and its
`research_pipeline` import package. It provides package identity, CLI help/version,
development validation, and a synthetic oscillator development fixture with a
source-local loader, validated domain envelopes, immutable local artifacts, and
SQLite-backed atomic revision submissions with durable receipts and audit events,
and typed scientific content with exact envelope relationships and durable admission/read.
Attributed Review/Issue values, exact assessment envelopes and durable typed
admission/read are also available. Immutable multi-file WorkProductManifest values
join the same typed boundary; see [work products](../docs/work-products.md).
It implements no research execution, models, scientific verification, or vault
generation. Specification v1.4 separates engineering readiness from scientific
validation; this durable slice does not complete either overall gate or M1/D02.
Implementation is submitted for review; controller acceptance and integration are
separate events.

Use Python 3.11+; Linux is the initially verified development platform. The product
has no third-party runtime dependencies. Git is required for development validation
of repository administration and source revision. Setuptools (>=61) is build tooling
only, declared through `setuptools.build_meta`; it is not imported by the product.
Frozen validation requires no installation or downloads.

Run these exact commands from the repository root:

```bash
PYTHONPATH="$PWD/implementation/src" python3 -B -m research_pipeline --help
PYTHONPATH="$PWD/implementation/src" python3 -B -m research_pipeline --version
PYTHONPATH="$PWD/implementation/src:$PWD/implementation" python3 -B -m unittest discover -s implementation/tests -t implementation -v
/home/francesco/miniconda3/bin/python3 -B implementation/scripts/validate.py
```

No arguments also prints help. Unknown commands, options, and abbreviated options
produce a usage error (status 2). There is no research command or console-script
interface. Explicit candidate-source paths avoid relying on an editable install
from another checkout.

The full validation process must inherit `RLIMIT_NOFILE` soft=4096 within its
existing hard limit. In the launching shell, after confirming the hard limit is
at least 4096, set `ulimit -S -n 4096` before running the unchanged validator.
This is a per-process prerequisite, not a persistent host setting. Source capture
holds selected file descriptors through the integrity gate; the 1,024-selected-file
case needs that capacity. Descriptor exhaustion is an ordinary
`CheckoutOperationalError`, not a reason to relax capture checks or skip tests.

Direct unittest discovery provides useful development feedback. The validator also
checks root layout, required documents, candidate import origin, clean nonempty
discovery, and at least one executed successful case. Skipped and expected-failure
cases do not satisfy that last requirement. Failures, errors, unexpected successes,
and missing/empty suites fail validation. Diagnostics retain tracebacks and report
counts and the actual source HEAD; source exports without a revision explicitly
report it as unavailable with a reason. Revision output describes source context,
not acceptance.

The validator derives the repository root from its own location, accepts no root
or bypass options, and disables bytecode writes. Tests launch isolated subprocesses
and use disposable fixtures, including Git administration fixtures without commits.
They check that fixture bytes and directory contents remain unchanged. Import-effect
guards demonstrate observed behavior, not a security sandbox.

Root directories and regular `.md` files are allowed; root symlinks are forbidden.
Git's legitimate `.git` pointer file is an exception checked using Git's read-only
resolver. `project_description.md`, `README.md`, and `AGENTS.md` must be non-symlink,
nonempty UTF-8 regular files. Validation never rewrites those documents.

See [foundation architecture](../docs/architecture.md) for module boundaries and
future scientific-runtime limits.

The [durable records guide](../docs/durable-records.md) documents direct imports
from `research_pipeline.domain`, `research_pipeline.artifacts` and
`research_pipeline.store`, exact signatures/errors, and a runnable temporary-store
low-level generic graph submission/append/reopen/retry example. Select runtime
directories explicitly outside software source. Creation rejects existing roots; opening gates fixed
schema versions 1 and 2 before normal rollback-journal recovery. New stores use
schema 2; legacy stores retain old-kind operations without rewriting. SQLite uses DELETE/EXTRA,
foreign keys and a 5000 ms busy timeout. Independent handles compare relevant heads;
exact submission retries return original metadata-only receipts even after head
advancement or later artifact damage. Record/history exposure verifies attached bytes.
Use the original submission identity to reconcile uncertain commit acknowledgment.

Real disk and fresh-process tests cover ordering/canonical fingerprints, stale and
conflicting writes, retained orphans, hot-journal recovery, post-commit interruption,
and later artifact integrity failures. Local test results are advisory to controller
validation. Remaining typed payloads and state machines,
support/assessment freshness, eligibility/promotion, worker isolation, attempt leases/fencing, resource
authorization/accounting, general migrations, periodic scheduling, distributed
execution and research execution remain unsupported. There is no duplicate charging
guarantee without a ledger. Artifact identity and completed task state confer no
scientific support; no overall M0-E, M0-S, M1, D02 or full-product completion follows.

The [typed scientific content contract](../docs/typed-content.md) documents frozen
contexts, provisional claims, conjunctive justifications and synthetic/unverified
evidence, strict codecs, exact role projection and runnable codec/persistence examples.
`RecordStore.submit_typed` admits the four scientific, two assessment, work-product manifest, Source, corpus-manifest and project kinds
as coherent exact typed target graphs atomically;
`get_typed_revision` returns the exact envelope and decoded value. `submit` remains
a trusted generic persistence API, not a scientific admission gate. Typed retries
and backups preserve original receipts and historical scope without promotion.

The [attributed assessment contract](../docs/attributed-assessments.md) documents
pure Review/Issue codecs, independent reported dimensions, explicit route judgments
and exact envelope links. Their dimensions are separate from canonical state;
reported independence, checks, policy references and provenance confer no authority
or scientific truth. Durable assessment admission checks constrained targets and
exact route-conclusion membership under the existing write transaction. Generic
manifest/policy/execution/affected roles remain shallow. The executed persistence
example retains disagreements and separate Issue revisions through reopen/restore,
without changing candidate history. Current eligibility/freshness, Apply disposition
and scientific qualification remain future work.

The [synthetic oscillator walkthrough](../docs/synthetic-oscillator.md) documents
the versioned fixture, exact-reference contract, loader exceptions, expected scoped
assessments, and focused test commands. It is neither expert-audited nor held-out
material. Load it from the repository root without installation:

```bash
PYTHONPATH="$PWD/implementation/src" /home/francesco/miniconda3/bin/python3 -B -c 'from research_pipeline.fixtures import load_oscillator_fixture; data = load_oscillator_fixture()'
/home/francesco/miniconda3/bin/python3 -B implementation/scripts/validate.py
```

The default data path follows the resolved source module, independently of cwd.
Explicit relative inputs are caller-relative; missing inputs fail with ordinary
file errors and are never acquired. Each load returns fresh mutable data. This
paper fixture adds no research CLI command or runtime/persistence capability.

## Verified local backup and restore

The explicit `research_pipeline.backup` API captures consistent SQLite snapshots,
verifies historical artifact inventories and restores independent stores exactly.
Supported backup format/schema pairs are `(1, 1)` and `(2, 2)`; default restore
preserves the source version. Schema 2 admits twenty generic kinds while retaining
claim/task state rules; all fifteen additions require null canonical states.
Legacy new-kind requests fail with a migration-required error. The separate
schema-2 administrative history format is validated and preserved; fresh creation
invents none. `restore_backup(root, destination, *, target_schema=None,
migration_provenance=None)` supports only explicit v1→v2 migration with ordinary
integer target `2` and caller-supplied `CreationProvenance`. Both defaults select
exact restoration. Migration preserves historical values and original receipts
and records the verified source identity/digest separately under the existing
durable incomplete marker. Invalid options fail before reservation; interrupted
copies remain unusable and retries require a new absent path.
See [backups](../docs/backups.md) for exact signatures, runnable examples, strict
manifest verification, retained incomplete directories and uncertain publication
acknowledgment. This is partial R-019/R-017 evidence; full D02, real research-run/
session/job recovery, scientific validation and live-provider work remain outstanding.

[Work-product manifests](../docs/work-products.md) provide explicit authors, portable logical
paths, ordered exact references and optional previous-revision supersession. Repeated
bytes can appear at distinct paths. Manifest context/claims/supersession are typed
edges; build dependencies and Review context-manifest references remain shallow.
Kind labels certify no detailed TeX/checkpoint/run-report/execution contract; attribution
is declared, not authenticated. [Safe durable checkout](../docs/checkout.md) provides
`checkout_work_product` and read-only `inspect_checkout` directly from
`research_pipeline.checkout`. Explicit exclusion roots and finite byte/count limits
bound independent writable copies; durable controls distinguish retained incomplete
output from publication with uncertain acknowledgment. Inspection does not authenticate
local descriptors or certify edited bytes.
[Preview and explicit import](../docs/work-product-import.md) provides bounded capture,
detached summaries and strict saved proposals for separate `submit_typed` commit and
original-ID recovery. Full vault/intake, scientific sufficiency and research execution
remain deferred; D02 is partial.

[Versioned Source captures](../docs/sources.md) add bounded bibliographic declarations,
explicit unknowns, original/derived artifact lineage, exact locations and attributed
reading/statements. Capture, upstream and reading-report revisions remain distinct.
Typed history preserves work identity while old exact references and original receipts
remain pinned. Generic historical source payloads and existing shallow source roles
remain supported. The runnable synthetic example executes no parser and reads no
paper. [Bounded local Source capture](../docs/source-capture.md) adds explicit file
selection, strict saved proposals, separate commit and original-ID recovery.
Scientific readiness and D02/D03/M0-S qualifications remain partial/pending.


[Immutable seed inventories](../docs/corpus.md) add pure bounded CorpusManifest
values and exact durable selection/history checks over Source captures. The ninth
typed kind keeps original baselines, attributed declarations, inert locators and
explicit replacement identities through restart and backup. Direct selected
originals are verified; transitive closure remains metadata-only. Corpus inventory
alone establishes no project readiness, scientific support or operating grant.


[Versioned project intake](../docs/project-intake.md) adds the tenth typed kind,
ProjectSetup, with exact original/current corpus pins, attributed declarations,
conditional document/location coherence and complete immutable history. Readiness
is an attributed proposal presented as awaiting materials, incomplete setup or
awaiting authorization; actual research admission remains subsequent work. The
self-contained documented example records an empty shell, captures a short note
and appends a dossier using ordinary saved Submission requests.
