# Versioned work-product manifests

`research_pipeline.work_product` supplies pure frozen `WorkProductFile` and
`WorkProductManifest` values and strict version-1 codecs. Import directly from
this submodule; there are no package re-exports, CLI commands, dependencies or
import-time filesystem effects. Immutable bundles are admitted through the existing
durable store. [Safe durable checkout](checkout.md) materializes exact committed
revisions as independent writable copies with bounded capture and local base
descriptors. [Preview and explicit import](work-product-import.md) captures edits
and freezes proposals for separate typed commit and original-ID recovery.

A product kind and descriptive build/input links confer no execution authority,
support, endorsement, task completion, verified exposure or certification of
detailed TeX, checkpoint, run-report or execution contracts. Authors and envelope
provenance are declared attribution, not authenticated authorship; their values
need not match. No dates, authors, titles, status or content meaning are inferred
from filenames or bytes. D02 remains partial. Scientific sufficiency, eligibility,
full vault/intake and research execution remain deferred.

## Constructors and exact fields

All arguments are required, including nullable references and empty collections.
Constructor collections accept only ordinary lists or tuples and become detached
tuples. Strings retain their spelling, meaningful whitespace and ordering.

```python
WorkProductFile(path: str, artifact: ArtifactReference)
WorkProductManifest(
    product_kind: str,
    title: str,
    purpose: str,
    authors: tuple[str, ...],
    task: RecordReference | None,
    branch: RecordReference | None,
    context: RecordReference | None,
    run: RecordReference | None,
    linked_claims: tuple[RecordReference, ...],
    linked_sources: tuple[RecordReference, ...],
    supersedes: RecordReference | None,
    build_dependencies: tuple[RecordReference, ...],
    files: tuple[WorkProductFile, ...],
    entry_file: str,
    limitations: tuple[str, ...],
)
```

| Field | Contract |
| --- | --- |
| `product_kind` | Exactly `note`, `derivation`, `calculation`, `notebook`, `checkpoint`, `reading_report`, `end_of_run_report`, `figure`, `program` or `context_packet`. A label only. |
| `title`, `purpose` | Separate nonblank scalar-Unicode strings. The display title is independent of paths. |
| `authors` | Nonempty ordered attribution strings, each nonblank scalar Unicode. Repetitions are retained. |
| `task`, `branch`, `context`, `run`, `supersedes` | Explicit null or exact reference with the role/kind below. |
| `linked_claims`, `linked_sources`, `build_dependencies` | Explicit ordered reference collections, possibly empty. Repeated `(record_id, revision)` targets within a collection fail; distinct revisions remain distinct. |
| `files` | Nonempty ordered file entries. Each serializes as exactly `{path, artifact}`; artifact is exactly `{digest, size}`. Distinct paths may reuse identical bytes. Repeated digests must have identical sizes. |
| `entry_file` | Must equal a supplied file path exactly as a Python string, not merely under alias comparison. |
| `limitations` | Explicit ordered nonblank text collection, possibly empty; repetitions and whitespace are retained. |

The manifest wire object contains exactly these fields plus
`format="research_pipeline.work_product_content"`, `version=1`, and
`kind="work_product_manifest"`. There are no constructor switches for headers,
no alternate wire representations, and no implicit omitted fields. Every serialized
collection is an ordinary JSON array. Both value classes expose strict
`to_dict() -> dict` and `from_dict(dict)` with fresh detached trees.

## Portable logical paths

Paths are nonempty relative POSIX names, split only on `/`. Validation examines
the original string before any path normalization. Leading or trailing `/`, empty
components, `.` and `..`, backslashes, `< > : " | ? *`, Unicode control/format
characters (categories `Cc`/`Cf`), and components ending in ASCII space or dot
are forbidden. Colon exclusion rejects drive syntax, alternate streams and URL
schemes. Scalar validation rejects surrogates; supplementary Unicode remains valid.

For each component the conservative, locale-independent alias key is:

```text
NFKC(NFKC(component).casefold())
```

The key must satisfy the same component safety checks, so compatibility characters
cannot become separators, unsafe endings, punctuation or dot components. To check
reserved device names, take the key's portion before its first dot, remove trailing
ASCII spaces from that stem, and reject `con`, `prn`, `aux`, `nul`, `clock$`,
`conin$`, `conout$`, `com1`–`com9`, and `lpt1`–`lpt9`. This includes extensions,
case variants, full-width names and superscript-digit compatibility forms such as
`COM¹.txt`.

