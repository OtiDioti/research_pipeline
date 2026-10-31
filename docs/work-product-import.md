# Work-product preview and explicit import

Import directly from `research_pipeline.work_product_import`. This is a trusted
controller/library boundary, with no CLI, package re-exports or authenticated worker
endpoint. Preview verifies the canonical base, captures explicit inert draft bytes,
publishes immutable artifacts and checks typed admission in a read snapshot. It
returns a frozen proposal and explanatory summary. It writes no application metadata:
records, heads, submissions, receipts and events remain unchanged.

```text
prepare_work_product_import(
    source: RecordStore, base: RecordReference, checkout_directory, *,
    expected_head: int, metadata: dict, selected_paths, submission_id: str,
    record_provenance: CreationProvenance,
    submission_provenance: CreationProvenance,
    source_root, protected_roots,
    max_file_bytes: int, max_total_bytes: int, max_files: int,
    max_descriptor_bytes: int, max_inventory_entries: int,
) -> PreparedWorkProduct

dumps_prepared_submission(Submission) -> str
loads_prepared_submission(str | bytes) -> Submission

# Separate explicit commit:
source.submit_typed(prepared.submission)
```

`PreparedWorkProduct.submission` returns a fresh detached `Submission` on each
access. `PreparedWorkProduct.summary` returns a fresh JSON dictionary; mutating
nested returned values cannot change the stored result. The proposal preserves the
supplied identity and both explicit provenance values. No timestamp, authorship,
revision or permission is inferred from filenames or the descriptor.

## Exact inputs and canonical base

`base` retains checkout's `checkout_base` relationship and
`work_product_manifest` target kind. `expected_head` is an ordinary positive integer
equal to `base.revision`. The proposal appends the same identity at revision
`base.revision + 1`, with that exact base as `supersedes` and the matching expected
head. Preparation checks current CAS; a subsequent advance can still make commit
raise `RevisionConflictError`. It never silently rebases. Reconcile edits explicitly
against a new canonical base and prepare with a distinct proposal ID.

`metadata` is a complete ordinary JSON dictionary with **exactly** these fields,
using the [manifest serialized types](work-products.md), explicit nulls/arrays and
complete nested references:

```text
product_kind, title, purpose, authors, task, branch, context, run,
linked_claims, linked_sources, build_dependencies, entry_file, limitations
```

`selected_paths` is an explicit nonempty list/tuple of logical path strings in
proposed manifest order. Each string is also its exact checkout-relative source
path. There are no globs, source mappings or descriptor-derived selections.
Omitted base paths are removed from the proposal even if still present on disk;
a rename is an explicit removal and addition. `entry_file` must exactly equal a
selected path. All portable path, NFKC/casefold alias and prefix-collision rules
apply before opening selected files. The `.work-product` namespace and its portable
aliases are reserved. Ordering is preserved for files, authors and all links.

`source_root` and the explicit list/tuple `protected_roots` are trusted caller
exclusions, with the selected runtime automatically included. Overlap in either
direction is refused. Supply external backup, Git and controller locations too.
Ancestors are traversed without following symlinks; recognizable storage/control
layouts are refused, allowing only this checkout root's expected control directory.
The descriptor never selects a runtime, identity, exclusion or source path.

Preparation obtains the exact base envelope through a metadata-only transaction,
decodes it and bounds its full logical inventory **before reading originals**. All
direct originals are verified, including those removed from the proposal. No build
dependency traversal or transitive attachment reads occur. Existing typed admission
checks are reused in a read snapshot: exact references, kinds, CAS, direct object
availability, constrained context/claim/supersession closure and shallow generic
roles retain their accepted semantics. Review `context_manifest` and manifest build
dependencies remain shallow. A malformed constrained historical base cannot be
made acceptable by omitting its bad references in the proposed revision.

The complete local base/envelope must equal the canonical caller-pinned
`CheckoutInfo` under canonical serialization. Coherent title, attribution, hash or
identity edits to the descriptor fail; booleans cannot masquerade as integers.
Controls, descriptor signatures and root/ancestor bindings remain pinned through
return. Missing controls, any incomplete marker, unexpected control entries, unsafe
types and observed descriptor replacement fail. Preparation never edits controls.
Declared authorship and local descriptors are **not authentication**.

