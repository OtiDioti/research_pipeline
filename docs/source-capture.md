# Bounded local Source capture

`research_pipeline.source_capture` is an explicit library boundary. Import it
directly; there is no CLI or package-level re-export. Preparation captures inert
selected bytes and checks admission, but only an explicit `store.submit_typed`
commits. The [Source codec](sources.md), existing typed-history rules, generic
payloads and work-product proposal format remain unchanged.

```python
prepare_source_capture(
    store: RecordStore, input_root, *, selected_files, metadata: dict,
    record_id: str, revision: int, expected_head: int, submission_id: str,
    record_provenance: CreationProvenance, submission_provenance: CreationProvenance,
    source_root, backup_roots, control_roots, max_file_bytes: int,
    max_total_bytes: int, max_files: int,
) -> PreparedSourceCapture

dumps_prepared_submission(submission: Submission) -> str
loads_prepared_submission(data: str | bytes) -> Submission
PreparedSourceCapture(submission: Submission, mapping: dict)
```

`PreparedSourceCapture.submission` reconstructs a fresh exact Submission on every
access. `mapping` returns a fresh ordinary dictionary. Both are internally stored
as canonical JSON snapshots, so caller mutations cannot change the prepared result.
The public constructor rejects an inconsistent mapping. Mapping is explanatory,
not authority to commit.

## Complete capture template and selection

`metadata` is an ordinary dictionary with exactly the existing Source constructor
fields: `work_id, upstream_identity, upstream_version, title, authors, provenance,
restrictions, originals, extractions, locations, reading, statements,
related_sources, supersedes, limitations`. It has no `format`, `version` or `kind`.
All values use the complete [Source wire representations](sources.md), with one
exception: each `originals` entry and each `extractions[*].outputs` entry contains
exactly `artifact_id, path, media_type, provenance`. Supplying computed `artifact`
or `original_mode` fields is an error. All other nested fields, nulls and arrays
are required. This template is preparation input, not another Source content codec.

`selected_files` is an explicit nonempty ordinary list/tuple of ordinary dictionaries
containing exactly `artifact_id` and `input_path`. IDs must equal the flattened
inventory order: all originals, then each extraction's outputs. There is exactly
one selection per inventory occurrence, with no duplicate IDs or physical paths.
`input_path` is the exact root-relative POSIX name to open; inventory `path` is its
independently declared portable logical name. Each inventory independently obeys
the existing portable alias/prefix-collision rules and the 4,096-character bound.
Traversal, absolute selections, alternate separators, normalization aliases and
file/directory prefix collisions fail; selected spellings are never normalized
into another filename. Distinct paths with identical bytes remain separate
inventory/provenance entries and count separately against all budgets.

Each inventory provenance must explicitly declare `method="supplied_local"`,
`outcome="available"` and a known `supplied_locator` equal to the lexical absolute
`input_root/input_path` selected. Disagreement is rejected, never repaired.
Top-level provenance is a separate declaration and selects no paths. Attribution,
acquisition times, requested/resolved locators, media types and unknowns remain
supplied declarations. Capture observes `original_mode=stat.S_IMODE(held_stat.st_mode)`
and obtains actual `{digest, size}` references only through `store.put_artifact`.
It infers no timestamps, upstream identity/version, permissions or reading from
bytes or names. Supplied extraction outputs are inert selected files; declared
tool settings, exact original-input lineage and mappings do not run or authenticate
the declared tool.

`revision` is an ordinary integer from 1 through `2**63-1`; `expected_head` is from
0 through `2**63-2`; `revision == expected_head + 1` is mandatory. `supersedes` is
explicit: revision 1 requires null; any non-null value must pin this capture's
immediate predecessor. Existing admission requires supersession and stable
`work_id` for typed predecessors and preserves generic-history transition rules.
There is no inferred head, silent rebase or historical-reference rewrite.
Record/submission IDs and both CreationProvenance values are explicit.

`max_file_bytes` and `max_total_bytes` are required ordinary integers from 0 through
`2**63-1`; zero permits only empty files. `max_files` is a required positive integer
through `2**63-1`, with the independent Source cap of 1,024 inventory entries.
Bools, floats, nulls and generators do not coerce. Count is checked before copying
or opening selection entries. Template shape, standalone nested declarations,
paths, provenance agreement and attribution are checked before reading content.
Complete lineage and byte ranges are checked with actual captured references.

## Filesystem contract and trusted exclusions

This is a POSIX local-filesystem operation under trusted-owner and trusted-mount
assumptions. Paths are anchored lexically without resolving away symlinks. The
input root must not overlap, in either direction, any of these trusted exclusions:

- `source_root`: the actual software-source location;
- the selected store's actual runtime root, automatically excluded;
- `backup_roots`: a mandatory explicit list/tuple of every applicable backup location;
- `control_roots`: a mandatory explicit list/tuple of every applicable Git and controller location.

