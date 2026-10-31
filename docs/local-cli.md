# Local exact inspection and work-product checkout

The source-local foundation provides four bounded operations. Research execution
is unavailable. Declared provenance and author names are attribution, not
authenticated authorship, scientific support or permission. Full R-082, creation
and intake, other draft kinds, snapshot/refresh commands, runtime administration
and research execution remain incomplete. Preview and explicit import are still
[library-only](work-product-import.md); this command slice does not submit metadata.

Put the executing candidate's `implementation/src` first on `PYTHONPATH`, using an
absolute path when changing working directories. No installation is required:

```bash
export PYTHONPATH="$PWD/implementation/src"
python3 -B -m research_pipeline --help
python3 -B -m research_pipeline --version
python3 -B -m research_pipeline inspect-record --config /private/cli/config.json --record-id bundle --revision 1
python3 -B -m research_pipeline inspect-receipt --config /private/cli/config.json --submission-id initial
python3 -B -m research_pipeline checkout-work-product --config /private/cli/config.json --record-id bundle --revision 1 --destination /private/drafts/note
python3 -B -m research_pipeline inspect-checkout --checkout /private/drafts/note
```

No arguments prints help. Every command has `--help`, including units and defaults.
Identifiers and exact revisions are mandatory; there is no current-head default,
positional shortcut, environment-selected store, stdin control, response-file
expansion, generic execution command, plugin or user-selected module. Unknown or
abbreviated options, missing arguments, repeated singleton options and malformed
numeric option syntax are usage errors. Numeric options use ASCII decimal digits.
All options are validated before opening controls, stores or destinations.

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
Limits do not authorize writes or certify content.

| Option | Applicable commands | Default | Range and units |
| --- | --- | ---: | --- |
| `--max-control-bytes` | Config commands | 65536 | 1..1048576 UTF-8 config bytes |
| `--max-output-bytes` | All operations | 2097152 | 1..16777216 ASCII bytes, including LF |
| `--max-metadata-bytes` | Store commands | 2097152 | 1..16777216 selected metadata bytes |
| `--max-links` | Record inspection, checkout | 4096 | 0..65536 record/artifact link occurrences together |
| `--max-receipt-records` | Receipt inspection | 1024 | 1..65536 ordered membership occurrences |
| `--max-descriptor-bytes` | Checkout, checkout inspection | 1048576 | 1..16777216 descriptor bytes |
| `--max-files` | Checkout | 128 | 1..1024 logical files |
| `--max-file-bytes` | Checkout | 16777216 | 0..1073741824 bytes per file |
| `--max-total-bytes` | Checkout | 67108864 | 0..4294967296 logical file bytes |

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

## Machine output and exit statuses

Every machine success or deliberate absence is one complete compact, sorted-key,
ASCII-escaped JSON document plus LF; arrays retain their domain order. All results
have exactly `format: "research_pipeline.cli_result"`, `version: 1`, `command`,
`status` (`"ok"` or `"absent"`) and `result`. The result fields are:

| Command | Exact result fields |
| --- | --- |
| `inspect-record` | `record_id`, `revision`, complete `envelope`, `commit` with `submission_id`, `committed_at`, `fingerprint`; envelope/commit both null when absent |
| `inspect-receipt` | `submission_id`, original complete `receipt` (`null` when absent) |
| `checkout-work-product` | normalized absolute `destination`, complete exact `base`, `descriptor: ".work-product/checkout.json"` |
| `inspect-checkout` | normalized absolute `checkout`, original complete `base` and `envelope`, `observation: "published_descriptor"`, `historical_durability: "unknown"` |

There are no inferred dates, current heads, artifact bytes or mutable status
summaries. Both presence and absence obey output limits. Serialization is bounded
incrementally, including JSON escape expansion and LF. Checkout prepares its
predictable output before reserving the destination; too-small output budgets
cannot create a draft. Output is never intentionally truncated.

| Status | Meaning |
| ---: | --- |
| 0 | Complete acknowledged result, help or version |
| 2 | CLI usage error |
| 3 | Absent store root, exact record revision or original submission |
| 4 | Destination collision/conflict, including an exclusive-creation race |
| 5 | Unsafe/invalid controls or layouts, malformed requested values or exceeded limits |
| 6 | Operational failure, corrupt canonical metadata/artifacts, or read-only output failure |
| 7 | Uncertain checkout effects or output acknowledgment |

A missing store and a missing checkout base produce a diagnostic, without a
fabricated command result. Missing canonical artifact bytes during checkout are
an integrity failure. Except for deliberate absent inspection results, errors
leave stdout empty if output has not begun. A physical write can deliver a prefix
before failing: nonzero status disavows a complete acknowledgment. Never treat
partial JSON, or bytes from a failed flush/close, as successful acknowledgment.

Diagnostics are one ASCII-escaped JSON line on stderr, at most 65536 bytes, with
exactly `format: "research_pipeline.cli_diagnostic"`, `version: 1`, `command`,
`code`, `message`, `context`. The command may be null. Context has exactly `store`,
`destination`, `record_id`, `revision`, `submission_id`, `next_action`; unavailable
values are null. Codes are `missing`, `conflict`, `invalid_input`, `unsafe_layout`,
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

    def cli(*arguments):
        """Run a real CLI operation, requiring complete acknowledgment before parsing its result."""
        process = subprocess.run([sys.executable, "-B", "-m", "research_pipeline", *arguments],
                                 cwd=parent, env=os.environ.copy(), capture_output=True, timeout=30)
        assert process.returncode == 0, process.stderr
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
```