## Bounds, capture and unselected material

All five limits are required finite ordinary integers; booleans/floats/nulls are
invalid. File/total bytes may be zero, while file counts, descriptor bytes and
inventory entries must be positive. `max_files`, `max_file_bytes` and
`max_total_bytes` independently bound both the entire canonical base inventory and
the proposed selection. Repeated logical paths holding equal bytes count separately.
Sizes are checked before allocation, total selected bytes are bounded incrementally,
and reads use bounded chunks up to observed size with at most a one-byte EOF probe.
Only one bounded file is buffered for `source.put_artifact`; references and signatures
are retained afterward. There is no new artifact storage or streaming API.

Selected files must be owned regular files with one link, owner-read permission,
no group/world write bits and no special mode bits. Ordinary `0600`/`0644` files and
owner-controlled executable files are allowed. Execute bits never trigger execution.
Selected product directories, including newly created nested directories, must be
owned private **`0700`** directories. Create them with `mkdir(mode=0o700)` and retain
that mode. Import does not chmod files or directories for you.

Parent-relative no-follow/nonblocking opens and preopen lstat/open fstat comparison
reject symlinks, FIFOs, devices, sockets, hard links and directory leaves before
consuming bytes. Held descriptors and final name/signature checks detect observed
replacement (even with equal bytes), growth, truncation, in-place changes, changes
to earlier files while reading later ones, and root/ancestor/control rebinding.
These checks cannot defeat arbitrary same-owner hostile mutation or privileged
processes; this is not a hostile-owner sandbox.

Unselected entries are reported without reading their contents. Enumeration visits
only the root and directories needed by selected paths. Unvisited directories are
reported as **opaque subtrees**, never recursively searched; omitted base files still
on disk appear individually in visited directories or under an opaque parent.
Symlinks are reported without following them. Only the exact validated root control
directory is excluded from the report. `max_inventory_entries` counts all encountered
entries in visited product directories, including that control entry, and fails
explicitly on overflow. Each recheck is bounded by the same limit. Membership and
entry/directory signatures are rechecked before return. The report describes observed
material and opaque subtrees, not a recursive content audit.

Failures leave selected and unselected draft material untouched. Immutable orphan
objects can remain after later failure; there is no cleanup or source repair.
Artifact publication retains its existing failure semantics and chained causes.
Filesystem failures use checkout's `CheckoutLayoutError`, `CheckoutIntegrityError`
and `CheckoutOperationalError`; malformed inputs use `DomainValidationError`, and
store admission errors retain their existing types. A used submission ID is refused
with an instruction to retry the saved proposal directly. Preparation neither
reserves IDs nor emits receipts/events.

## Summary and frozen proposal formats

The deterministic summary has exactly these top-level fields:

| Field | Shape and meaning |
| --- | --- |
| `base` | Complete original `checkout_base` reference |
| `proposed_revision` | Proposed integer revision |
| `paths` | Ordered objects `{path, status, old, new}`; base order followed by additions in selection order |
| `old_files`, `new_files` | Ordered lists of path strings; expose ordering-only changes |
| `metadata_changes` | Changed metadata field names mapped to `{before, after}` |
| `provenance_changes` | Changed `record` and/or `submission` provenance mapped to `{before, after}`; submission baseline is the canonical base's original submission |
| `structural_changes` | `revision` and `supersedes`, each `{before, after}` |
| `unselected_material` | Sorted objects `{path, path_escaped, kind, opaque}` |

Path status is `added`, `removed`, `changed` or `unchanged`. `old` and `new` are
`{digest, size}` or null. Equality means exact digest and size equality for both text
and binary; no semantic equivalence or text diff is claimed. Metadata differences
preserve ordering, explicit nulls and integer/boolean distinctions. `kind` in the
unselected report is `file`, `directory`, `symlink` or `other`; `opaque` is true only
for unvisited directories. Non-scalar filesystem names are displayed as the inside
of an ASCII JSON string (without enclosing quotes) and marked `path_escaped=true`.
Ordinary scalar names retain their exact display and `path_escaped=false`.
The summary is explanatory and is never consumed as commit authority.

