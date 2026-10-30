# Versioned source captures

`research_pipeline.source` provides frozen, bounded values, strict version-1 JSON
and exact envelope conversion. Import directly from that submodule. Imports and
codecs are inert: no locator is opened, no bytes are parsed, and no tool runs.
The existing scientific, assessment and work-product version-1 codecs are unchanged.

A Source describes a capture of a caller-declared work. `work_id` is its stable
opaque work identity; `upstream_identity` and `upstream_version` are descriptive
known-or-unknown declarations. Only the envelope supplies local capture
`record_id` and `revision`. An optional exact `reading.report` pins a separate
WorkProductManifest identity/revision with `product_kind="reading_report"`.
None of these three version systems implies another. Filenames and hashes do
not establish an upstream version. A null report claims no report; metadata triage
need not fabricate one.

Stored acquisition, attribution, reading and reproduction declarations are
unauthenticated. Capture/extraction establishes neither reading nor transcription
fidelity, mathematical equivalence, scientific support, approval or readiness.
Restrictions are explained declarations, not operational grants or a broader
policy enforcement system. Empty limitations certify nothing. Scientific readiness,
source acquisition/processing permission enforcement remain separate work.
[Bounded local capture and saved Source proposals](source-capture.md) are available
through a separate explicit library boundary; this pure codec introduces no network
acquisition, parser, OCR or execution.

## Required constructors

Every argument below is required, in the listed positional order; keyword arguments
are supported. Every wire field is required, including nulls and empty arrays.
Nested wire objects contain exactly their constructor fields. Only Source adds
`format="research_pipeline.source_content", version=1, kind="source"`.

| Constructor | Required arguments |
| --- | --- |
| `DeclaredText` | `value, unknown_reason` |
| `SourceProvenance` | `method, attribution, occurred_at, supplied_locator, requested_locator, resolved_locator, outcome, notes` |
| `SourceDeclaration` | `status, detail` |
| `SourceRestrictions` | `access, reuse, confidentiality, external_processing` |
| `SourceArtifact` | `artifact_id, path, artifact, media_type, original_mode, provenance` |
| `ToolSetting` | `name, value` |
| `SourceLocation` | `location_id, artifact_id, kind, label, start, end` |
| `LocationMapping` | `original_location, output_location` |
| `SourceExtraction` | `extraction_id, original_inputs, tool, tool_version, settings, outputs, mappings, warnings` |
| `SourceReading` | `coverage, locations, report, reproduction, checks, attribution, limitations` |
| `SourceStatement` | `statement_id, category, text, attribution, locations, checks, limitations` |
| `RelatedSource` | `reference, relation` |
| `Source` | `work_id, upstream_identity, upstream_version, title, authors, provenance, restrictions, originals, extractions, locations, reading, statements, related_sources, supersedes, limitations` |

All classes provide `to_dict() -> dict` and `from_dict(value: dict)` returning the
corresponding class. Nested values require exact classes, are reconstructed and
revalidated, and never retain caller containers. Deliberately bypassed frozen state
is revalidated on serialization. Returned dictionaries/lists are detached.
Constructor collections accept ordinary lists/tuples, become tuples and preserve
order; wire collections require ordinary lists. No defaults or extension bags
supply missing declarations.

## Bounds and declarations

Source-owned nonblank text contains ordinary Unicode scalar strings, at most
16,384 characters each. Whitespace and spelling are preserved without normalization.
Every Source-owned collection has at most 1,024 members. Across all originals and
extraction outputs there are at most 1,024 artifact entries total. These extra bounds
do not change older codecs or generic payloads. Opaque local IDs and `work_id`
use the existing 1–128 ASCII letters/digits/underscore/hyphen rule, starting with a
letter or digit. Revisions are ordinary integers 1 through `2**63-1`; artifact sizes
are ordinary integers 0 through `2**63-1`. Booleans, floats and strings do not coerce.

`DeclaredText(value: str | None, unknown_reason: str | None)` requires exactly one
non-null nonblank text field. Empty text is invalid; the literal word `unknown`
is ordinary known text, not a sentinel. Source upstream identity/version/title,
each author, provenance attribution/time/locators, media type, tool/version,
setting value, reading attribution and statement attribution use this type.
`authors` is nonempty; an unknown author or incomplete authorship can be explicitly
explained. Original inventories may be empty for unavailable or metadata-only captures.

