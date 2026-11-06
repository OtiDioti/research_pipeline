# Local inspection and explicit work-product round trips

The source-local foundation provides fifteen bounded operations. Research execution
is unavailable. Declared provenance and author names are attribution, not
authenticated authorship, scientific support or permission. Full R-082, creation
and intake, other draft kinds, runtime administration
and research execution remain incomplete. The explicit saved-proposal route uses the
existing [preview and import APIs](work-product-import.md). The separate
`submit-work-product` and `submit-tool-records` commands submit metadata; inspection, checkout and preparation create no canonical submission.
The [passive Tool-record CLI guide](tool-record-cli.md) specifies exact typed
inspection and mixed passive Tool batches, independent limits and original-ID
recovery, with an executable private-store example. The
[current claim-use CLI guide](claim-use-cli.md) specifies complete metadata-only
current operational snapshots over immutable pins and paged generation history,
with an independent executable private-store example.

Put the executing candidate's `implementation/src` first on `PYTHONPATH`, using an
absolute path when changing working directories. No installation is required:

```bash
export PYTHONPATH="$PWD/implementation/src"
python3 -B -m research_pipeline --help
python3 -B -m research_pipeline --version
python3 -B -m research_pipeline inspect-record --config /private/cli/config.json --record-id bundle --revision 1
python3 -B -m research_pipeline inspect-receipt --config /private/cli/config.json --submission-id initial
python3 -B -m research_pipeline inspect-claim-use --config /private/cli/config.json --use-id U
python3 -B -m research_pipeline inspect-claim-use-history --config /private/cli/config.json --use-id U --after-generation 0 --page-limit 1
python3 -B -m research_pipeline checkout-work-product --config /private/cli/config.json --record-id bundle --revision 1 --destination /private/drafts/note
python3 -B -m research_pipeline inspect-checkout --checkout /private/drafts/note
python3 -B -m research_pipeline prepare-work-product --config /private/cli/config.json --checkout /private/drafts/note --request /private/cli/edit.json --destination /private/proposals/edit-1
python3 -B -m research_pipeline inspect-proposal --proposal /private/proposals/edit-1
python3 -B -m research_pipeline submit-work-product --config /private/cli/config.json --proposal /private/proposals/edit-1
```

No arguments prints help. Every command has `--help`, including units and defaults.
Identifiers and exact revisions are mandatory for exact record operations. Readable-view
selection controls permit explicit null for current head; omission never selects it.
The two claim-use operations explicitly select a registered current use by mandatory
`--use-id`, with no revision option; history additionally selects an exclusive
generation cursor and page size. There is no
positional shortcut, environment-selected store, stdin control, response-file
expansion, generic execution command, plugin or user-selected module. Unknown or
abbreviated options, missing arguments, repeated singleton options and malformed
numeric option syntax are usage errors. Numeric options use ASCII decimal digits.
The two Tool and two claim-use commands additionally require canonical spelling
`0` or `[1-9][0-9]*`, without leading zeros, signs, whitespace or numeric aliases.
Malformed spelling is a usage error; canonical oversized/out-of-range values are
`limit_exceeded` before control access. Older commands retain their syntax.
All options are validated before opening controls, stores or destinations.

The four [immutable readable-view commands](readable-view-cli.md) add generation,
preserved refresh from an independently retained baseline, and offline view/refresh
inspection. That guide specifies their complete selection/limits schemas, result and
recovery field sets, conservative descriptor admission and executable continuation.
All four require config and limits, even when the configured runtime is unavailable.
Existing commands retain the controls and limits below.

## Trusted local configuration and filesystem assumptions

Create an owned private `0700` configuration directory. Its configuration file
must be an owned, single-link regular file, mode `0600` or `0400`. It contains
strict UTF-8 JSON with exactly these four required fields:

```json
{
  "format": "research_pipeline.cli_config",
  "version": 1,
  "store": "/private/runtime",
  "protected_roots": ["/private/backups", "/private/external-git"]
}
```