The frozen proposal wrapper has exactly:

```text
{
  "format": "research_pipeline.work_product_import_submission",
  "version": 1,
  "submission": <complete existing Submission.to_dict() representation>
}
```

Encoding is compact, sorted-key ASCII JSON; arrays retain their order. Loading and
dumping are pure and require one coherent work-product envelope with non-null
immediate-predecessor supersession and matching expected head. All nested serialized
fields are explicit, including defaults and nulls. Duplicate fields at every depth,
unknown versions/fields, omitted fields, coercion, invalid UTF-8, non-scalar Unicode
and nonfinite numbers are rejected. This is a proposal-file format, not a new
storage schema or fingerprint algorithm. Neither operation accesses checkout/storage
or generates IDs/timestamps.

## Durable proposal, explicit commit and recovery

**Preserve the serialized proposal before attempting commit.** Exclusively create an
explicit ordinary proposal file outside checkout controls, flush/fsync it and its
parent, then reload it before submitting. The library does not persist proposals
automatically. The example chooses a private sibling file outside the draft.

Call only `RecordStore.submit_typed(saved_submission)` to commit. Do not add draft,
base or artifact availability checks in front of this retry operation. Existing
original-ID reconciliation occurs before CAS and availability checks. Identical
retries return the original receipt after checkout edits/deletion, later head
advances, artifact loss/damage and lost acknowledgment, without replay or duplicate
events. A changed request under the same ID raises `SubmissionConflictError`,
including changes to content, provenance or order. New edits need a new proposal ID.
Preparation is not the retry operation.

Before-metadata and mid-transaction interruption leave no committed proposal metadata
(after normal journal recovery). Post-COMMIT interruption can lose the acknowledgment
while the original receipt is committed. Reopen and submit the **identical saved ID
and request** to reconcile either outcome. Retained drafts and published orphan
objects remain available. Existing backup/exact restore preserves imported history,
links, provenance, old/new bytes and original receipts without replay. Generic
persistence still preserves malformed/unsupported typed-looking history; typed reads
reject it.

Nothing here refreshes views, executes/imports dependencies or content, deletes
drafts, promotes claims or repairs source files. D02 remains partial. Scientific
sufficiency, detailed execution/TeX/checkpoint/run-report contracts, full vault/intake
and worker authorization remain deferred. The synthetic oscillator retains its
original v1.3 provenance.

## Runnable round-trip example

Run with candidate `implementation/src` on `PYTHONPATH`. Tests execute this exact
block in fresh Python with bytecode disabled. The temporary software and protected
roots stand in for real caller-owned trusted exclusions.

