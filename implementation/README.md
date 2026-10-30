# Research workbench foundation

This directory contains the `theoretical-research-pipeline` distribution and its
`research_pipeline` import package. It provides package identity, CLI help/version,
development validation, and a synthetic oscillator development fixture with a
source-local loader, validated domain envelopes, immutable local artifacts, and
SQLite-backed atomic revision submissions with durable receipts and audit events.
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
graph submission/append/reopen/retry example. Select runtime directories explicitly
outside software source. Creation rejects existing roots; opening gates fixed
schema version 1 before normal rollback-journal recovery. SQLite uses DELETE/EXTRA,
foreign keys and a 5000 ms busy timeout. Independent handles compare relevant heads;
exact submission retries return original metadata-only receipts even after head
advancement or later artifact damage. Record/history exposure verifies attached bytes.
Use the original submission identity to reconcile uncertain commit acknowledgment.

Real disk and fresh-process tests cover ordering/canonical fingerprints, stale and
conflicting writes, retained orphans, hot-journal recovery, post-commit interruption,
and later artifact integrity failures. Local test results are advisory to controller
validation. Full scientific schemas/kinds, support/assessment freshness,
eligibility/promotion, worker isolation, attempt leases/fencing, resource
authorization/accounting, general migrations, periodic scheduling, distributed
execution and research execution remain unsupported. There is no duplicate charging
guarantee without a ledger. Artifact identity and completed task state confer no
scientific support; no overall M0-E, M0-S, M1, D02 or full-product completion follows.

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
verifies historical artifact inventories and restores independent version-1 stores.
See [backups](../docs/backups.md) for exact signatures, runnable examples, strict
manifest verification, retained incomplete directories and uncertain publication
acknowledgment. This is partial R-019/R-017 evidence; full D02, real research-run/
session/job recovery, scientific validation and live-provider work remain outstanding.
