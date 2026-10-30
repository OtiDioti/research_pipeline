# Validated envelopes and immutable artifacts

The implemented primitives provide domain-independent record values and durable
local artifact bytes. They support engineering work under specification v1.4;
they do not establish scientific validation or complete M0-E, M0-S, M1 or D02.
Controller acceptance and integration remain separate from implementation and test
results. The historical oscillator fixture, including its v1.3 provenance, remains
an intentionally separate paper example.

`research_pipeline.domain` owns validation and detached JSON serialization.
`research_pipeline.artifacts` owns filesystem layout, publication and integrity.
Imports are inert. Use direct submodule imports; no installation or package-level
re-exports are needed. The CLI still provides only help/version.

## Domain API

All four values are frozen and validate their constructors at runtime. Each has
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

A constructed record reference is syntactically valid only. Resolution, declared
kind comparison against actual targets, and cross-revision kind stability await
the transaction store. An artifact reference alone says nothing about current
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
Later integrity checks detect mutation; they provide neither scientific validity
nor backup guarantees.

## Runnable local example

Run from the repository root. The temporary runtime directory is explicitly
placed under `/tmp`, outside the source checkout. Its removal here is test/example
lifecycle management; the artifact API itself has no destructive cleanup operation.

```bash
PYTHONPATH="$PWD/implementation/src" /home/francesco/miniconda3/bin/python3 -B - <<'PY'
from pathlib import Path
from tempfile import TemporaryDirectory
from research_pipeline.domain import CreationProvenance, RecordEnvelope, RecordReference
from research_pipeline.artifacts import ArtifactStore

provenance = CreationProvenance(
    actor="graph-investigator", created_at="2026-10-30T12:00:00Z",
    details={"classification": "synthetic", "notes": ["engineering example"]},
)
with TemporaryDirectory(prefix="graph-runtime-", dir="/tmp") as temporary:
    root = Path(temporary) / "artifacts"
    artifacts = ArtifactStore.create(root)
    result = artifacts.put(b"vertices: a,b,c; edges: a-b,b-c\n")
    context = RecordEnvelope(
        record_id="graph-context", revision=1, kind="research_context",
        content={"vertices": ["a", "b", "c"], "edges": [["a", "b"], ["b", "c"]]},
        provenance=provenance,
    )
    claim = RecordEnvelope(
        record_id="connected", revision=1, kind="claim",
        content={"statement": "The graph is connected", "quoted_status": "supported"},
        provenance=provenance, scientific_disposition="provisional",
        record_references=[RecordReference("graph-context", 1, "uses_context", "research_context")],
        artifact_references=[result],
    )
    task = RecordEnvelope(
        record_id="inspect-graph", revision=1, kind="task_specification",
        content={"objective": "Inspect connectivity"}, provenance=provenance,
        operational_status="completed",
        record_references=[RecordReference("connected", 1, "investigates", "claim")],
    )
    assert RecordEnvelope.from_dict(claim.to_dict()) == claim
    assert task.operational_status == "completed"
    assert claim.scientific_disposition == "provisional"
    assert artifacts.read(result) == b"vertices: a,b,c; edges: a-b,b-c\n"
    reopened = ArtifactStore.open(root)
    reopened.verify(result)
    assert reopened.put(b"vertices: a,b,c; edges: a-b,b-c\n") == result
PY
/home/francesco/miniconda3/bin/python3 -B implementation/scripts/validate.py
```

Only artifact bytes persist in this example. Envelopes remain in-memory values;
there is no submission operation or durable submission idempotency yet. The
validator discovers the existing tests together with domain and artifact tests.
Those tests exercise real bytes, no-clobber races, corruption, and narrowly
injected publication/synchronization failures. They do not replace transaction
crash/restart evidence or controller verification.

## Remaining scope

The next milestone owns SQLite metadata, schema versioning, atomic submissions,
fingerprints, expected-head checks, persisted exact-reference resolution,
receipts/events and subprocess transaction-crash/recovery evidence. No placeholder
interfaces for these operations are exposed here.

Full scientific payload schemas and remaining record kinds, assessment/support
freshness, eligibility and promotion, actual worker isolation, attempt leases and
fencing, resource accounting, general migrations, verified backups/restoration,
and distributed execution remain unsupported. Engineering progress does not
certify scientific claims or remove scientific evaluation and release obligations.
