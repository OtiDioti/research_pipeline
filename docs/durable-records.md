# Durable revisions, artifacts and atomic submissions

The local durable core provides domain-independent record values, immutable
artifact bytes and SQLite-backed atomic, idempotent revision submissions. They support engineering work under specification v1.4;
they do not establish scientific validation or complete M0-E, M0-S, M1 or D02.
Controller acceptance and integration remain separate from implementation and test
results. The historical oscillator fixture, including its v1.3 provenance, remains
an intentionally separate paper example.

`research_pipeline.domain` owns validation and detached JSON serialization.
`research_pipeline.artifacts` owns filesystem layout, publication and integrity.
`research_pipeline.store` owns private SQLite metadata, transactions and recovery.
Imports are inert. Use direct submodule imports; no installation or package-level
re-exports are needed. The CLI still provides only help/version.

## Domain API

All domain values are frozen and validate their constructors at runtime. Each has
`to_dict()` and `from_dict(value)`: dictionaries are detached JSON-compatible data,
and reconstruction rejects missing required fields, unknown fields and malformed
nested values. Defaulted constructor fields may also be omitted in serialized
input; `to_dict()` always includes them. No reconstruction invents a timestamp.
Invalid domain fields and invalid `put` input types raise
`research_pipeline.domain.DomainValidationError`, a `ValueError` subclass.

| Constructor | Contract |
| --- | --- |
| `CreationProvenance(actor, created_at, details={})` | Attributed creator and explicit UTC time; details is descriptive JSON object metadata. |
| `RecordReference(record_id, revision, relationship, target_kind=None)` | One exact revision and a required relationship label; optional target kind is a supported kind. |
| `ArtifactReference(digest, size)` | SHA-256 address and byte count; no path or URL. |
| `RecordEnvelope(record_id, revision, kind, content, provenance, record_references=(), artifact_references=(), operational_status=None, scientific_disposition=None)` | Common validated storage fields, typed provenance and typed reference sequences. |

Record IDs, actor IDs and relationship labels are case-sensitive opaque strings
matching `[A-Za-z0-9][A-Za-z0-9_-]{0,127}`. Nothing strips whitespace, infers a kind,
or parses identity meaning. Revisions are ordinary integers from 1 through
`2**63 - 1`; artifact sizes are ordinary integers from 0 through `2**63 - 1`.
Booleans, floats and numeric strings are not integers for these fields. Digests
are exactly 64 lowercase hexadecimal characters.

`created_at` accepts the RFC3339 subset `YYYY-MM-DDTHH:MM:SS[.ffffff]Z`, with
one through six fractional digits when a fraction is supplied. Calendar and time
must be valid; leap seconds and other timezone spellings are not accepted. Values
normalize to six fractional digits. This is attributed creation information,
not authenticated execution or a database commit timestamp.

The five supported kinds are `research_context`, `claim`, `justification`,
`evidence`, and `task_specification`. They are common envelopes, not full
scientific payload schemas or all specification §5.1 records.

| Kind | Required canonical state |
| --- | --- |
| `claim` | Explicit `scientific_disposition="provisional"`; `operational_status=None`. |
| `task_specification` | Explicit `operational_status` in `proposed`, `ready`, `blocked`, `active`, `completed`, `cancelled`, `abandoned`; `scientific_disposition=None`. |
| Other supported kinds | Both state fields are `None`. |

Claims cannot have canonical `supported`, `endorsed`, `supported_within_scope`,
or any other non-provisional disposition. Task completion records the caller's
operational assertion; it proves neither execution nor scientific support.
Descriptive JSON can quote support or contain keys such as `status`, `endorsement`
and `scientific_disposition`. Those keys never override typed fields, create an
assessment or grant authority. There is no recursive blacklist of scientific prose.

Content and provenance details must be ordinary JSON objects. Nested values may
be ordinary dictionaries with string keys, lists, strings, integers, finite
floats, booleans and null. All keys and string values must contain only Unicode
scalar values: actual surrogate code points (U+D800–U+DFFF), including explicit
Python surrogate pairs, raise a field-specific `DomainValidationError`.
Supplementary characters remain supported, including valid JSON surrogate
escapes decoded into a supplementary scalar. Literal backslash-u text is also
accepted. No characters or fields are normalized, replaced, merged or discarded.
Tuples, sets, bytes, custom objects, nonstring keys,
nonfinite numbers and cycles fail. Serialization/depth failures report domain
validation errors. Each object is retained as a private canonical JSON string:
sorted mapping keys, compact separators, ASCII escaping, and no NaN/Infinity.
Mapping insertion order is irrelevant; ordered lists and scalar types matter
(`1`, `1.0` and `true` remain distinct). Properties and serialization return fresh
mutable trees; caller mutations and edits to returned trees cannot change a
value. Reference sequences are copied to tuples in their original order, without
sorting or deduplication.