Use actual absolute paths. An explicit empty `protected_roots` array declares no
additional exclusions. These are operating controls, never scientific metadata;
`source_root`, permissions, provenance and arbitrary settings are refused.
Version must be the ordinary integer `1`, not `true` or `1.0`. Duplicate/unknown
fields, nonfinite numbers, unpaired surrogates and malformed JSON are refused.
Whitespace and object key order are insignificant. Container nesting is limited
to 64 before decoding; numeric tokens are limited to 128 characters before numeric
conversion. Paths must be nonempty scalar strings, at most 4096 UTF-8 bytes each
(including their normalized absolute form), with no NUL or `..` component. At most
64 additional roots are allowed; normalized duplicates are refused.

Configuration store/exclusion paths must be absolute, so moving the configuration
does not change its meaning. CLI config/destination/checkout paths may be relative
to invocation cwd. Redundant separators and POSIX `//` are normalized lexically;
user symlinks are never resolved to make a denied path appear safe.

The entire executing software checkout is derived from the resolved
`implementation/src/research_pipeline` module layout and is always excluded.
An unrecognizable source-local layout fails closed. Runtime overlap with source
or caller exclusions is refused in either direction. Checkout also refuses
bidirectional overlap with the runtime, source, exclusions and config file itself.
External Git administration, backups and other control trees must be supplied as
explicit additional exclusions. No config or environment override removes source
protection. The store must already exist; inspection never creates it.

The store retains its established private owned runtime, objects, staging,
database and rollback-journal restrictions. Checkout requires an existing owned
`0700` destination parent. No missing ancestors are created. Recognizable backup,
checkout, readable-view/refresh and incomplete-control ancestors are rejected by
fixed-name no-follow stat checks, without opening their contents or enumerating
arbitrary directories. Symlink ancestors are refused. Config leaves are checked
before a nonblocking/no-follow open; held directories, lstat/fstat signatures,
bounded reads plus one EOF probe, and final binding checks detect observed file
replacement, growth, truncation and ancestor changes. Input close failures fail
the command. Local descriptors use the same stable-reading assumptions and the
existing complete nested descriptor codec.

Ancestors outside private owned controls are trusted. Held descriptors detect
observed substitutions; they do not sandbox a hostile same-owner or privileged
process. These CLI-specific config/parent requirements do not change library API
policies. `RecordStore.open` retains schema/history validation, legitimate hot
rollback-journal recovery and its five-second SQLite busy timeout. Metadata-only
inspection is therefore **not a zero-physical-writes promise**. Selected payload
limits do not bound SQLite opening, schema validation or recovery work.

## Finite limits

