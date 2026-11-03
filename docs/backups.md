# Verified local backup and restoration

`research_pipeline.backup` provides an explicit trusted-controller boundary for
schema-1, schema-2 and schema-3 `RecordStore` data. Import directly from this submodule. Imports are
inert; there is no CLI, dependency, environment-selected location, scheduler,
worker endpoint or general SQL interface. Callers select paths outside software
source, relative to their working directory or absolute, under existing parents.
Parent-traversal components and symlinked ancestors are rejected, not resolved.

| Signature | Result and effects |
| --- | --- |
| `create_backup(source: RecordStore, destination) -> BackupInfo` | Capture an open, owning-thread source without an active transaction into an absent destination. |
| `inspect_backup(root) -> BackupInfo` | Verify a complete backup without recovery, writes, permission changes or sidecars. |
| `restore_backup(root, destination, *, target_schema=None, migration_provenance=None) -> RecordStore` | Verify before reserving an absent runtime; restore exactly by default or explicitly migrate v1→v2 or v2→v3. Return an independent handle after publication barriers. Close it or use a context manager. |

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

A complete backup of either supported version contains exactly:

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

Only `(format_version, schema_version)` pairs `(1, 1)`, `(2, 2)` and `(3, 3)` are supported.
The example shows the historical format-1 representation; format 2 has the same
four exact fields and reference shapes with both version values set to 2.
Schema3 uses the same shape with both versions set to 3 and includes its entire ledger.
Legacy canonical serialization and `backup_id` hashing are unchanged. Crossed
pairs, unknown versions and disagreement with the actual database are rejected.
Capture selects its version from the captured snapshot, never from live state.

Versions and sizes must be ordinary integers, excluding booleans. Artifact entries
are digest-sorted and unique, with exactly `digest` and `size` fields; no entry
provides a path. Metadata always names `snapshot.sqlite3`. Empty inventory is
valid. UTF-8 JSON parsing rejects duplicate keys at every depth, nonfinite numbers,
unknown/missing fields, invalid scalar types and unsupported versions. Extra root
entries, SQLite sidecars, extra objects and nonempty `.staging` are rejected.

Inspection checks the actual snapshot digest and size, standalone DELETE-journal
header, exact version-specific DDL gate, SQLite integrity and foreign keys.
The manifest schema must equal the actual metadata schema. Canonical request
kinds and declared reference kinds must be allowed by that schema, so the broader
domain does not weaken legacy verification. It reconstructs
strict canonical submission requests and fingerprints and compares every ordered
normalized revision and link against them, keeping `1`, `1.0` and `true` distinct.
It checks original event attribution/timestamps, membership, head expectations,
stable kinds, contiguous revision histories and chronological target availability.
Same-batch forward/self/cyclic links remain valid. Domain constructors validate
common fields; no scientific payload schema is invented. No submissions are
replayed and no receipts regenerated. Historical references, registrations,
manifest entries and actual object names/sizes must agree exactly; every object's
actual bytes are verified.

Typed scientific and assessment graphs use these unchanged generic backup mechanics: canonical
requests, ordered links, original provenance, receipts and events survive restore
without replay or promotion. Inspection does not decode scientific or assessment
payloads. Legacy generic records and unsupported typed versions remain preserved; explicit
`get_typed_revision` rejects unsupported versions without rewriting them. Capture
before intentional artifact damage because all historical objects must be healthy.
After restore, later byte loss still leaves exact `submit_typed` retry and
metadata-only receipt reconciliation available.

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
Default restoration is exact: each supported schema yields the same schema,
with original metadata bytes, identities and receipts. Schema3 also retains all
resource operations, allocations, original reservations, cumulative observations,
reconciliations, policies, sticky breaches and outstanding liabilities. Restored v1
stores accept old-kind appends and reject v2-only submitted or declared reference
kinds with a migration-required `DomainValidationError`. Restored v2 stores accept
all twenty generic kinds. Neither path changes the backup or source.

## Explicit verified migration

Supported migrations are verified format-1/schema-1 backups into absent schema2
runtimes and verified format-2/schema-2 backups into absent schema3 runtimes.
Supply the next `target_schema` (`2` or `3`) and
`migration_provenance=CreationProvenance(actor, created_at, details)` explicitly.
The actor and UTC timestamp are caller supplied; details may be `{}`. Attribution
is reconstructed and validated at the API boundary and serialized canonically.
No operator, timestamp, migration request or scientific authority is inferred.

Both options default to `None`, selecting exact restoration. `BackupLayoutError`
rejects provenance without a target, missing or malformed attribution with a
target, and targets other than ordinary integers `2` and `3` (including booleans,
strings and floats). Direct 1→3, same-version migrations, downgrades and every
explicit target on a schema3 source are rejected. Invalid options and damaged backups
fail before destination reservation. There is no live in-place migration,
automatic upgrade on open, public v1 creation option or general conversion API.