An empty list explicitly asserts that no additional locations in that category
apply. Callers must include every applicable backup, Git and controller location.
Exclusions must name their actual locations without symlink or mount aliases.
This API does not discover aliases or establish a broader authorization system.
These roots are trusted caller authority, never derived from Source metadata.
No directory enumeration, recognizable-layout discovery, glob, recursive walk,
archive expansion, network request, parser, OCR, configuration activation,
dependency installation or content execution occurs. Only ancestors needed for
the explicit selection are opened.

Every traversed directory must remain bound to the held device/inode and be owned
by the effective user or root. Ordinary ancestors have no group/world write or
special bits. Root-owned sticky shared ancestors such as `/tmp` are allowed
outside the input root, provided each traversed child satisfies its own ownership
and mode rule. The input root and selected subdirectories must be effective-user
owned, owner-readable/searchable directories without group/world write or special
bits: ordinary 0700 and 0755 work. Ownership, group, mode and binding stability
are checked before reads and before return. Directory size/mtime are not file
content evidence: unrelated sibling activity is permitted.

Selected leaves must be effective-user-owned, owner-readable, single-link regular
files without group/world write or special bits. Ordinary executable bits are
allowed and never cause execution. Symlinks at any traversed depth, hard links,
FIFOs, sockets, devices and directory leaves fail before content reads. Each leaf
uses lstat followed by `O_RDONLY|O_NOFOLLOW|O_NONBLOCK` and complete preopen/open
signature comparison. All directory and selected-file descriptors are retained
through the final gate and closed on success and failure. Observations include
identity, size, mtime/ctime, mode, ownership and link count; read-induced atime is
not input modification. These observed binding checks are not a sandbox against
arbitrary same-owner or privileged adversaries, or dishonest mounts.

All selected leaves are opened and size-checked, including the aggregate total,
before allocating content buffers. Files are read one at a time in chunks no larger
than the remaining observed size or 64 KiB, with exact completion and at most one
extra byte for the EOF probe. Growth, truncation, in-place modification, same-byte
inode substitution, ancestor rebinding and changes to earlier files during later
capture fail. Signatures are checked after reading and before publication; all
bindings and permissions are checked again after preview and detached-result
construction. No chmod, repair, removal, renaming or cleanup of supplied material
occurs. Scripts, notebooks, configuration, licenses and data are only bytes.

## Mapping, saved requests and recovery

The mapping contains exactly `input_root` (anchored lexical absolute string) and
`files` (ordered array). Every file object contains exactly `input_path`,
`supplied_path` (full selected path), `artifact_id`, `path` (logical name),
`artifact` (`{digest, size}`), `original_mode`, and complete `provenance`.
Every entry is checked against its resulting Source inventory occurrence.
Exact paths, hashes, modes and provenance remain recoverable from that inventory
and its supplied locators after saving only the Submission.

The Source saved wrapper is exactly:

```text
{format: "research_pipeline.source_capture_submission", version: 1,
 submission: <complete Submission.to_dict()>}
```

`submission` is the complete object, with no omitted nested fields. Encoding is deterministic,
compact, sorted-key ASCII JSON; array order remains supplied order. Exactly one
coherent Source envelope and `{record_id: revision - 1}` expected heads are required.
The strict loader accepts only ordinary str or strict UTF-8 bytes and rejects
omitted fields at every nesting level, duplicates, unknown versions/fields,
coercion, malformed Unicode, nonfinite values and forged/incoherent projections.
It compares the parsed canonical snapshot to fully reconstructed serialization to
reject default insertion or normalization changes. Both directions revalidate
nested typed values. Neither codec accesses filesystem/storage, checks admission,
or generates IDs/timestamps. Source and work-product proposal codecs reject each
other's format. A pure serialized request can later fail historical admission.

Preparation calls the store's existing read-only typed admission check, including
exact links, typed history, current CAS and direct artifact availability. It
writes no application metadata, events, receipts or submission reservations.
Published unreferenced objects may remain after success or failure; no cleanup
is attempted. A preview is not a promise of future admission. Competing proposals
can prepare successfully; only one can win the expected-head CAS.

Save is caller-controlled and visibly separate. Exclusively create an ordinary
proposal file outside both selected input and runtime, flush/fsync the file,
fsync its parent directory, reload that saved value, then explicitly call
`submit_typed`. On uncertainty, load and submit the same saved request directly.
**Never put an input reread, head check, backup check or artifact check before
`submit_typed` on a retry.** The store's original-ID-first reconciliation returns
the original receipt for an identical request, even after local edits/deletion,
head advancement or missing/corrupt direct artifacts, without new events/receipts.
Changed reuse conflicts; new captures or edits require a new submission ID.
Preparation with a used ID fails and directs callers to retry the saved proposal.
A process exit before commit leaves no metadata; an exit after commit can lose the
acknowledgment, which the saved original request reconciles after reopen or exact
backup restore. Existing backup format and migration behavior are unchanged.

Malformed arguments raise `DomainValidationError`. Unsafe layouts raise
`CheckoutLayoutError`, observed changes raise `CheckoutIntegrityError`, and
filesystem failures raise `CheckoutOperationalError` with chained causes.
Artifact failures remain meaningful through the existing checkout error hierarchy;
existing store admission/CAS/submission-conflict errors retain their semantics.
Preparation failures preserve all application tables while possibly retaining
unreferenced objects. No error authorizes repairing the supplied material.