All ranges are inclusive. Counts/bytes include repeated logical occurrences.
Limits do not authorize writes or certify content. The table below retains the
predecessor work-product/exact-inspection contracts; the
[Tool guide](tool-record-cli.md#independent-caller-limits) and
[claim-use guide](claim-use-cli.md#independent-allowances-and-selections) specify
their command-specific accounts. Claim-use defaults differ: `max_records` is
1024 (range 1..1024), `max_metadata_bytes` is 67108864 (1..67108864) and
`max_output_bytes` is 8388608 (1..16777216). Its other required API dimensions are
independent binding/reference/assertion-revision work and complete domain-result
bytes (at most 4194304); config bytes and full output including LF are separate.

| Option | Applicable commands | Default | Range and units |
| --- | --- | ---: | --- |
| `--max-control-bytes` | Config and saved-package commands | 65536 | 1..1048576 bytes per config or package manifest; manifest also capped at 16384 |
| `--max-output-bytes` | Operations in this table | 2097152 | 1..16777216 ASCII bytes, including LF |
| `--max-metadata-bytes` | Record/receipt inspection, checkout, preparation | 2097152 | 1..16777216 selected metadata bytes |
| `--max-links` | Record inspection, checkout, preparation | 4096 | 0..65536 record/artifact link occurrences together |
| `--max-receipt-records` | Receipt inspection, preparation | 1024 | 1..65536 ordered membership occurrences |
| `--max-descriptor-bytes` | Checkout, checkout inspection, preparation | 1048576 | 1..16777216 descriptor bytes |
| `--max-files` | Checkout, preparation, submission | 128 | 1..1024 logical files |
| `--max-file-bytes` | Checkout, preparation, submission | 16777216 | 0..1073741824 bytes per file |
| `--max-total-bytes` | Checkout, preparation, submission | 67108864 | 0..4294967296 logical file bytes |
| `--max-request-bytes` | Preparation | 1048576 | 1..16777216 UTF-8 authored request bytes |
| `--max-proposal-bytes` | Preparation, proposal inspection, submission | 2097152 | 1..16777216 exact ASCII proposal bytes |
| `--max-summary-bytes` | Preparation, proposal inspection, submission | 4194304 | 1..16777216 exact ASCII summary bytes |
| `--max-inventory-entries` | Preparation | 4096 | 1..65536 entries across visited draft directories |

Metadata limits cover preflight fetched-byte accounting and detached encoded
metadata, including repeated reads by the existing reconstruction helpers. Record
inspection uses the established snapshot helper's record and aggregate budgets
for exactly one revision. It never captures an outgoing closure, resolves a head,
enumerates history, reads artifacts or certifies historical typed admission.
Generic envelopes remain inspectable. Receipt inspection preflights complete
joined metadata, field byte lengths, membership count and contiguous ordered
ordinals in the same read transaction as original receipt reconstruction. It
returns original provenance even after head advancement or artifact loss.
Corrupt metadata is an error, not absence or a scientific validity judgment.
Preparation preflights the exact base envelope and its original receipt through
these same bounded readers before the preview API reconstructs them. Its file
budgets apply independently to both the original inventory and selected files;
its entry budget includes controls and unselected entries in visited directories.
Submission bounds the declared proposed inventory without opening artifacts ahead
of the store's original-ID reconciliation. Package encoding bounds include ASCII
escape expansion; reads count actual bytes and probe EOF. Stored declarations can
never raise caller limits. These are selected-data bounds, not total database-work
or wall-clock bounds: opening, schema checks, journal recovery and typed admission
retain their established work and semantics.

## Machine output and exit statuses

Every machine success or deliberate absence is one complete compact, sorted-key,
ASCII-escaped JSON document plus LF; arrays retain their domain order. All results
have exactly `format: "research_pipeline.cli_result"`, `version: 1`, `command`,
`status` (`"ok"` or `"absent"`) and `result`. The result fields are:

| Command | Exact result fields |
| --- | --- |
| `inspect-record` | `record_id`, `revision`, complete `envelope`, `commit` with `submission_id`, `committed_at`, `fingerprint`; envelope/commit both null when absent |
| `inspect-receipt` | `submission_id`, original complete `receipt` (`null` when absent) |
| `inspect-claim-use` | normalized absolute `store`, `use_id`, complete API `inspection` (`null` when absent) |
| `inspect-claim-use-history` | normalized absolute `store`, `use_id`, `after_generation`, `page_limit`, complete API `history` (`null` when absent) |
| `checkout-work-product` | normalized absolute `destination`, complete exact `base`, `descriptor: ".work-product/checkout.json"` |
| `inspect-checkout` | normalized absolute `checkout`, original complete `base` and `envelope`, `observation: "published_descriptor"`, `historical_durability: "unknown"` |
| `prepare-work-product` | normalized absolute `destination`, `proposal_sha256`, `submission_id`, complete exact `base`, `proposed_revision` |
| `inspect-proposal` | normalized absolute `destination`, `state`, `proposal_sha256`, `submission_id`, complete `base`, `proposed_revision`, complete decoded `proposal` and `summary`, `historical_durability: "unknown"` |
| `submit-work-product` | normalized absolute `destination`, `proposal_sha256`, `submission_id`, exact returned complete `receipt` |

Exact record/receipt and saved-product results contain no inferred dates, current
heads, artifact bytes or mutable status summaries. The explicit claim-use commands
pass through complete current-use/history API documents without reconstructing
status views. A registered empty history page is successful and differs from an
absent unregistered use. All nested versions, fields, arrays and causes are retained. Both presence and absence obey output limits. Serialization is bounded
incrementally, including JSON escape expansion and LF. Checkout prepares its
predictable output before reserving the destination; too-small output budgets
cannot create a draft. Output is never intentionally truncated.

| Status | Meaning |
| ---: | --- |
| 0 | Complete acknowledged result, help or version |
| 2 | CLI usage error |
| 3 | Absent store root, exact base/record revision, original submission, selected package or missing/unregistered claim use |
| 4 | Destination collision, stale expected head, used/different submission ID or conflicting saved evidence |
| 5 | Unsafe/invalid controls or layouts, malformed requested values or exceeded limits |
| 6 | Operational failure, corrupt canonical metadata/artifacts, or read-only output failure |
| 7 | Uncertain checkout/preparation/submission effects or output acknowledgment |

A missing store and a missing checkout base produce a diagnostic, without a
fabricated command result. Missing canonical artifact bytes during checkout are
an integrity failure. Except for deliberate absent inspection results, errors
leave stdout empty if output has not begun. A physical write can deliver a prefix
before failing: nonzero status disavows a complete acknowledgment. Never treat
partial JSON, or bytes from a failed flush/close, as successful acknowledgment.

Diagnostics are one ASCII-escaped JSON line on stderr, at most 65536 bytes, with
exactly `format: "research_pipeline.cli_diagnostic"`, `version: 1`, `command`,
`code`, `message`, `context`. The command may be null. Context has exactly `store`,
`destination`, `record_id`, `revision`, `submission_id`, `next_action` for the
work-product/exact-inspection commands above; unavailable values are null. Tool
and readable-view contexts are specified in their guides. Claim-use context has
exactly `config`, `use_id`, `after_generation`, `page_limit`, `next_action`; current
inspection has null cursor/page fields. Only established normalized paths and
validated selections survive refusals. Its limit errors precede generic domain
validation; unsupported schemas are `unsafe_layout`, recognized wrapped metadata
corruption/changed held observations are `integrity_error`, and true chained
EACCES/EIO and database/busy/close failures remain `operational_error`. Claim-use
commands are read-only and never report exit-7 submission uncertainty. Codes are
`missing`, `conflict`, `invalid_input`, `unsafe_layout`,
`limit_exceeded`, `integrity_error`, `operational_error`, `output_failed`, and
`effects_uncertain`. Recovery identities are preserved without dumping private
artifact content or tracebacks. Usage errors retain bounded escaped argparse text.

## Editing and retained-checkout recovery

Checkout selects an exact historical work-product manifest, validates its reserved
namespace/inventory and copies only its directly referenced artifacts. All file
formats are inert; no build dependencies, scripts, notebooks or imported settings
are executed. Files are independent writable mode `0600` copies in private `0700`
directories, with read-only mode `0400` controls. Repeated objects have distinct
copy inodes. Editing with an ordinary editor does not change canonical originals.
An existing file, directory or dangling symlink at the destination is a conflict.
There is no overwrite, reuse, automatic cleanup or finishing an interrupted draft.

The existing [checkout protocol](checkout.md) retains incomplete output on earlier
failure. Unlinking `.work-product/incomplete` is logical publication; later failures
retain the published directory with uncertain synchronization/acknowledgment. The
CLI does not infer publication from exception message wording or promise rollback.
A reportable interruption after checkout begins likewise preserves evidence and
provides recovery guidance; abrupt termination may leave no diagnostic.

For status 7, use the exact `destination` from the diagnostic with:

```bash
python3 -B -m research_pipeline inspect-checkout --checkout /exact/retained/destination
```

This offline read-only operation needs no config/store. It neither inspects edited
product contents nor requires them to exist. Any incomplete marker entry, unsafe,
missing or extra control, changed binding or malformed descriptor refuses normal
inspection. A successful observation describes original local base/envelope data;
it does **not** prove an earlier fsync acknowledgment, authenticated authorship or
scientific support. Review retained evidence before a new checkout attempt, which
must use a new absent destination. After read-only output failure, safely repeat
the same inspection and discard any partial output.

## Authored preparation request

`--request FILE` requires an owned single-link regular `0600` or `0400` file in an
owned `0700` parent, under the same strict UTF-8, depth-64, numeric-token, Unicode,
no-follow/nonblocking, stable-read and close rules as configuration. Exactly these
fields are required; no runtime, source root, destination, limits or protected roots
belong in this authored document:

```json
{
  "format": "research_pipeline.cli_work_product_preparation",
  "version": 1,
  "base": {"record_id": "bundle", "revision": 1, "relationship": "checkout_base", "target_kind": "work_product_manifest"},
  "expected_head": 1,
  "metadata": {
    "product_kind": "note", "title": "Edited note", "purpose": "Explicit local revision",
    "authors": ["Declared editor"], "task": null, "branch": null, "context": null, "run": null,
    "linked_claims": [], "linked_sources": [], "build_dependencies": [],
    "entry_file": "note.txt", "limitations": ["No scientific validation"]
  },
  "selected_paths": ["note.txt"],
  "submission_id": "explicit-edit-1",
  "record_provenance": {"actor": "editor", "created_at": "2026-10-30T13:00:00.000000Z", "details": {}},
  "submission_provenance": {"actor": "submitter", "created_at": "2026-10-30T13:00:00.000000Z", "details": {}}
}
```

`base` is complete and exact. `expected_head` must be an ordinary positive integer
equal to its revision, which must be incrementable within the domain revision
range. Metadata uses exactly the existing [manifest fields](work-product-import.md),
with explicit nulls and complete nested references. Both provenance values contain
all serialized fields, including details and the normalized six-fractional-digit
UTC timestamp. Omitted defaults and coercive equivalents are refused. The ordered,
nonempty `selected_paths` array retains exact portable relative paths, alias and
prefix restrictions, and reserved control namespaces. Omitted old paths are removed
from the proposed manifest, even if still present in the draft. No field is inferred
from an editor, the OS or a current head. The entire request is validated before
reading draft content or publishing objects.

Checkout and saved destination must not overlap each other, runtime, executing
source, explicit protected roots, config or request in either direction. The CLI
also rejects `.work-product-proposal` ancestors, including for new checkout
destinations. A saved package cannot become another operation's writable parent.
No automatic rebase, cleanup, submit, repair or resume option exists. Preview can
leave immutable unreferenced objects on failure; it preserves the edited draft.

## Saved package, inspection and separate submit

A published package has exactly `proposal.json`, `summary.json`, and the directory
`.work-product-proposal`, whose sole entry is `manifest.json`. Directories are owned
`0700`; leaves are owned single-link regular `0400`. Each leaf is accessed relative
to held no-follow parents, with type/mode/link checks before nonblocking open,
actual byte bounds and an EOF probe. Earlier leaf signatures are rechecked after
later reads, detecting observed cross-file substitutions, even with equal bytes.
The trusted-ancestor and same-owner limitations above continue to apply.

All three documents are compact sorted-key ASCII JSON with no trailing newline:

* `proposal.json` is exactly the existing `dumps_prepared_submission` encoding.
  Strict CLI gates precede the existing codec, and canonical re-encoding must equal
  the exact saved bytes. It contains one typed work-product append with immediate
  predecessor CAS. Generic Submission JSON, arbitrary records and generated status
  edits are refused. The CLI selects the whole package, never an arbitrary file.
* `summary.json` has exactly `format: "research_pipeline.cli_work_product_summary"`,
  `version: 1`, `proposal_sha256`, `base_checkout`, `base_submission_provenance`, and
  `changes`. The baseline is the complete original checkout descriptor and the
  base's original submission provenance. `changes` is the existing preview summary:
  additions/removals/changed references, ordered old/new files, metadata, both
  provenance comparisons, revision/supersession and unselected material. Inspection
  recomputes the comparison from these saved values and rejects disagreement.
  Unselected entries have exactly `path`, `path_escaped`, `kind`, `opaque`, sorted by
  path/escaped flag; only directories are opaque. They describe visited directories
  and opaque subtrees, not authenticated evidence of a current draft.
* `manifest.json` has exactly `format: "research_pipeline.cli_saved_work_product"`,
  `version: 1`, `proposal`, `summary`, `submission_id`, `record_id`, `base_revision`,
  and `proposed_revision`. Each file binding has exactly `sha256` (64 lowercase hex
  digits) and `bytes` (ordinary positive integer). Every identity must agree with
  the complete proposal and summary. The SHA-256 of exact `proposal.json` bytes is
  the proposal identity; no additional submission ID or timestamp is generated.

Digests bind internal evidence; they do not authenticate its owner or certify
scientific content. The saved summary is explanatory; the exact proposal alone is
passed to typed admission after the package has been verified.

Preparation exclusively reserves the absent destination as its private preparation
area. It creates and synchronizes an empty
`.work-product-proposal/incomplete` marker and parent directories before writing
payloads. Proposal/summary are written and synchronized first, manifest last. Full
content, inventory and binding gates run before and after synchronization barriers,
immediately before marker removal. **Removing the marker is logical publication.**
The entire directory does not become atomically visible. Collisions preserve the
competitor and all retained material. After publication the command never recreates
the marker, removes the package or claims rollback. Final synchronization, bindings,
resource closes and output acknowledgment must all succeed for status 0.

Offline `inspect-proposal` uses no configuration, store or artifacts and never
synchronizes, repairs, chmods, finishes or cleans evidence. It reports:

| State | Observation |
| --- | --- |
| `absent` | Initial missing-path observation with stable previously held ancestors; outer `status: "absent"`, exit 3 |
| `incomplete` | Early reservation or missing required members before complete evidence exists |
| `complete_unpublished` | Complete verified coherent package with an empty valid marker |
| `published` | Complete verified coherent package without a marker |

Absence and incomplete observations have null proposal, summary and unestablished
identity fields. Loss or substitution of an already observed directory binding is
a conflict, including when an ancestor changes before a missing child is observed.
An observed saved leaf disappearing before opening or during reading is also a
conflict, for both inspection and submission.
Complete states expose verified documents. Malformed available
JSON or unsafe leaves are errors, not ordinary incomplete work. Contradictory
hashes, identities, comparisons, substitutions or impossible inventories are explicit
conflicts. `historical_durability` is always `"unknown"`: present files cannot prove
a past fsync, successful close or stdout acknowledgment.

`submit-work-product` refuses incomplete/unpublished packages and never finishes
them. It synchronizes the verified saved files, control/package/parent directories,
rechecks the entire observation, and successfully closes input resources before
opening the explicit existing store and submitting the detached exact request.
That establishes this invocation's saved-input durability, without certifying a
historical acknowledgment. Declared inventory limits are checked without touching
artifacts. Original-ID reconciliation stays ahead of head/object availability in
the store: identical retries return the original receipt after later head advances,
draft edits/deletion or object loss/damage. New requests still undergo all normal
typed CAS, reference and object admission. Unavailable required objects do not
commit new metadata. Different requests under the same ID conflict.

Preparation and submission reserve predictable bounded success output before
mutations. Submit reserves the full SQLite event-ID width, fingerprint and timestamp
representation without fabricating a receipt. It emits only the exact returned
receipt. Unclassified errors after entering submit, reportable interruptions, and
postcommit resource/output failures retain acknowledgment uncertainty. Read-only
output failures are status 6 and permit repeating inspection.

After preparation uncertainty, run `inspect-proposal` at the exact retained
`destination` in the diagnostic. A preparation retry requires a new absent
destination and recaptures the draft; it is **not original-ID reconciliation**.
After submit uncertainty, use the diagnostic's original `submission_id`:

```bash
python3 -B -m research_pipeline inspect-receipt --config /private/cli/config.json --submission-id explicit-edit-1
python3 -B -m research_pipeline submit-work-product --config /private/cli/config.json --proposal /exact/retained/package
```

When retry is appropriate, use the identical saved package/config. An absent receipt
does not authorize regenerating the request or changing its ID. Stale preparation
and stale saved submission have distinct diagnostics and preserve both drafts.
Neither inspection nor engineering tests confer scientific endorsement. Broader
R-082, scientific/M0-S and runtime/authority obligations remain incomplete.

## Executable synthetic example

The suite executes this block verbatim in a fresh candidate-source interpreter.
Only the initial bundle is seeded through APIs. The temporary parent must be
outside the executing software checkout, as it normally is under `/tmp`.

```python
import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory

from research_pipeline.domain import CreationProvenance, Submission
from research_pipeline.store import RecordStore
from research_pipeline.work_product import WorkProductFile, WorkProductManifest, encode_envelope

with TemporaryDirectory(prefix="local-cli-example-") as temporary:
    parent = Path(temporary)
    runtime, config, draft = parent / "runtime", parent / "config.json", parent / "draft"
    provenance = CreationProvenance("synthetic_author", "2026-10-30T12:00:00Z", {"synthetic": True})
    with RecordStore.create(runtime) as store:
        artifact = store.put_artifact(b"Synthetic note; no scientific validation.\n")
        manifest = WorkProductManifest(
            product_kind="note", title="Synthetic CLI example", purpose="Demonstrate editing",
            authors=["Declared author"], task=None, branch=None, context=None, run=None,
            linked_claims=[], linked_sources=[], supersedes=None, build_dependencies=[],
            files=[WorkProductFile("note.txt", artifact)], entry_file="note.txt",
            limitations=["No scientific validation"],
        )
        envelope = encode_envelope("bundle", 1, manifest, provenance)
        receipt = store.submit_typed(Submission("initial", provenance, [envelope], {"bundle": 0}))
    config.write_text(json.dumps({"format": "research_pipeline.cli_config", "version": 1,
                                 "store": str(runtime), "protected_roots": []}), encoding="utf-8")
    config.chmod(0o600)

    def cli(*arguments, expected=0):
        """Run a real CLI operation, checking its status before parsing acknowledged results or conflicts."""
        process = subprocess.run([sys.executable, "-B", "-m", "research_pipeline", *arguments],
                                 cwd=parent, env=os.environ.copy(), capture_output=True, timeout=30)
        assert process.returncode == expected, process.stderr
        if expected:
            assert process.stdout == b""
            return json.loads(process.stderr)
        assert process.stderr == b""
        return json.loads(process.stdout)["result"]

    original = cli("inspect-record", "--config", str(config), "--record-id", "bundle", "--revision", "1")
    assert original["envelope"] == envelope.to_dict()
    saved_receipt = cli("inspect-receipt", "--config", str(config), "--submission-id", "initial")
    assert saved_receipt["receipt"] == receipt.to_dict()
    checked = cli("checkout-work-product", "--config", str(config), "--record-id", "bundle",
                  "--revision", "1", "--destination", str(draft))
    assert checked["base"]["revision"] == 1
    (draft / "note.txt").write_text("An unsubmitted local edit.\n", encoding="utf-8")
    observed = cli("inspect-checkout", "--checkout", str(draft))
    assert observed["envelope"] == envelope.to_dict()
    assert observed["historical_durability"] == "unknown"
    assert cli("inspect-record", "--config", str(config), "--record-id", "bundle", "--revision", "1") == original
    # This local descriptor is not certification of the edited note or its scientific content.
    competing = parent / "competing-draft"
    cli("checkout-work-product", "--config", str(config), "--record-id", "bundle",
        "--revision", "1", "--destination", str(competing))
    (competing / "note.txt").write_text("An independently edited competing note.\n", encoding="utf-8")
    metadata = dict(product_kind="note", title="Edited synthetic note", purpose="Demonstrate editing",
                    authors=["Declared editor"], task=None, branch=None, context=None, run=None,
                    linked_claims=[], linked_sources=[], build_dependencies=[], entry_file="note.txt",
                    limitations=["No scientific validation"])

    def prepare(identity, checkout, destination):
        """Write a complete authored request and save it with the CLI; never infer identity or submit."""
        request_path = parent / (identity + ".json")
        request_path.write_text(json.dumps(dict(
            format="research_pipeline.cli_work_product_preparation", version=1,
            base=checked["base"], expected_head=1, metadata=metadata, selected_paths=["note.txt"],
            submission_id=identity,
            record_provenance={"actor": "editor", "created_at": "2026-10-30T13:00:00.000000Z", "details": {}},
            submission_provenance={"actor": "submitter", "created_at": "2026-10-30T14:00:00.000000Z", "details": {}}
        )), encoding="utf-8")
        request_path.chmod(0o600)
        return cli("prepare-work-product", "--config", str(config), "--checkout", str(checkout),
                   "--request", str(request_path), "--destination", str(destination))

    package, other = parent / "saved-edit", parent / "saved-competing"
    prepared = prepare("edit-one", draft, package)
    prepare("edit-two", competing, other)
    reviewed = cli("inspect-proposal", "--proposal", str(package))
    assert reviewed["state"] == "published"
    assert reviewed["historical_durability"] == "unknown"
    assert reviewed["proposal_sha256"] == prepared["proposal_sha256"]
    assert reviewed["summary"]["changes"]["paths"][0]["status"] == "changed"
    assert reviewed["summary"]["changes"]["metadata_changes"]["title"]["after"] == metadata["title"]
    assert set(reviewed["summary"]["changes"]["provenance_changes"]) == {"record", "submission"}
    assert json.loads((package / "proposal.json").read_bytes()) == reviewed["proposal"]
    assert cli("inspect-record", "--config", str(config), "--record-id", "bundle", "--revision", "1") == original

    committed = cli("submit-work-product", "--config", str(config), "--proposal", str(package))
    assert committed["submission_id"] == "edit-one"
    historical_two = cli("inspect-record", "--config", str(config), "--record-id", "bundle", "--revision", "2")
    assert historical_two["envelope"] == reviewed["proposal"]["submission"]["records"][0]
    conflict = cli("submit-work-product", "--config", str(config), "--proposal", str(other), expected=4)
    assert conflict["code"] == "conflict"
    assert (competing / "note.txt").read_text() == "An independently edited competing note.\n"
    stale = cli("prepare-work-product", "--config", str(config), "--checkout", str(competing),
                "--request", str(parent / "edit-two.json"), "--destination", str(parent / "stale"), expected=4)
    assert "Preparation conflicts" in stale["message"]
    assert not (parent / "stale").exists()
    # Reconcile the original ID after an imagined lost stdout acknowledgment; do not prepare again.
    original_receipt = cli("inspect-receipt", "--config", str(config), "--submission-id", "edit-one")
    assert original_receipt["receipt"] == committed["receipt"]
    (draft / "note.txt").unlink()
    assert cli("submit-work-product", "--config", str(config), "--proposal", str(package)) == committed
    assert cli("inspect-record", "--config", str(config), "--record-id", "bundle", "--revision", "1") == original
    assert cli("inspect-receipt", "--config", str(config), "--submission-id", "initial")["receipt"] == receipt.to_dict()
```