| Field | Codes and conditions |
| --- | --- |
| Provenance `method` | `supplied_local`, `supplied_artifact`, `reported_retrieval`, `unknown`; supplied methods require a known `supplied_locator` |
| Provenance `outcome` | `available`, `partial`, `unavailable`, `unknown` |
| Restriction `access.status` | `available`, `limited`, `unavailable`, `unknown` |
| Restriction `reuse.status`, `external_processing.status` | `permitted`, `restricted`, `prohibited`, `unknown` |
| Restriction `confidentiality.status` | `public`, `confidential`, `restricted`, `unknown` |
| Location `kind` | `page`, `section`, `equation`, `theorem`, `byte`, `line` |
| Reading `coverage` | `uninspected`, `metadata_only`, `abstract_only`, `selected_material`, `whole_document` |
| Reading `reproduction` | `unreported`, `not_attempted`, `reported_failed`, `reported_partial`, `reported_succeeded` |
| Statement `category` | `source_statement`, `interpretation`, `referenced_check` |

All four restrictions contain `SourceDeclaration(status: str, detail: str)`;
explanatory detail is mandatory nonblank text, even for unknown status. The containing
field validates its vocabulary. A known `occurred_at` must satisfy the existing UTC
calendar syntax `YYYY-MM-DDTHH:MM:SS[.ffffff]Z`, with one through six fractional
digits if supplied, but preserves the supplied spelling. This reported acquisition
time is separate from envelope `CreationProvenance`, whose existing normalized
creation timestamp contract is unchanged. Unavailable retrieval locations remain
explicit unknowns. `notes`, `warnings` and `limitations` are ordered text collections.