After full read-only source verification, restore reserves the destination and
durably writes `.restore-incomplete`. It independently copies/verifies artifacts,
copies the snapshot into private metadata, compares its original digest/size and
verifies the copied source database. Only that unpublished copy is opened for migration,
using the existing bounded SQLite DELETE-journal/EXTRA connection settings.
The backup is never written, chmodded or attached to a writable connection.

For 1→2, one `BEGIN IMMEDIATE` transaction saves the exact identities and record links in
connection-local temporary tables, drops/recreates those main tables and the
state trigger using registered v2 DDL, and copies named SQL columns back. It adds
the administrative history row and sets `user_version=2`. Historical JSON text,
NULLs, IDs, ordinals, revisions, events, requests and receipts remain unchanged;
no submissions are replayed. Foreign-key enforcement is temporarily disabled
outside the transaction only on this unpublished private connection to replace
the mutually dependent tables without renaming them. Exact main-schema validation,
explicit `foreign_key_check`, application checks and strict history validation
must succeed before COMMIT. Enforcement is restored and checked after COMMIT.
Exceptions roll back an active transaction and close the connection; failed or
uncertain commits never permit publication.

After closing the migration connection, restore requires a standalone database
without sidecars, verifies the target schema/application/history (and schema3 ledger) and exactly the source
artifact inventory, rechecks object bytes and synchronizes metadata, objects and
directories. The migrated metadata digest is expected to change; history retains
the original source digest. Only then may marker removal publish the copy.

Schema 2's separate `migration_history` table is empty on fresh creation. If
present, its singleton administrative row records `migration_id=1`,
`source_schema=1`, `target_schema=2`, `source_backup_id`, `source_manifest_json`,
and `provenance_json`. The complete canonical legacy source manifest retains the
source metadata digest/size and artifact inventory, and hashes to the recorded
source backup identity. Attribution requires explicit actor, canonical UTC time
and details. Strict duplicate-free finite JSON, exact manifest fields/order,
canonical text, and matching current source-artifact registrations are verified.
Later registrations are allowed. This is internal consistency, not external
authentication. Inspection validates it on the standalone snapshot; open validates
live history after legitimate journal recovery. Exact backup/restoration preserves
these values without inserting a submission or scientific event. Migration writes
this row separately from original creation attribution; it never relabels old
records as v2 creations. The source manifest is reconstructed canonically from
verified `BackupInfo` and checked against its `backup_id`, independently of outer
manifest whitespace. No public arbitrary history insertion API exists.

For 2→3, one `BEGIN IMMEDIATE` transaction copies the six original history columns
through a temporary SQL table, replaces only `migration_history`, restores every
original value, appends an attributed 2→3 row, creates the resource tables/indexes
empty and sets `user_version=3`. No scientific table is rewritten. Foreign keys
remain enabled. Exact schema, scientific application, foreign-key, ordered history
and ledger checks precede COMMIT and are repeated before publication.

Schema3 permits exactly these ordered histories: empty (fresh3), `(1,2,3)` for
fresh2→3, or `(1,1,2)` followed by `(2,2,3)` for historical1→2→3, where each tuple
is migration ID/source/target. Every row retains its exact source backup identity,
canonical complete manifest (including original metadata digest/size) and explicit
provenance. Exact schema3 restore copies metadata unchanged; it does not reconstruct
a ledger or insert another administrative row.

Live schema3 open validates the ledger after legitimate journal recovery. Immutable
backup inspection validates strict canonical resource requests/results, fingerprints,
normalized projections, ordered reference watermarks, hierarchy, inherited policies
including mandatory handoff provisioning bounds, and historical admission capacity.
The same shared validator is used for ledger inspection. Resource references do not
register artifacts; exact registration-versus-historical-scientific-links closure
remains mandatory, with no orphan exception. See [resource accounting](resource-accounting.md)
for a runnable usage, settlement, breach, explicit 2→3 and exact-restore example.

Schema3 usage and reconciliation append to the existing operation log without a DDL
or schema-identity change. Live open recovers legitimate hot journals before replay;
immutable backup inspection performs no recovery. The shared validator reconstructs
cumulative lower bounds, settlement predecessors/evidence, external receipt identity,
remaining liability, exact decimal aggregate totals and sticky project-wide breach
gates at each historical sequence. Valid breached ledgers and totals above `2**63-1`
remain inspectable, exportable and exactly restorable; later breaches do not invalidate
earlier valid admissions. Rehashed bytes cannot conceal impossible history. These
checks establish internal consistency, not hostile-owner authentication. Scientific
outgoing-closure snapshots remain observations, not full runtime backups.

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
copied bytes and database without initialization, replay or VACUUM. Explicit
migration then follows the transaction and re-verification sequence above;
default restoration preserves exact metadata bytes.
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

This applies equally to mid-transformation interruption and a committed v2 copy
whose publication failed. Keep any journal and other partial files intact; public
open and inspection refuse the marker before recovery. There is no automatic
cleanup, repair or retry. If publication succeeded but opening the returned handle
fails, restore reports that a complete copy was published but opening failed.

| Error | Meaning |
| --- | --- |
| `BackupError` | Base for backup failures. |
| `BackupLayoutError` | Unsafe/incomplete layout, traversal, existing destination, unsupported format or invalid migration options/transition. |
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

