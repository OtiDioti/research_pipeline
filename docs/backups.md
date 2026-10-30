# Verified local backup and restoration

`research_pipeline.backup` provides an explicit trusted-controller boundary for
version-1 `RecordStore` data. Import directly from this submodule. Imports are
inert; there is no CLI, dependency, environment-selected location, scheduler,
worker endpoint or general SQL interface. Callers select paths outside software
source, relative to their working directory or absolute, under existing parents.
Parent-traversal components and symlinked ancestors are rejected, not resolved.

| Signature | Result and effects |
| --- | --- |
| `create_backup(source: RecordStore, destination) -> BackupInfo` | Capture an open, owning-thread source without an active transaction into an absent destination. |
| `inspect_backup(root) -> BackupInfo` | Verify a complete backup without recovery, writes, permission changes or sidecars. |
| `restore_backup(root, destination) -> RecordStore` | Verify before reserving an absent runtime, copy original bytes, and return an independently usable handle after publication barriers. Close it or use a context manager. |

`BackupInfo` is frozen and contains `backup_id: str`, `format_version: int`,
`schema_version: int`, `metadata: ArtifactReference`, and
`artifacts: tuple[ArtifactReference, ...]`. `backup_id` is SHA-256 of the canonical
manifest, not a new scientific identity. The manifest uses the same canonical
JSON convention as submissions: sorted mapping keys, compact separators, ASCII
escaping, finite strict JSON values. Harmless manifest whitespace and key order
do not change identity. This is integrity checking, neither scientific correctness
nor an externally authenticated signature. A coherently rewritten database and
manifest cannot be detected as an external-authority forgery.

## Format and verification

A complete version-1 backup contains exactly:

```text
backup/
  snapshot.sqlite3
  manifest.json
  objects/                 # exactly the distinct historically referenced digests
  .staging/                # empty
```

The snapshot and manifest are owned read-only regular files. Private owned
directories and read-only objects reuse `ArtifactStore` protections. The exact
manifest field set is:

```json
{"format_version":1,"schema_version":1,"metadata":{"digest":"<64 lowercase hex characters>","size":123},"artifacts":[{"digest":"<64 lowercase hex characters>","size":456}]}
```

Versions and sizes must be ordinary integers, excluding booleans. Artifact entries
are digest-sorted and unique, with exactly `digest` and `size` fields; no entry
provides a path. Metadata always names `snapshot.sqlite3`. Empty inventory is
valid. UTF-8 JSON parsing rejects duplicate keys at every depth, nonfinite numbers,
unknown/missing fields, invalid scalar types and unsupported versions. Extra root
entries, SQLite sidecars, extra objects and nonempty `.staging` are rejected.

Inspection checks the actual snapshot digest and size, standalone DELETE-journal
header, fixed version-1 DDL gate, SQLite integrity and foreign keys. It reconstructs
strict canonical submission requests and fingerprints and compares every ordered
normalized revision and link against them, keeping `1`, `1.0` and `true` distinct.
It checks original event attribution/timestamps, membership, head expectations,
stable kinds, contiguous revision histories and chronological target availability.
Same-batch forward/self/cyclic links remain valid. Domain constructors validate
common fields; no scientific payload schema is invented. No submissions are
replayed and no receipts regenerated. Historical references, registrations,
manifest entries and actual object names/sizes must agree exactly; every object's
actual bytes are verified.

## Capture boundary and continued use

Capture uses SQLite `Connection.backup` in finite 64-page steps with a small retry
sleep. A private monotonic five-second deadline bounds capture/retries and can
reject a snapshot that cannot finish in time. Existing source and restored
connections retain their accepted five-second lock settings. A source handle must
be open, used on its owning thread and have no active transaction.

Another connection may commit during capture; SQLite can restart incremental
backup. The successfully captured database is the snapshot boundary. Neither
operation-start time nor a wall-clock timestamp establishes which instantaneous
source state was selected. After capture closes its target connection, all metadata
and inventory decisions use that snapshot only. No source read transaction is
pinned during artifact copying; later source submissions can continue and do not
enter the captured inventory.

All historical revisions are retained, including artifacts referenced only by
older revisions. Committed rows, canonical requests, exact links, receipts, events
and original provenance are copied without rewriting. Source orphan objects,
`.staging` content, credentials/configuration and unrelated files are not copied.
There is no garbage collector and the source is unchanged. Artifact copying uses
the accepted full-byte-buffer API, so memory includes the largest artifact (and
buffered snapshot/manifest bytes). Copies have independent database/object inodes.
The restored runtime accepts ordinary new artifacts and submissions without changing
the backup or source.

## Completeness, errors and recovery

Destinations must be absent: existing directories, files and dangling symlinks are
preserved unchanged. Backup destinations inside their source runtime and restore
destinations inside their backup are rejected before reservation. Creation never
merges, overwrites, repairs or recursively removes a failed directory.

The reserved private directory is the operation's staging area. An exclusive,
synchronized `.backup-incomplete` or `.restore-incomplete` marker precedes any
metadata/manifest writing. A crash before marker creation leaves no usable metadata
or manifest. Backup inspection requires the exact complete layout. `RecordStore.open`
rejects any `.restore-incomplete` entry, including a dangling symlink or unsafe
entry, before schema inspection or an operational SQLite connection. It never
removes a marker. Existing version-1 stores without this marker remain supported.