```python
import os
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory

from research_pipeline.checkout import checkout_work_product
from research_pipeline.domain import CreationProvenance, RecordReference, Submission
from research_pipeline.store import RecordStore
from research_pipeline.work_product import WorkProductFile, WorkProductManifest, encode_envelope
from research_pipeline.work_product_import import (
    prepare_work_product_import, dumps_prepared_submission, loads_prepared_submission,
)


def metadata_snapshot(runtime):
    """Read every application table to demonstrate that preview changes no metadata."""
    with sqlite3.connect(runtime / "metadata.sqlite3") as connection:
        tables = connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
        ).fetchall()
        return {name: connection.execute('SELECT * FROM "' + name + '" ORDER BY rowid').fetchall()
                for (name,) in tables}


creator = CreationProvenance("author", "2026-10-30T12:00:00Z", {"source": "synthetic"})
editor = CreationProvenance("editor", "2026-10-30T13:00:00Z", {"reason": "explicit edit"})
controller = CreationProvenance("controller", "2026-10-30T13:01:00Z", {})
with TemporaryDirectory(prefix="work-product-import-example-") as temporary:
    parent = Path(temporary)
    runtime, draft = parent / "runtime", parent / "draft"
    source_root, protected = parent / "software", parent / "external-controls"
    source_root.mkdir(mode=0o700)
    protected.mkdir(mode=0o700)
    limits = dict(source_root=source_root, protected_roots=[protected],
                  max_file_bytes=1024, max_total_bytes=4096,
                  max_files=10, max_descriptor_bytes=65536)
    with RecordStore.create(runtime) as store:
        old_text = store.put_artifact("Original α\n".encode())
        binary = store.put_artifact(b"\x00\xff")
        product = WorkProductManifest(
            product_kind="note", title="Synthetic bundle", purpose="Demonstrate explicit import",
            authors=["Declared author"], task=None, branch=None, context=None, run=None,
            linked_claims=[], linked_sources=[], supersedes=None, build_dependencies=[],
            files=[WorkProductFile("note.txt", old_text), WorkProductFile("data.bin", binary)],
            entry_file="note.txt", limitations=["No scientific validation"],
        )
        initial = encode_envelope("bundle", 1, product, creator)
        store.submit_typed(Submission("initial", controller, [initial], {"bundle": 0}))
        base = RecordReference("bundle", 1, "checkout_base", "work_product_manifest")
        checkout_work_product(store, base, draft, **limits)
        captured_text = "Explicit edited α\n".encode()
        (draft / "note.txt").write_bytes(captured_text)
        (draft / "extra.txt").write_bytes(b"Unselected material remains here")
        (draft / "new").mkdir(mode=0o700)
        empty_fd = os.open(draft / "new/empty", os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        os.close(empty_fd)
        proposed_metadata = dict(
            product_kind="note", title="Edited synthetic bundle", purpose=product.purpose,
            authors=["Declared editor"], task=None, branch=None, context=None, run=None,
            linked_claims=[], linked_sources=[], build_dependencies=[], entry_file="note.txt",
            limitations=["No scientific validation"],
        )
        before = metadata_snapshot(runtime)
        prepared = prepare_work_product_import(
            store, base, draft, expected_head=1, metadata=proposed_metadata,
            selected_paths=["note.txt", "new/empty"], submission_id="explicit-edit-1",
            record_provenance=editor, submission_provenance=controller,
            max_inventory_entries=100, **limits,
        )
        assert metadata_snapshot(runtime) == before
        assert [item["status"] for item in prepared.summary["paths"]] == ["changed", "removed", "added"]
        assert (draft / "data.bin").read_bytes() == b"\x00\xff"
        assert (draft / "extra.txt").read_bytes() == b"Unselected material remains here"

        # Explicitly chosen ordinary sibling file; exclusive create, then durable barriers.
        proposal_path = parent / "explicit-edit-1.proposal.json"
        with proposal_path.open("x", encoding="ascii") as stream:
            stream.write(dumps_prepared_submission(prepared.submission))
            stream.flush()
            os.fsync(stream.fileno())
        parent_fd = os.open(parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            os.fsync(parent_fd)
        finally:
            os.close(parent_fd)
        saved = loads_prepared_submission(proposal_path.read_bytes())
        assert dumps_prepared_submission(saved) == dumps_prepared_submission(prepared.submission)
        (draft / "note.txt").write_bytes(b"Later local edit, outside the saved proposal")
        assert metadata_snapshot(runtime) == before

        # EXPLICIT COMMIT: the saved request is the entire input, with no draft reread.
        receipt = store.submit_typed(saved)
        committed, value = store.get_typed_revision("bundle", 2)
        assert store.read_artifact(value.files[0].artifact) == captured_text
        assert committed.provenance == editor
        assert value.supersedes == RecordReference("bundle", 1, "supersedes", "work_product_manifest")
        assert store.get_revision("bundle", 1) == initial
        assert store.read_artifact(old_text) == "Original α\n".encode()
        assert (draft / "note.txt").read_bytes() == b"Later local edit, outside the saved proposal"
        assert store.submit_typed(saved) == receipt
        assert len(store.audit_events()) == 2
    with RecordStore.open(runtime) as reopened:
        assert reopened.submit_typed(loads_prepared_submission(proposal_path.read_bytes())) == receipt
```

Preserved direct view edits can enter this explicit route using the exact historical
record/revision and logical path in the [readable refresh continuation](readable-refresh.md).
Refresh itself never previews or imports; stale expected bases conflict without rebasing.