A constructed record reference is syntactically valid only. Submission resolves
exact targets, compares declared target kinds and enforces stable identity kinds. An artifact reference alone says nothing about current
availability: `read` or `verify` must establish integrity.

## Artifact API and failure contract

Import `ArtifactStore` from `research_pipeline.artifacts`:

| Operation | Result and effects |
| --- | --- |
| `ArtifactStore.create(root)` | Create a new owned area under an existing parent; reject any existing root without changing it. Sync the layout and parent directory. |
| `ArtifactStore.open(root)` | Validate an existing complete layout; no creation, repair, chmod or cleanup. |
| `store.put(data: bytes) -> ArtifactReference` | Publish immutable bytes, including empty bytes, or fully verify and reuse existing identical bytes. |
| `store.read(reference: ArtifactReference) -> bytes` | Verify and return the full byte string. |
| `store.verify(reference: ArtifactReference) -> None` | Apply the same full integrity checks without retaining a returned byte string. |

The caller must select a runtime directory **outside software source**. Relative
paths are relative to the caller's working directory; there is no default path,
environment-selected location or fixture fallback. `put` accepts only immutable
`bytes`, not mutable buffers, filenames, streams or URLs. The API is for a trusted
local controller; it is not an access-control service or a worker endpoint.
There is no public arbitrary object-path operation and no retained handle requiring
`close()`.

The layout is `root/objects/<digest>` plus private `root/.staging/` files. Newly
created directories use mode `0700`; managed directories must belong to the
current effective user and grant no group/other access. Opening and every
operation recheck these conditions. Path traversal rejects symlink components,
including managed directories; it does not use symlink-resolving normalization
as a safety check. External parent directories must be trusted against concurrent
replacement. Directory/file descriptors are operation-scoped and closed on exit.

New objects are written to unique exclusively created mode-`0600` staging files,
changed to `0400`, and file-synchronized before publication. Atomic hard-link
creation publishes without replacing a destination. A competing publisher's
winner is fully verified before reuse. The canonical file and objects directory
are synchronized before success is returned, including reuse of an object another
publisher may just have linked. Ordinary cleanup removes only the current call's
temporary entry and synchronizes the staging directory.

Reads, verification and reuse reject symlinks (including dangling links),
nonregular objects, foreign-owned or writable files, unexpected sizes, truncated
bytes, and SHA-256 mismatches. Inspection and no-follow/nonblocking opening prevent
FIFOs from hanging before descriptor validation. Bytes are read and hashed from
the same opened descriptor. Reuse also compares those bytes with the supplied
input. A corrupt destination is never overwritten, unlinked, repaired or chmodded,
even if correct bytes were supplied to `put`.

All artifact-operation exceptions derive from `ArtifactError`:

| Exception | Meaning |
| --- | --- |
| `ArtifactLayoutError` | Missing, incomplete, non-directory, linked or unsafe owned layout; creation of an existing root. |
| `ArtifactNotFoundError` | No canonical object at the validated digest. |
| `ArtifactIntegrityError` | Unsafe canonical object or byte/size/hash mismatch. |
| `ArtifactIOError` | Operational read, write, publication or synchronization failure; useful underlying `OSError` causes are retained. |

Synchronization failures never count as success. Before publication, failures
expose no partial canonical file. After publication, failures may leave a valid
unreferenced object; canonical publication is never rolled back. Abrupt termination
may leave staging entries, and failed creation may leave an incomplete area.
Cleanup makes a best effort on failure while preserving the original diagnostic.
There is no sweeping cleanup, destructive orphan collection, download or
regeneration fallback. `open` does not repair such state.

Durability assumes the recorded Linux/POSIX target supports reliable file and
directory `fsync`, `O_DIRECTORY`, `O_NOFOLLOW`, and atomic hard links on the same
filesystem for staging and objects. Unsupported operations fail rather than
weakening the protocol. Directory privacy and read-only files constrain ordinary
access, not a hostile storage owner, privileged process, or unsupported filesystem.
Later artifact integrity checks detect mutation; they provide no scientific
validity or independent copy. Use the separate [backup boundary](backups.md) for
verified local snapshots and restoration.