The complete file set rejects exact duplicates, alias-equivalent paths and files
that are proper component prefixes of other files, in either insertion order.
Shared directories must also retain one exact spelling: `Dir/a` with `dir/b`
fails, while `Dir/a` with `Dir/b` is valid. `a` with `ab/c` is valid because textual
prefixes alone are irrelevant. Errors name conflicting supplied paths.

NFKC/casefold intentionally rejects some names a case-sensitive filesystem can
distinguish, including `Straße`/`STRASSE` and composed/decomposed accents. A single
allowed decomposed spelling is preserved unchanged; adding its alias fails.
Validation never silently renames a supplied file. This is neither a filesystem
sandbox nor a universal confusable-character detector; the pure codec does not
access the filesystem.

## Strict codecs and envelope projection

| Module-local operation | Result |
| --- | --- |
| `decode_content(value: dict) -> WorkProductManifest` | Decode only the explicit supported format/version/kind. |
| `dumps_content(value: WorkProductManifest) -> str` | Revalidate and produce canonical sorted-key compact ASCII-escaped JSON, preserving array order. |
| `loads_content(data: str | bytes) -> WorkProductManifest` | Decode ordinary strings or strict UTF-8 bytes with duplicate-key rejection at every depth. |
| `encode_envelope(record_id, revision, content, provenance) -> RecordEnvelope` | Derive `work_product_manifest`, null operational/scientific states, and complete ordered links; preserve explicit caller provenance. |
| `decode_envelope(envelope: RecordEnvelope) -> WorkProductManifest` | Defensively reconstruct and require exact kind, states, ordered links and local supersession coherence. |

Missing format raises the existing `NotTypedContentError` subtype of
`DomainValidationError`. Other malformed input raises useful `DomainValidationError`
with field/index context and chained causes where appropriate. Missing/extra fields
at any depth, omitted `target_kind`, unknown headers, boolean/coerced integer fields,
invalid collections, invalid UTF-8, nonfinite values, duplicate JSON keys, trailing
JSON, cycles, excessive depth and nonscalar Unicode fail. Valid supplementary
characters, literal escape text and repeated narrative statements survive.
Constructors, dictionary decoding, serialization and envelope conversion all
revalidate nested exact classes and reject forged frozen values or serialization
lookalikes. Codecs neither resolve targets nor check artifact availability.

| Field | Relationship | Required declared `target_kind` |
| --- | --- | --- |
| `task` | `task` | `task_specification` |
| `branch` | `branch` | `branch` |
| `context` | `context` | `research_context` |
| `run` | `run` | `run` |
| `linked_claims` members | `linked_claim` | `claim` |
| `linked_sources` members | `linked_source` | `source` |
| `supersedes` | `supersedes` | `work_product_manifest` |
| `build_dependencies` members | `build_dependency` | Any supported record kind, explicitly declared; null is forbidden. |

Record links project in exactly this order: task, branch, context, run, linked
claims, linked sources, supersedes, build dependencies. Only null optional links
are omitted. The same target in different roles remains separate, and each role
has its own validation. Build dependencies are descriptive input records, with no
execution configuration or artifact-dependency mechanism.

Artifact links walk files in order and retain the first occurrence of each digest.
File entries sharing bytes remain separate in content. This does not change
Evidence's non-deduplicated cross-role projection. Decoders reject missing,
surplus, duplicate, reordered, relabeled or substituted envelope links rather
than repairing them.

Supersession is optional. Revision 1 requires null. On revision `n > 1`, a non-null
supersession must name the same `record_id` at exactly `n - 1`; wrong identities,
skipped revisions, self and future references fail. Appending with null is permitted.
Both envelope directions and typed exact reads apply this local rule. Content-only
codecs can check the role/kind but cannot know the enclosing identity or revision.
The local check consults no storage, preserving original-ID retry ordering.

## Durable admission, history and guarantees

`RecordStore.submit_typed(Submission(...))` accepts coherent manifests alongside
the four scientific and two assessment kinds, including forward references in a
mixed batch. `get_typed_revision(record_id, revision)` returns the detached exact
envelope and `ScientificContent | AssessmentContent | WorkProductManifest` value.
No new store API, transaction path, schema version or fingerprint version is added.