`SourceArtifact.artifact` is an exact `ArtifactReference(digest, size)`: a 64-character
lowercase SHA-256 hex digest and bounded size. `original_mode` is null or an ordinary
integer 0 through `0o7777`. It is supplied metadata, not the artifact store's actual
mode and never an instruction to chmod. Logical `path` has at most 4,096 characters
and follows the [portable work-product rules](work-products.md#portable-logical-paths),
including conservative Unicode/case aliases and file/directory collision checks
across the entire inventory. Separate IDs/paths may retain repeated bytes; one digest
must always have the same size.

## Local inventory, locations and extraction lineage

Artifact IDs are unique across originals and every extraction output. Extraction,
location and statement IDs are unique within their respective collections. These IDs
are scoped to this exact Source; resolved artifact references pin exact bytes.

Named page/section/equation/theorem locations preserve their nonblank labels literally
and require null start/end. Their artifact ID may be null, explicitly describing an
upstream locator without captured-byte anchoring. Byte locations require an artifact
and ordinary integers `0 <= start < end <= artifact.size`, with half-open offsets.
Line locations require an artifact and integers `1 <= start <= end`, with inclusive
endpoints. Bytes are never read to infer a line count. Every non-null artifact ID
must resolve in the inventory. Every reading/statement location must exist, with
no duplicate location IDs within that collection.

Each extraction requires nonempty ordered unique `original_inputs` resolving only
to originals, and nonempty `outputs`. Chained extractions are unsupported. Tool and
tool version can be explicitly unknown; `settings` contains bounded `ToolSetting`
values with unique exact nonblank names. These are declarations, not executable
configuration. Mapping pairs must be unique. Each original endpoint must be anchored
to one of that extraction's exact original inputs, and each output endpoint to one
of its outputs. Missing endpoints, reversed roles, cross-extraction output links
and unanchored upstream labels fail. Empty mappings require at least one warning
explaining the unavailable mapping. Mapping declarations imply no fidelity or
scientific equivalence. Input/output order and warnings are retained.

`uninspected` requires no inspected locations; `selected_material` requires at least
one. Other coverage levels do not imply exhaustive locator enumeration. Reported
reproduction outcomes require at least one separate check reference. Checks and
artifact/extraction availability never upgrade coverage automatically.
`source_statement` requires a location; `interpretation` may have none. Both require
empty checks. `referenced_check` requires checks. All categories retain attribution
and limitations; they do not create scientific Claims.

## Exact references, projections and APIs

Every reference has all four required keys `record_id, revision, relationship,
target_kind`, with explicit non-null kind. Checks support exactly
`reported_evidence → evidence` and `reported_tool_execution → tool_execution`.
Exact `(record_id, revision)` targets are unique within each check collection.
RelatedSource uses `related_source → source`, nonblank relation text and unique
exact targets in its collection. A related source cannot name any revision of the
containing capture identity; same-capture history uses `supersedes → source`.

Envelope record projection order is: supersedes when present; related sources in
order; reading report when present; reading checks in order; each statement's checks
in statement/check order. Occurrences across roles or statement collections remain
separate. Artifact projection scans originals then extraction outputs in their
respective orders and keeps the first occurrence of each digest. Content preserves
all separate entries for repeated bytes. Decoding requires exact equality of the
complete ordered projections, rejecting missing, extra, substituted or reordered
links without repair. Source envelope kind is `source`; both canonical state fields
are null.

| Pure function signature | Result |
| --- | --- |
| `decode_content(value: dict) -> Source` | Strict explicit Source document |
| `dumps_content(value: Source) -> str` | Revalidated canonical JSON: sorted keys, compact separators, ASCII escaping, ordered arrays, finite values |
| `loads_content(data: str \| bytes) -> Source` | Strict JSON, bytes decoded as UTF-8 |
| `encode_envelope(record_id: str, revision: int, content: Source, provenance: CreationProvenance) -> RecordEnvelope` | Detached coherent null-state envelope |
| `decode_envelope(envelope: RecordEnvelope) -> Source` | Reconstructed content with exact envelope checks |

Pure codecs do no store lookup or artifact reads. Both envelope directions reject
supersedes unless it names the same record identity at revision minus one; revision
1 requires null. Null is locally valid at later revisions, subject to durable history
rules below. There is no second embedded report revision counter.

Missing format raises `scientific.NotTypedContentError`; malformed/unknown formats,
unsupported version/kind, missing/extra nested fields, duplicate JSON keys at any
depth, invalid UTF-8, surrogate code points, cycles/depth failures, trailing data,
nonordinary types and forged values raise `DomainValidationError`. Diagnostics retain
field context and relevant causes. Generic envelope APIs preserve arbitrary historical
source documents, unsupported formats and versions unchanged.

## Durable admission and history

The [exhaustive eight-kind traversal table](attributed-assessments.md#durable-api-and-exact-traversal)
defines constrained versus shallow edges. Source supersedes, reading report and each
reported Evidence occurrence are constrained. Related sources and reported ToolExecution
are shallow. A report target must be a coherent typed WorkProductManifest with
`product_kind="reading_report"`; this is checked on every incoming report edge,
including historical closure and cached targets. No equality of unrelated contexts
or inference of scientific results is added.

For new requests, ordinary CAS checks precede Source history checks in the same
transaction. If the immediately preceding capture explicitly uses the Source format,
it must decode strictly, preserve `work_id`, and be explicitly pinned by supersedes.
Omitting the link cannot bypass continuity. Malformed or unsupported explicitly Source
predecessors fail with chained `ReferenceResolutionError`. A legacy generic source
using another/no format may be followed by a first typed revision with null supersedes,
without interpreting or certifying its metadata. Explicit supersedes always requires
a coherent typed Source predecessor. The same rules apply to historical Sources
reached through constrained traversal, using metadata only and a finite cached worklist.

Existing manifest `linked_source`, Evidence `input_record`, Issue `affected_record`
and other shallow roles still accept generic/unsupported/incoherent source payloads
when exact existence and declared kind pass. Shallow edges do not inspect payload,
history, outgoing links or damaged attachments. Independently submitted members of a
typed batch still all require valid typed content. Constrained traversal checks
historical metadata and links, not transitive artifact availability. Direct originals
and derived outputs on submitted/read Sources receive existing artifact verification;
missing/corrupt bytes raise the existing artifact errors.

`submit_typed` uses the existing canonical fingerprint, transaction, fault seams and
original-ID-first reconciliation. An identical locally valid request returns its
original receipt before new history, target, head or artifact checks, even after head
advancement/damage and even if originally committed through generic `submit`. This
acknowledges that original commit; it is not retroactive typed certification. Changed
reuse raises `SubmissionConflictError`; stale heads raise `RevisionConflictError`.
Rejected requests change no application tables. Already published unreferenced
objects may remain. `_check_prepared_typed` retains its read-only admission contract;
[bounded local preparation](source-capture.md) uses that contract before returning
a detached saved Source proposal. Commit remains an explicit separate operation.

Metadata corrections, new captured bytes and changed upstream declarations append
Source revisions under new submission IDs. Report revisions append independently via
existing manifest/CAS behavior; a later Source can pin a new report while retaining
upstream version and originals. Old Evidence inputs and manifest linked sources stay
pinned to their original captures; uses, reports, receipts and declarations never
update automatically. `get_typed_revision` returns Source and the exact envelope and
verifies direct bytes; it checks local coherence, not historical admission certification.
Schema 1 still refuses new Source records until explicit migration. Schema/backup
formats and exact restoration are unchanged.

## Runnable synthetic typed-source persistence example

Run this exact block from the repository root with
`PYTHONPATH="$PWD/implementation/src" /home/francesco/miniconda3/bin/python3 -B`.
The tests execute it in a fresh candidate-source interpreter. The extraction is
**supplied synthetic test data**, not executed parsing or a read paper.

```python
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
from research_pipeline.domain import CreationProvenance, RecordReference, Submission
from research_pipeline.source import (
    DeclaredText, SourceProvenance, SourceDeclaration, SourceRestrictions,
    SourceArtifact, SourceExtraction, SourceLocation, LocationMapping,
    SourceReading, Source, encode_envelope,
)
from research_pipeline.work_product import WorkProductFile, WorkProductManifest
from research_pipeline.work_product import encode_envelope as report_envelope
from research_pipeline.store import RecordStore

creator = CreationProvenance("synthetic-supplier", "2026-10-30T12:00:00Z")
unknown = DeclaredText(None, "Not supplied in synthetic data")
provenance = SourceProvenance("supplied_artifact", unknown, unknown,
                              DeclaredText("synthetic supplied bytes", None), unknown, unknown,
                              "available", ["No parser executed; no paper read"])
declaration = SourceDeclaration("unknown", "No permission inferred")
restrictions = SourceRestrictions(declaration, declaration, declaration, declaration)

def batch(identity, records, heads):
    """Build an explicit attributed request with caller-selected expected heads."""
    return Submission(identity, creator, records, heads)

with TemporaryDirectory(prefix="source-example-") as temporary:
    runtime = Path(temporary) / "runtime"
    with RecordStore.create(runtime) as store:
        original = store.put_artifact(b"Synthetic TeX-like input: x^2\n")
        supplied = store.put_artifact(b"Synthetic supplied text: x squared\n")
        report_bytes = store.put_artifact(b"Synthetic report: bytes uninspected\n")
        original_file = SourceArtifact("original", "input/synthetic.tex", original, unknown, 0o640, provenance)
        output_file = SourceArtifact("text", "derived/synthetic.txt", supplied, unknown, None, provenance)
        locations = [SourceLocation("original-section", "original", "section", "Supplied section A", None, None),
                     SourceLocation("output-range", "text", "byte", "Supplied range", 0, supplied.size)]
        extraction = SourceExtraction("supplied", ["original"], DeclaredText("supplied test data", None),
                                      unknown, [], [output_file],
                                      [LocationMapping("original-section", "output-range")],
                                      ["No fidelity or parsing claim"])
        report = WorkProductManifest("reading_report", "Synthetic report", "Record uninspected coverage",
                    ["Synthetic supplier"], None, None, None, None, [], [], None, [],
                    [WorkProductFile("report.txt", report_bytes)], "report.txt", ["No paper read"])
        reading = SourceReading("uninspected", [], RecordReference("report", 1, "reading_report", "work_product_manifest"),
                                "unreported", [], unknown, ["No inspection claimed"])
        capture = Source("declared-work", unknown, unknown, DeclaredText("Synthetic title α", None),
                         [unknown], provenance, restrictions, [original_file], [extraction], locations,
                         reading, [], [], None, [])
        first = encode_envelope("capture", 1, capture, creator)
        initial = batch("initial", [first, report_envelope("report", 1, report, creator)], {"capture": 0, "report": 0})
        receipt = store.submit_typed(initial)
        # The report has its own revision; an exact old source use stays pinned.
        report2 = replace(report, title="Corrected report", linked_sources=[RecordReference("capture", 1, "linked_source", "source")],
                          supersedes=RecordReference("report", 1, "supersedes", "work_product_manifest"))
        store.submit_typed(batch("report-correction", [report_envelope("report", 2, report2, creator)], {"report": 1}))
        capture2 = replace(capture, title=DeclaredText("Corrected title α", None),
                           reading=replace(reading, report=RecordReference("report", 2, "reading_report", "work_product_manifest")),
                           supersedes=RecordReference("capture", 1, "supersedes", "source"))
        second = encode_envelope("capture", 2, capture2, creator)
        store.submit_typed(batch("capture-correction", [second], {"capture": 1}))
    with RecordStore.open(runtime) as reopened:
        assert reopened.history("capture") == (first, second)
        assert reopened.get_typed_revision("capture", 1)[1].reading.report.revision == 1
        assert reopened.get_typed_revision("report", 2)[1].linked_sources[0].revision == 1
        assert reopened.get_typed_revision("capture", 2)[1].upstream_version == unknown
        assert reopened.read_artifact(original) == b"Synthetic TeX-like input: x^2\n"
        assert reopened.read_artifact(supplied) == b"Synthetic supplied text: x squared\n"
        assert reopened.submit_typed(initial) == receipt
```