## Runnable synthetic migration example

This demonstration uses `tests.legacy.historical_store` solely as source-local
support for constructing authentic v1 data. It is not a public v1 creation API
or evidence of a scientific run. It preserves generic/typed histories and original
receipts while explicitly attributing the administrative migration. The oscillator
fixture retains its original v1.3 provenance and is not involved here.

From the candidate repository root, set the two candidate-local import paths:

```bash
export PYTHONPATH="$PWD/implementation/src:$PWD/implementation"
export PYTHONDONTWRITEBYTECODE=1
```

Run the following Python block using `/home/francesco/miniconda3/bin/python3 -B`
from a working directory outside source. All runtime paths are explicit children
of a disposable `/tmp` directory. Cleanup is demonstration-owned. The focused
test extracts and executes this exact block in a bounded subprocess when the
controller runs validation; the documentation itself is not an execution claim.

```python
from pathlib import Path
from tempfile import TemporaryDirectory
from research_pipeline.backup import create_backup, inspect_backup, restore_backup
from research_pipeline.domain import CreationProvenance, RecordEnvelope, Submission
from tests.legacy import historical_store, table_values  # source-local fixture support only

with TemporaryDirectory(prefix="synthetic-migration-", dir="/tmp") as temporary:
    paths = Path(temporary)
    source, requests, artifact = historical_store(paths / "legacy")
    with source:
        original = table_values(paths / "legacy")
        histories = {row[0]: source.history(row[0]) for row in original["identities"]}
        receipts = [source.get_submission(item.submission_id) for item in requests]
        events = source.audit_events()
        typed = source.get_typed_revision("evidence", 1)
        legacy = create_backup(source, paths / "legacy-backup")
    assert (legacy.format_version, legacy.schema_version) == (1, 1)
    assert inspect_backup(paths / "legacy-backup") == legacy
    attribution = CreationProvenance("synthetic-migration-operator", "2026-10-30T14:00:00Z", {})
    with restore_backup(paths / "legacy-backup", paths / "upgraded",
                        target_schema=2, migration_provenance=attribution) as upgraded:
        assert table_values(paths / "upgraded") == original
        assert upgraded.audit_events() == events
        for identity, history in histories.items():
            assert upgraded.history(identity) == history
        assert upgraded.get_typed_revision("evidence", 1) == typed
        for item, receipt in zip(requests, receipts):
            assert upgraded.submit(item) == receipt
        assert upgraded.submit_typed(requests[2]) == receipts[2]
        assert upgraded.audit_events() == events
        p = CreationProvenance("synthetic-author", "2026-10-30T15:00:00Z")
        project = RecordEnvelope("new-project", 1, "project", {"synthetic": True}, p)
        upgraded.submit(Submission("new-project-submission", p, [project], {"new-project": 0}))
        assert upgraded.get_revision("new-project", 1) == project
        exported = create_backup(upgraded, paths / "v2-backup")
    assert (exported.format_version, exported.schema_version) == (2, 2)
    assert inspect_backup(paths / "v2-backup") == exported
    assert inspect_backup(paths / "legacy-backup") == legacy
```

Migration tests also compare all seven historical tables, independent inodes and
unchanged source bytes; exercise real mid-DDL rollback and abrupt exits, committed
but incomplete copies, metadata/directory synchronization and marker failures;
and carry a v1 post-COMMIT lost acknowledgment through migration and a v2 exact
restore. Administrative corruption tests rehash outer snapshots so application
and history checks must still reject them. These are bounded local integrity
checks, not authentication of a coherent hostile-owner rewrite.

General migrations, periodic scheduling, complete D02/R-019/R-017 fulfillment,
research-run/session/job recovery, scientific validation, full scientific schemas,
assessment freshness/eligibility, attempt lifecycle, worker isolation and live-provider work
remain outstanding. M0-S and the original historical fixture/provenance are unchanged.

## Operating authority and external current trust

[Operating decisions](operating-authority.md) are ordinary immutable submission
history and survive exact backup/restore. Host credentials and current authorization
policy are never backup inputs. Without externally supplied verification material,
restored history can be inspected but cannot establish current permission.

An older backup cannot discover or reconcile later omitted revocations. Before any
future dispatch, restart must supply current external denying policy or credential
withdrawal and resolve the restored snapshot. Retaining public policy fingerprints
does not authenticate key bytes or reconstruct current trust. Resource history is
restored independently; operating approvals and reductions do not reset it.

## Committed lifecycle sources

[Lifecycle source submissions](committed-lifecycle-sources.md), source artifacts,
scientific rows, original receipts and pending control/resource histories are ordinary
immutable runtime state preserved by healthy exact backup/restore. No new backup
format or schema is introduced. Source metadata-only recovery can retain its historical
meaning after later object loss; a verified source read and a healthy backup require
all required bytes. A schema-2 source retains its original schema-2 resource-unavailable
observation after an allowed migration. Restoring a source never grants current
permission, discharges an obligation, publishes output or establishes restart readiness.