## Runnable synthetic capture example

Run this exact block in a fresh interpreter with candidate-source imports, for
example `PYTHONPATH=implementation/src python3 -B` from the worktree root. All
materials are deterministic synthetic development data created in a disposable
temporary directory; no external data is acquired. The ordinary proposal file
is exclusively created in a trusted parent outside input/runtime.

```python
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import research_pipeline.source_capture as capture_api
from research_pipeline.domain import CreationProvenance
from research_pipeline.source import (
    DeclaredText, Source, SourceDeclaration, SourceProvenance,
    SourceReading, SourceRestrictions, decode_envelope,
)
from research_pipeline.source_capture import (
    prepare_source_capture, dumps_prepared_submission, loads_prepared_submission,
)
from research_pipeline.store import RecordStore


def known(value):
    """Represent a supplied literal declaration without inferring authority from it."""
    return DeclaredText(value, None)


def unknown():
    """Explain missing synthetic metadata explicitly rather than inventing facts."""
    return DeclaredText(None, "Not supplied in this synthetic example")


with TemporaryDirectory() as temporary:
    parent = Path(temporary)
    inputs = parent / "inputs"
    inputs.mkdir(mode=0o755)
    # Candidate-source layout: worktree/implementation/src/research_pipeline.
    software = Path(capture_api.__file__).parents[3]
    payload = "Synthetic α: $x^2$; not a read paper.\n".encode("utf-8")
    selected_path = inputs / "supplied.tex"
    selected_path.write_bytes(payload)
    selected_path.chmod(0o644)
    acquisition = SourceProvenance(
        "supplied_local", known("Synthetic supplier"), unknown(),
        known(str(selected_path)), unknown(), unknown(), "available", [],
    )
    declaration = SourceDeclaration("unknown", "No permission inferred")
    value = Source(
        work_id="synthetic-work", upstream_identity=unknown(), upstream_version=unknown(),
        title=known("Synthetic α"), authors=[unknown()], provenance=acquisition,
        restrictions=SourceRestrictions(declaration, declaration, declaration, declaration),
        originals=[], extractions=[], locations=[],
        reading=SourceReading("uninspected", [], None, "unreported", [], unknown(), []),
        statements=[], related_sources=[], supersedes=None,
        limitations=["Synthetic engineering example; no scientific qualification"],
    )
    template = value.to_dict()
    for key in ("format", "version", "kind"):
        del template[key]
    template["originals"] = [dict(
        artifact_id="original", path="originals/α.tex", media_type=unknown().to_dict(),
        provenance=acquisition.to_dict(),
    )]
    attribution = CreationProvenance("synthetic-caller", "2026-10-30T12:00:00Z", {})
    with RecordStore.create(parent / "runtime") as store:
        prepared = prepare_source_capture(
            store, inputs, selected_files=[dict(artifact_id="original", input_path="supplied.tex")],
            metadata=template, record_id="capture", revision=1, expected_head=0,
            submission_id="capture-request-1", record_provenance=attribution,
            submission_provenance=attribution, source_root=software,
            backup_roots=[], control_roots=[], max_file_bytes=len(payload),
            max_total_bytes=len(payload), max_files=1,
        )
        assert store.get_submission("capture-request-1") is None
        frozen = dumps_prepared_submission(prepared.submission)
        template["authors"].clear()
        exposed = prepared.mapping
        exposed["files"].clear()
        assert dumps_prepared_submission(prepared.submission) == frozen
        assert len(prepared.mapping["files"]) == 1
        proposal = parent / "proposal.json"
        with proposal.open("xb") as stream:
            stream.write(frozen.encode("ascii"))
            stream.flush()
            os.fsync(stream.fileno())
        directory_fd = os.open(parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
        saved = loads_prepared_submission(proposal.read_bytes())
        receipt = store.submit_typed(saved)
        content = decode_envelope(saved.records[0])
        assert content.reading.coverage == "uninspected"
        assert content.originals[0].original_mode == 0o644
        assert store.read_artifact(content.originals[0].artifact) == payload
        assert selected_path.read_bytes() == payload
        assert selected_path.stat().st_mode & 0o7777 == 0o644
        selected_path.unlink()  # Caller edits/deletes only after capture; capture never does.
        events = store.audit_events()
        assert store.submit_typed(loads_prepared_submission(proposal.read_bytes())) == receipt
        assert store.audit_events() == events
    with RecordStore.open(parent / "runtime") as reopened:
        assert reopened.submit_typed(loads_prepared_submission(proposal.read_bytes())) == receipt
```

Supplied paths, provenance and tool settings are inert data. Capture establishes
neither actual reading, authenticated attribution, extraction fidelity, scientific
qualification, project readiness, tool enablement nor external-processing authority.
It never upgrades coverage or certifies reproduction. Historical oscillator
provenance is unchanged; D02/D03 and M0-S qualifications remain partial/pending.
Future acquisition/processing permission enforcement and scientific readiness
remain separate required work.