## Submission values and fingerprint

`Submission(submission_id, provenance, records, expected_heads)` is a frozen,
defensively detached request. `provenance` is a `CreationProvenance` identifying
the submitting controller, independently of each record's creator. `records` is
a nonempty ordered sequence of envelopes with one revision per identity.
`expected_heads` must be an explicit dictionary covering exactly those identities:
zero requires absence; a positive integer must equal the current head. The same
ordinary-integer bound applies, excluding booleans. The next revision must equal
expected head plus one; exhaustion fails. Typed nested values are revalidated at
construction and submission. Returned `expected_heads` and JSON trees are detached.

`SubmissionReceipt(submission_id, fingerprint, event_id, committed_at, provenance,
revisions)` and `AuditEvent(event_id, submission_id, event_type, committed_at,
provenance, revisions)` are frozen, detached values with strict `to_dict()` and
`from_dict(value)` operations. `revisions` is an ordered tuple of `(record_id,
revision)` pairs in request order (JSON serialization uses lists).
`event_type` is exactly `submission_committed`. The store generates `committed_at`
as UTC with six fractional digits; it describes local recording, not authenticated
scientific execution. Receipts are reconstructed from persisted metadata without
consulting current heads or inventing a new timestamp. One unique event belongs
to each submission; membership/order lives in revision rows, not another envelope
or receipt copy.

The fingerprint is lowercase SHA-256 of canonical UTF-8 JSON for:
`{"fingerprint_version": 1, "submission": submission.to_dict()}`. Canonical JSON
uses sorted mapping keys, compact separators, ASCII escaping and finite strict
JSON types. It includes submission identity, complete normalized submission and
creation attribution/time/details, expectations, all content and canonical states,
exact relationship fields, and artifact addresses/sizes. Mapping insertion order
is immaterial. Record, relationship, artifact and nested JSON list order is
meaningful, including duplicates; `1`, `1.0` and `true` remain distinct. Generated
commit time, event sequence, current heads and artifact paths are excluded.
The database retains canonical request text as well as its hash and compares text
on identity reuse, rather than trusting hash equality alone.

## RecordStore API

Import `RecordStore` and metadata error classes from `research_pipeline.store`.
No installation or package-level re-exports are needed.

| Signature | Result and effects |
| --- | --- |
| `RecordStore.create(root) -> RecordStore` | Create only an absent private root, then exclusively create and initialize its mode-0600 database; sync database and directory before success. |
| `RecordStore.open(root) -> RecordStore` | Validate an existing layout and schema, then open for normal SQLite recovery; never create missing files or initialize a database. |
| `store.close() -> None` | Idempotently close; later operations fail with `StoreClosedError`. Context-manager exit closes too. |
| `store.put_artifact(data: bytes) -> ArtifactReference` | Delegate durable byte publication; no metadata registration. |
| `store.read_artifact(reference: ArtifactReference) -> bytes` | Delegate verified byte retrieval. |
| `store.submit(submission: Submission) -> SubmissionReceipt` | Atomically append a new batch, or return the original receipt for an exact retry. |
| `store.get_revision(record_id: str, revision: int) -> RecordEnvelope` | Return exactly that revision after checking direct artifacts; absence raises `RecordNotFoundError`. |
| `store.history(record_id: str) -> tuple[RecordEnvelope, ...]` | Revision-ascending verified history; absent identities return an empty tuple. |
| `store.head(record_id: str) -> int \| None` | Metadata-only current revision number or absence. |
| `store.get_submission(submission_id: str) -> SubmissionReceipt \| None` | Metadata-only original receipt or absence. |
| `store.audit_events() -> tuple[AuditEvent, ...]` | Metadata-only events in ascending event-ID order. |

Lookup identifiers and revisions are validated before querying. Compound reads use
a consistent transaction snapshot, including envelope content and ordered link
rows. Envelopes are reconstructed from normalized relational rows through domain
constructors; no separately stored envelope can disagree with its link tables.
The SQLite connection and SQL operations are private. Each handle uses SQLite's
ordinary same-thread restriction; open independent handles on their owning threads.
There is no worker endpoint, generic write operation, policy grant or research CLI.

All metadata failures derive from `StoreError`:

| Exception | Meaning |
| --- | --- |
| `StoreLayoutError` | Missing/unsafe layout, unsupported version/journal format, or malformed fixed schema. |
| `StoreClosedError` | Closed or invalidated handle. |
| `RecordNotFoundError` | Requested exact revision absent. |
| `RevisionConflictError` | Stale head, skipped/repeated/exhausted revision, or changed kind. |
| `ReferenceResolutionError` | Missing exact target or wrong declared kind. |
| `SubmissionConflictError` | Reused identity with different canonical request. |
| `StoreBusyError` | Busy/locked SQLite failure after its bounded wait; no spin or automatic replay. |
| `StoreDatabaseError` | Other database/integrity failure; useful SQLite cause retained. |

Malformed requests continue to raise `DomainValidationError`. Object failures keep
the existing `ArtifactError` subclasses. Injected exceptions and Python-handled
interruptions retain their original diagnostics. OS/database causes are chained.

## Runtime layout, schema and locking

The explicit root contains `objects/`, `.staging/`, and `metadata.sqlite3`.
`create` first creates the artifact area, then exclusively creates the database.
Any existing root, including a standalone artifact area, is rejected unchanged;
there is no silent upgrade. Failed creation may leave an incomplete root, never
erased, repaired or swept. Missing, symlinked, nonregular, foreign-owned or
group/other-accessible database files are rejected. Runtime data must stay outside
software source; relative paths use the caller's working directory.

Version 1 (`PRAGMA user_version`) and DDL commit in one explicit transaction.
Opening first rejects any `.restore-incomplete` entry without repair or removal.
The [backup/restore API](backups.md) removes this marker only after complete copy
verification and synchronization. Existing unmarked version-1 stores remain supported.
Opening checks the SQLite header and fixed schema before any connection that could
recover journals or change files. A read-only immutable connection reads only the
main-file version and schema for this gate. Complete DDL matching checks required
columns, primary/unique keys, foreign keys, state checks and the kind/state trigger;
a matching version alone is insufficient. Unsupported/zero versions and malformed
layouts fail unchanged. Extra schema objects are unsupported too.

This gate relies on the schema/version never changing after initialization and
on absence of WAL. It deliberately ignores hot journals and must never be used for
live data, head/receipt queries, integrity conclusions or recovery. After the gate,
the operational connection uses a correctly encoded SQLite URI with `mode=rw`,
allowing legitimate version-1 hot rollback journal recovery. WAL headers/sidecars
and unsafe rollback-journal objects are rejected without conversion.

Connections use rollback-journal `DELETE`, `synchronous=EXTRA`, `foreign_keys=ON`
and a fixed 5000 ms busy timeout, checking the effective values and failing rather
than weakening them. Autocommit mode (`isolation_level=None`) is paired with
explicit `BEGIN`, `COMMIT` and `ROLLBACK`; writes use `BEGIN IMMEDIATE`.
This is single-host local storage. Network filesystems, WAL, distributed storage,
general migrations and concurrent external mutation are unsupported. Durability
assumes trusted storage ownership and working filesystem/device synchronization;
it is not protection from a hostile owner. The separate
[verified local backup API](backups.md) supplies consistent capture and restoration.

## Atomic submission, exact links and recovery

Inside the serialized write transaction, submission identity is checked **before**
heads, references or current artifact availability. Identical canonical text returns
the original receipt without any metadata changes or another event, even after a
later revision advances. Different text conflicts atomically. Only affected
identities' expected heads are compared; unrelated events never invalidate them.

All proposed exact revisions are indexed before resolution. A link may point to an
old committed revision or any member of the batch, independent of record order.
Forward links, self references and cycles are allowed as descriptive relationships;
there is no topological sorting, scheduling or deductive-support validation. Old
references never drift to latest heads. Optional declared target kinds must match.

Before any metadata write, every distinct attached digest/size is fully verified
and file-synchronized, followed by its objects-directory barrier; inconsistent
sizes for one digest fail. This also closes the gap from a publisher interrupted
before its directory sync. The operation does not repair or overwrite objects.
Publication must already have occurred through `put_artifact`; submissions accept
references, never paths, downloads or bytes to publish implicitly.

Submission registration, new identities/revisions, ordered record/artifact links,
artifact registrations, relevant head advances and exactly one attributed event
commit together. All revisions precede link insertion so forward links work.
Historical revisions are never updated/deleted, and replacement writes are not used.
Pre-commit failures roll back the entire batch. If rollback cannot restore a usable
connection, the handle is invalidated. Published orphans and interrupted staging
entries are retained, with no automatic destructive cleanup.