The [exhaustive traversal table](attributed-assessments.md#durable-api-and-exact-traversal)
defines every typed kind's constrained and shallow roles. Manifest context,
linked claims and supersession require supported coherent typed targets, recursively
following their constrained outgoing roles. Task, branch, run, linked sources and
build dependencies check only exact existence and declared kind. Shallow targets'
payloads, outgoing links and attachments are never inspected merely because their
kind is familiar. Review `context_manifest` remains shallow even after this codec
exists: generic, unsupported or incoherent declarations do not establish verified
exposure. A shallow occurrence cannot exempt the same target from a separate
constrained occurrence. Every independently submitted typed batch member is checked.
Descriptive cycles terminate through the existing finite worklist; build references
have no execution or acyclicity semantics.

For a new request, target resolution uses the proposed batch first, then exact
historical revisions, never current target heads. Every incoming edge checks kind,
even on cache hits. Missing/wrong-kind targets and invalid historical typed targets
raise `ReferenceResolutionError` naming exact target and role, with codec causes
chained. Submitted-member failures remain domain errors. Historical supersession
also receives the local identity/revision rule and recursive constrained checks.
Review route-conclusion membership remains unchanged.

All admission checks run inside the existing serialized write transaction before
metadata insertion. Direct artifacts are verified and synchronized; expected-head
CAS, stable kinds and next revisions apply. Typed reads verify direct artifacts
before detached local decoding. Neither admission nor typed reads add transitive
artifact reads. An exact typed read checks selected-envelope coherence, not past
admission, target availability or a scientific certificate. A rejected request
creates no records, heads, links, artifact metadata, submissions, receipts or events;
already published orphan bytes may remain.

Local request normalization and codec validation precede original-ID reconciliation.
Inside the transaction an identical canonical original request returns its original
receipt before schema-kind, head, target or artifact checks, even after head advance
or later byte damage. Changed content, attribution or ordering under that ID conflicts.
An original generic receipt remains an acknowledgment of that commit, not retroactive
typed certification. There is no earlier supersession lookup that could break retry.

Generic `submit` continues to preserve arbitrary manifests, including missing-marker,
unsupported-version and incoherent typed-looking payloads. Healthy backups and exact
restore preserve generic history, old/new bytes, ordered links, provenance, canonical
requests and original receipts without replay; typed reads reject invalid payloads.
Schema 1 refuses this schema-2 kind with its migration-required error before new-request
target or artifact checks. Explicit v1→v2 restore preserves the original history and
receipts, then allows typed manifests and subsequent v2 backup/exact restore.

## Runnable manifest persistence example

Run with candidate `implementation/src` on `PYTHONPATH`. Tests execute this actual
block in a fresh candidate-source interpreter. All data is synthetic, runtime is
outside source, and no artifact contents are executed.

```python
from pathlib import Path
from tempfile import TemporaryDirectory
from dataclasses import replace

from research_pipeline.domain import CreationProvenance, RecordReference, Submission
from research_pipeline.store import RecordStore
from research_pipeline.work_product import WorkProductFile, WorkProductManifest, encode_envelope

creator = CreationProvenance("author", "2026-10-30T12:00:00Z", {"source": "synthetic"})
controller = CreationProvenance("controller", "2026-10-30T12:01:00Z", {})
with TemporaryDirectory(prefix="work-products-example-", dir="/tmp") as temporary:
    root = Path(temporary) / "runtime"
    with RecordStore.create(root) as store:
        text = store.put_artifact("Synthetic note α\n".encode("utf-8"))
        binary = store.put_artifact(b"\x00\xff\x80")
        value = WorkProductManifest(
            product_kind="note", title="A synthetic bundle", purpose="Demonstrate exact storage",
            authors=["Declared author α"], task=None, branch=None, context=None, run=None,
            linked_claims=[], linked_sources=[], supersedes=None, build_dependencies=[],
            files=[WorkProductFile("notes/α.txt", text), WorkProductFile("data/raw.bin", binary),
                   WorkProductFile("copy.txt", text)],
            entry_file="notes/α.txt", limitations=["No scientific validation"],
        )
        first = encode_envelope("bundle", 1, value, creator)
        initial = Submission("initial", controller, [first], {"bundle": 0})
        receipt = store.submit_typed(initial)
        updated = replace(value, title="Revised declared title",
                          supersedes=RecordReference("bundle", 1, "supersedes", "work_product_manifest"))
        second = encode_envelope("bundle", 2, updated, creator)
        store.submit_typed(Submission("append", controller, [second], {"bundle": 1}))
    with RecordStore.open(root) as reopened:
        assert reopened.get_typed_revision("bundle", 1) == (first, value)
        assert reopened.get_typed_revision("bundle", 2) == (second, updated)
        assert reopened.history("bundle") == (first, second)
        assert first.artifact_references == (text, binary)
        assert reopened.read_artifact(text) == "Synthetic note α\n".encode("utf-8")
        assert reopened.read_artifact(binary) == b"\x00\xff\x80"
        assert second.operational_status is None and second.scientific_disposition is None
        assert reopened.submit_typed(initial) == receipt
```