Backup verifies and synchronizes the captured metadata, manifest and all referenced
objects and directories before removing its marker. Restore verifies the entire
backup **before** creating its destination, publishes durable artifacts first,
then copies the original snapshot into mode-0600 `metadata.sqlite3`. It checks the
copied bytes and database without initialization, replay, VACUUM or migration.
Restored objects remain read-only. Successful temporary-file removals and directory
changes are synchronized before completion; failed or older staging content is
never swept.

Atomic marker removal is the logical completeness boundary. Before that boundary,
failures retain an explicitly incomplete destination which inspection/open refuses.
After removal, destination and parent directory synchronization precede success.
If final synchronization or acknowledgment fails, an operational error reports
**uncertainty**: subsequent inspection may find a fully verified complete copy.
There is no promise to roll publication back. No partial content qualifies as
complete. Keep the failed path for diagnosis; choose a new absent destination if
retrying, and never remove a marker to make a failed copy usable.

| Error | Meaning |
| --- | --- |
| `BackupError` | Base for backup failures. |
| `BackupLayoutError` | Unsafe/incomplete layout, traversal, existing destination or unsupported format. |
| `BackupIntegrityError` | Invalid snapshot/application state, manifest, inventory, hash or size. |
| `BackupOperationalError` | Capture deadline, I/O, copy, sync or acknowledgment failure. Stages/paths/digests and useful causes are retained. |
| `StoreClosedError` | The supplied source handle was already closed. |

Reconcile a submission that lost acknowledgment by reopening the source and
looking up its **original submission ID**. An exact retry returns its original
receipt even after a later head advance; conflicting reuse fails without effects.
Backup and restore preserve this reconciliation identity. A failed/uncommitted
submission's orphan bytes stay in the source and are excluded from the backup.
This is submission recovery, not research-run/session/job recovery.

These guarantees assume reliable local POSIX file/directory `fsync`, no-follow
traversal, working SQLite/storage durability and trusted parents and owners with
no concurrent external mutation of managed files. Files are opened no-follow and
nonblocking and checked by descriptor before reading; SQLite subsequently opens
checked paths under that trusted-owner boundary. Immutable read-only connections
are used only for the stable standalone snapshot, never for live source data.
Hostile-owner protection, distributed/network filesystems and power-loss guarantees
beyond the tested barriers are not claimed.

## Runnable source-local example

Run from the repository root. All explicit runtime paths below are outside source;
cleanup belongs to this disposable example, not the product API.

```bash
PYTHONPATH="$PWD/implementation/src" PYTHONDONTWRITEBYTECODE=1 /home/francesco/miniconda3/bin/python3 -B - <<'PY'
from pathlib import Path
from tempfile import TemporaryDirectory
from research_pipeline.backup import create_backup, inspect_backup, restore_backup
from research_pipeline.domain import CreationProvenance, RecordEnvelope, Submission
from research_pipeline.store import RecordStore

p = CreationProvenance("synthetic-author", "2026-10-30T12:00:00Z", {"graph": {"vertices": ["a", "b"]}})
with TemporaryDirectory(prefix="verified-backup-", dir="/tmp") as temporary:
    paths = Path(temporary)
    with RecordStore.create(paths / "source") as source:
        artifact = source.put_artifact(b"a -> b\n")
        first = RecordEnvelope("graph", 1, "research_context", {"synthetic": True}, p,
                               artifact_references=[artifact])
        original = Submission("graph-initial", p, [first], {"graph": 0})
        receipt = source.submit(original)
        info = create_backup(source, paths / "backup")
    assert inspect_backup(paths / "backup") == info
    with restore_backup(paths / "backup", paths / "restored") as restored:
        assert restored.get_submission("graph-initial") == receipt
        assert restored.get_revision("graph", 1) == first
        extra = restored.put_artifact(b"a -> b -> c\n")
        second = RecordEnvelope("graph", 2, "research_context", {"synthetic": True}, p,
                                artifact_references=[extra])
        restored.submit(Submission("graph-next", p, [second], {"graph": 1}))
        assert restored.submit(original) == receipt
        assert restored.history("graph") == (first, second)
        assert restored.read_artifact(artifact) == b"a -> b\n"
    assert inspect_backup(paths / "backup") == info
PY
```

Focused tests exercise real incremental capture with a separate committing
connection, fresh-process inspection, damaged/rehashed metadata, unsafe filesystem
entries, partial writes, descriptor-selected sync failures, marker removal failure,
uncertain final acknowledgment and abrupt backup/restore interruption. A separate
end-to-end test recovers a durable submission after pre-acknowledgment process exit,
backs it up, restores and retries its original identity. Tests and local runs are
advisory; controller validation and Reviewer verification remain authoritative.

General migrations, periodic scheduling, complete D02/R-019/R-017 fulfillment,
research-run/session/job recovery, scientific validation, full scientific schemas,
assessment/eligibility, attempt lifecycle, worker isolation and live-provider work
remain outstanding. M0-S and the original historical fixture/provenance are unchanged.