Successful `COMMIT` ends rollback handling. An error or termination afterward may
lose acknowledgment while leaving the whole batch committed. Errors around COMMIT
can also leave the outcome uncertain. **Reopen and query the original submission
identity**, then retry exactly that request if needed; never invent a new identity
to reconcile uncertainty. Exact retries do not add events or revisions.

`get_revision`, `history` and `read_artifact` verify actual attached object bytes,
including type, size and hash, before successful exposure. Missing, corrupt,
truncated, unsafe or wrong-size objects fail usefully. Exact record links are
locators only: they do not imply transitive target artifact availability or
scientific validity. Fetching a target checks its own direct attachments.

`head`, `get_submission`, `audit_events` and exact duplicate responses are explicitly
**metadata-only**. They remain available if artifacts are later damaged, so callers
can establish whether a transaction committed. A durable receipt acknowledges a
historical metadata commit, not continuing evidence availability. No availability
success flag, automatic repair or new event is created by these reads/retries.

## Runnable local example

Run from the repository root. The explicitly selected temporary runtime is outside
source; its removal is example lifecycle management, not a storage cleanup API.

```bash
PYTHONPATH="$PWD/implementation/src" /home/francesco/miniconda3/bin/python3 -B - <<'PY'
from pathlib import Path
from tempfile import TemporaryDirectory
from research_pipeline.domain import CreationProvenance, RecordEnvelope, RecordReference, Submission
from research_pipeline.store import RecordStore

creator = CreationProvenance("graph-author", "2026-10-30T12:00:00Z", {"synthetic": True})
controller = CreationProvenance("local-controller", "2026-10-30T13:00:00Z")
with TemporaryDirectory(prefix="graph-runtime-", dir="/tmp") as temporary:
    root = Path(temporary) / "records"
    with RecordStore.create(root) as store:
        artifact = store.put_artifact(b"vertices: a,b,c; edges: a-b,b-c\n")
        context = RecordEnvelope("graph", 1, "research_context",
                                 {"vertices": ["a", "b", "c"]}, creator)
        claim = RecordEnvelope("connected", 1, "claim",
                               {"statement": "The graph is connected"}, creator,
                               [RecordReference("graph", 1, "uses_context", "research_context")],
                               [artifact], scientific_disposition="provisional")
        batch = Submission("graph-initial", controller, [claim, context], {"connected": 0, "graph": 0})
        receipt = store.submit(batch)  # Forward reference resolves regardless of list order.
        updated = RecordEnvelope("graph", 2, "research_context",
                                 {"vertices": ["a", "b", "c", "d"]}, creator)
        store.submit(Submission("graph-append", controller, [updated], {"graph": 1}))
    with RecordStore.open(root) as store:
        assert store.history("graph") == (context, updated)
        assert store.get_revision("connected", 1).record_references[0].revision == 1
        assert store.head("graph") == 2
        assert store.get_submission("graph-initial") == receipt
        assert store.submit(batch) == receipt  # Original identity, even after head advancement.
        assert len(store.audit_events()) == 2
        assert store.read_artifact(artifact) == b"vertices: a,b,c; edges: a-b,b-c\n"
PY
/home/francesco/miniconda3/bin/python3 -B implementation/scripts/validate.py
```

The permanent validator discovers existing tests plus real SQLite integration tests.
Tests use temporary stores, source-local fresh interpreters with `-B` and
`PYTHONDONTWRITEBYTECODE`, bounded timeouts and checked exit codes. A private no-op
fault seam identifies `before_metadata` (after artifact verification),
`after_first_revision` (after real partial writes), and `after_commit` (before
acknowledgment). Tests inject ordinary failures and abrupt `os._exit` termination,
including page spill/hot-journal recovery and fresh-process receipt reconciliation.
They exercise exact/conflicting retries, relevant-head contention, immutable
history, retained orphans, canonical types/order and later artifact damage.
These local results are advisory; controller validation and Reviewer verification
remain authoritative, and implementation submission is separate from acceptance.

## Remaining scope

Full scientific payload schemas and remaining record kinds, assessment/support
freshness, eligibility and promotion, actual worker isolation, attempt leases and
fencing, resource authorization/accounting, general migrations, periodic
scheduling, research-run/session/job recovery, distributed execution and research execution remain unsupported.
There is no duplicate resource charging guarantee without a ledger. This slice
completes neither overall M0-E, M0-S, M1, D02, the full product nor scientific
validation. M0-S gates scientifically dependent evaluation, qualification and
release, not independent storage engineering; all scientific obligations remain.
