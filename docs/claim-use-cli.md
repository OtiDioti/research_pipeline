# Current claim-use and generation-history CLI

These two source-local commands expose complete metadata-only observations from
existing private stores. Inspection is a current operational snapshot over
immutable scientific pins. It does not replace the exact historical envelope read
provided by `inspect-record`. An opaque generic `promotion_eligibility` envelope
is not a registered current use.

Put the executing candidate's `implementation/src` first on `PYTHONPATH` (absolute
when changing working directories). No installation or editable-original imports
are required:

```bash
export PYTHONPATH="$PWD/implementation/src"
python3 -B -m research_pipeline inspect-claim-use --config /private/controls/config.json --use-id U
python3 -B -m research_pipeline inspect-claim-use-history --config /private/controls/config.json --use-id U --after-generation 0 --page-limit 1
```

Both commands require exactly one `--config FILE` and `--use-id ID`. IDs contain
1–128 ASCII letters, digits, underscores or hyphens and start with a letter or
digit. Neither command accepts a revision, record selector, limits file, stdin,
environment-selected runtime, automatic pagination or execution option. Unknown,
abbreviated, repeated or missing options and extra positionals are usage errors.
`--help` requires no selections or control/runtime access.

These commands require numeric argv spelling `0` or `[1-9][0-9]*`: ASCII only,
without signs, leading zeros, surrounding whitespace, fractions, exponents or
negative zero. Malformed spelling exits 2. Canonical but oversized or out-of-range
numbers exit 5 with `limit_exceeded`, before any control discovery. All numeric
options, IDs and paths are validated first. Older commands retain their own
numeric syntax, defaults and ranges.

## Independent allowances and selections

Every range is inclusive. Both commands expose the eight allowances below. The
first six map directly into the six required `ClaimUseInspectionLimits` fields.

| Option | Default | Range | Account |
| --- | ---: | --- | --- |
| `--max-bindings` | 512 | 1..512 | Exact binding nodes visited by the public API |
| `--max-records` | 1024 | 1..1024 | Required metadata records |
| `--max-references` | 8192 | 1..8192 | Reference occurrences, including repetitions |
| `--max-assertion-revisions` | 1024 | 1..1024 | Relevant assertion revisions |
| `--max-metadata-bytes` | 67108864 | 1..67108864 | API Reader work/retention reservation bytes, including repeated representations |
| `--max-result-bytes` | 4194304 | 1..4194304 | Complete canonical ASCII domain document, excluding CLI framing and LF |
| `--max-control-bytes` | 65536 | 1..1048576 | Actual authored UTF-8 config bytes, including whitespace |
| `--max-output-bytes` | 8388608 | 1..16777216 | Complete canonical ASCII CLI result, including path escaping, repeated identities, framing, nested document and final LF |

History additionally accepts `--after-generation` (default 0, range
0..9223372036854775807, exclusive generation cursor) and `--page-limit` (default
256, range 1..256, transitions per page). They map to the public API's
`after_generation` and `limit`. Current inspection rejects both options.

The [domain guide](claim-use-freshness.md#current-and-history-apis) specifies the
Reader meanings and fixed internal policy, context, index and cause ceilings.
The CLI forwards all six limits unchanged. History performs only its API's page
work; small unused graph allowances do not cause invented traversal or scientific
certification. Metadata bytes are not domain-result bytes, and neither includes
the full CLI framing. Increasing output cannot bypass metadata or the 4 MiB domain
cap; increasing either domain allowance cannot bypass output. The 8 MiB output
default accommodates a maximum-size domain document plus framing. A smaller
independent output allowance may refuse an otherwise valid API observation.

Accounting includes ASCII escape expansion, supplementary Unicode and repeated
representations. Output is prepared with bounded incremental canonical encoding
before the first stdout byte. No truncation, omitted causes, reduced status views,
placeholder data or incomplete page presented as complete is permitted. These are
selected work/representation accounts, not total RAM, lifetime database-work or
timeout guarantees. They do not bound all store-opening validation/recovery work.

## Exact documents, absence and pagination

Each acknowledged result is one compact sorted-key ASCII-escaped JSON document
plus LF. Arrays retain domain order. The outer object has exactly:

`format: "research_pipeline.cli_result"`, `version: 1`, `command`, `status`, `result`.

| Command | Exact `result` fields |
| --- | --- |
| `inspect-claim-use` | `store`, `use_id`, `inspection` |
| `inspect-claim-use-history` | `store`, `use_id`, `after_generation`, `page_limit`, `history` |

`store` is the normalized absolute explicitly configured runtime. Selection fields
equal the validated invocation. `inspection` and `history` are complete detached
public API `to_dict()` documents, including their own format/version and every
nested field. The wrapper calls its selected public operation once on one opened
store. It does not resolve extra heads, query a second snapshot, verify old
attachments, filter fields, sort domain arrays or recompute causes.

The [claim-use freshness guide](claim-use-freshness.md) defines all nested fields
and versions: schemas 4/5/6/7 retain inspection versions 1/2/3/4, respectively;
history retains version 1. Complete old/bound and new/observed policy, target and
support-context declarations, separate role/occurrence coordinates, conjuncts,
alternatives, shared scopes and original causes pass through unchanged. A
current downstream D pinned to U@1 continues to observe that historical binding
and its old scope after U@2 is registered; current U follows U@2. Nothing redirects
D's pin or adopts the currently active context.

Success is outer `status: "ok"`, exit 0. A missing/unregistered use instead returns
the same result field set with `inspection` or `history` null, outer
`status: "absent"`, exit 3 and no stderr. It never manufactures an empty domain
document. An initially absent runtime produces a `missing` diagnostic, no result
and no creation.

History is generation ordered. Follow the returned `next_cursor` explicitly with
the same ID and a new `--after-generation`. `next_cursor` is the last returned
generation only when more transitions exist; otherwise it is null. Every original
binding, submission, event and cause remains intact. A registered use after its
latest generation, including cursor 9223372036854775807, returns the complete
history document with `transitions: []`, `next_cursor: null`, exit 0. This empty
page differs from absent use. No automatic page collection or certification is
implied; separate invocations can observe subsequent committed transitions.

Inspection preserves `eligible: false`, `requires_reassessment: true`, unavailable
authorized disposition, attributed assertions, unverified independence/execution,
unresolved context transfer, unrecorded premise support and conservative
limitations. `attachment_availability` remains `not_checked_metadata_only`.
Neither command admits metadata, creates a canonical receipt/event/head/generation
or reservation, changes disposition, adopts contexts, extracts artifacts or
executes research. Command success supplies no positive scientific sufficiency,
support, scope certification, authority or promotion. Research execution is
unavailable; R-082 and the broader product remain partial.

## Filesystem trust, errors and acknowledgement

Use the unchanged [version-one local configuration](local-cli.md#trusted-local-configuration-and-filesystem-assumptions)
with exactly `format`, `version`, `store`, `protected_roots`. Runtime and exclusions
are explicit absolute paths; at most 64 distinct normalized protected roots are
allowed. The version is ordinary integer 1. Strict UTF-8 rejects duplicate decoded
keys, invalid Unicode, nonfinite numbers, numeric tokens longer than 128 characters
and container nesting beyond 64. Config whitespace and key order are insignificant;
its preexisting JSON numeric behavior is unchanged.

The config is an owned single-link regular file, mode 0600 or 0400, with an owned
exact-0700 immediate parent. Paths normalize lexically without symlink resolution,
have Unicode scalar values and at most 4096 UTF-8 bytes before/after normalization,
and reject NUL and `..`. Runtime cannot overlap source or protected roots in either
direction; config cannot overlap source, runtime or protected roots in either
direction. Fixed-name no-follow ancestor probes refuse recognizable stores,
backups, checkouts, readable views/refreshes and proposals without reading sentinel
contents. Only the selected runtime and its expected `objects`/`.staging` internals
receive the explicit-runtime exception. Runtime ancestors are held and checked
before opening; expected internals are checked after acquisition.

Initial stat/open agreement, nonblocking no-follow reads, byte bounds and EOF
probes precede checked input closes. Initial leaf signatures are retained before
reading, including when reading/closing fails. Parent-relative leaf observations
and held directory bindings are rechecked on success and failure paths after store
close. Later disappearance, replacement, changed type/signature, directory ownership
or permission changes, or detached earlier ancestors are integrity failures and
cannot acknowledge success, even if the next acquisition fails. An initially
unsafe directory remains an unsafe-layout refusal through failure-path rechecks;
only a successful initial safety check establishes its ownership/permission observation. All
checked held descriptors close before stdout emission. Ancestors outside owned
private controls remain trusted; observations do not sandbox a hostile same-owner
or privileged process.

Opening uses existing `RecordStore.open`, never creation, migration, repair,
cleanup or chmod. Its schema/history validation, five-second busy timeout and
legitimate journal recovery remain in force. Metadata-only does **not** promise
zero physical SQLite writes. Historical attachment loss/damage does not add
verification that the APIs deliberately omit; required canonical metadata and
projection integrity checks remain mandatory. The
[Tool CLI](tool-record-cli.md) separately verifies selected exact Tool direct bytes.

| Exit/code | Meaning |
| --- | --- |
| 2 (argparse usage text) | Missing/unknown/abbreviated/repeated/malformed argv |
| 3 / `missing` | Initially absent explicit runtime (missing use is the silent absent result above) |
| 5 / `limit_exceeded` | Independent work/byte allowance or numeric range exceeded |
| 5 / `invalid_input` | Invalid local selections/configuration, including initially missing config |
| 5 / `unsafe_layout` | Unsafe initial filesystem or unsupported store schema; no migration |
| 6 / `integrity_error` | Recognized canonical metadata/reference/projection corruption or changed held observations |
| 6 / `operational_error` | Real EACCES/EIO and other substantive chained I/O failures, database/busy or checked-close failure |
| 6 / `output_failed` | Output write/progress, flush or close failed |

Diagnostics keep exactly the version-one `research_pipeline.cli_diagnostic`
envelope: `format`, `version`, `command`, `code`, `message`, `context`. For these
commands, context has exactly `config`, `use_id`, `after_generation`, `page_limit`,
`next_action`. Established config is normalized; validated selections are retained;
unavailable/unvalidated values are null. Current inspection has null cursor/page
fields. Explanatory text is bounded by escaped bytes and guidance refers to context
fields without repeating long paths. The entire ASCII diagnostic plus LF is at
most 65536 bytes. Failed subparser-help output uses the same context.

Progressing short stdout writes drain to completion. Zero/invalid progress, early
write loss, a delivered prefix, flush failure or close failure disavows success.
Even physically delivered complete-looking JSON followed by a failed flush/close
has no successful acknowledgement. Require the documented exit status as well as
a complete document; discard failed output before repeating the same read-only
selection. These commands never use submission recovery guidance or exit-7
canonical-submission uncertainty. No automatic retry is performed.

## Executable private-store example

The following delimited program is executed verbatim by a fresh-process test. Run
it with the candidate-local `PYTHONPATH` shown above. It uses only standard-library
and product imports, literal synthetic declarations and an explicit schema-7 store
outside source. No test fixtures or injected setup are required. `/tmp` must be a
writable private-temporary parent outside the source checkout.

```python
import json
import os
import subprocess
import sys
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
from research_pipeline.domain import CreationProvenance, RecordReference, RecordEnvelope, Submission
from research_pipeline.scientific import ResearchContext, Claim, Justification, Evidence, encode_envelope
from research_pipeline.assessment import (Review, IndependenceDeclaration, SubstantiveAssessment,
    SupportRouteAssessment, encode_envelope as assessment_envelope)
from research_pipeline.claim_use import (ClaimUse, ClaimUsePremise, ClaimUseRoute,
    ClaimUseInspectionLimits, encode_envelope as use_envelope)
from research_pipeline.store import RecordStore

creator = CreationProvenance("synthetic-example", "2026-11-06T00:00:00Z")
limits = ClaimUseInspectionLimits(512, 1024, 8192, 1024, 67108864, 4194304)

def ref(identity, role, kind, revision=1):
    """Declare an exact pin without conferring authority."""
    return RecordReference(identity, revision, role, kind)

def batch(identity, records):
    """Retain the complete original request and explicit expected-head CAS."""
    return Submission(identity, creator, records, {r.record_id: r.revision-1 for r in records})

def review(candidate, route):
    """Declare an attributed route assessment; favorable words confer no permission."""
    return Review(ref(candidate, "candidate_claim", "claim"), ref("target", "target_context", "research_context"),
        "synthetic reviewer", IndependenceDeclaration("candidate_aware_audit", "candidate_aware_audit",
        [], [], [], [], [], [], []), ref("manifest", "context_manifest", "work_product_manifest"),
        ref("policy", "authorization_policy", "decision"), [],
        SubstantiveAssessment("under_review", "supported_within_scope", ["analytical"], "applicable",
        "unassessed", "Attributed only", [], [], []),
        [SupportRouteAssessment(ref(route, "assessed_route", "justification"), "sufficient", "Unverified", [], [])],
        [], [], [], "synthetic")

def use(candidate, routes=(), target="target"):
    """Bind only selected exact support; status is supplied by the store."""
    return ClaimUse(ref(candidate, "candidate_claim", "claim"), ref(target, "target_context", "research_context"),
        list(routes), [], [ref("policy", "authorization_policy", "decision")], ["Synthetic only"])

with TemporaryDirectory(prefix="claim-use-cli-", dir="/tmp") as temporary:
    root = Path(temporary)/"store"
    with RecordStore.create(root, schema_version=7) as store:
        store.submit(batch("declarations", [RecordEnvelope("policy", 1, "decision", {}, creator),
            RecordEnvelope("manifest", 1, "work_product_manifest", {}, creator)]))
        scope = ResearchContext("Synthetic scope", ["f(x)=x"], ["x is real"], [], [], ["R"], [], [], [], [], [])
        science = [encode_envelope(i, 1, replace(scope, question=i), creator) for i in
            ("candidate-scope", "route-scope", "premise-scope", "evidence-scope", "target", "down-scope", "independent")]
        for identity, context in (("candidate", "candidate-scope"), ("premise", "premise-scope"),
                                  ("down", "down-scope"), ("independent-claim", "independent")):
            science.append(encode_envelope(identity, 1, Claim(identity, "synthetic", [],
                ref(context, "context", "research_context"), [], [], []), creator))
        artifact = store.put_artifact(b"synthetic evidence")
        evidence = Evidence([artifact], ref("evidence-scope", "context", "research_context"), "identity",
            [], "declared method", [], [], [], "unverified", [], [], "synthetic")
        science.append(encode_envelope("evidence", 1, evidence, creator))
        for identity, candidate, premise, context, evidence_refs in (
                ("route", "candidate", "premise", "route-scope", [ref("evidence", "evidence", "evidence")]),
                ("down-route", "down", "candidate", "down-scope", [])):
            science.append(encode_envelope(identity, 1, Justification(ref(context, "context", "research_context"),
                [ref(premise, "premise", "claim")], [], "declared method",
                [ref(candidate, "conclusion", "claim")], evidence_refs, []), creator))
            science.append(assessment_envelope(identity+"-review", 1, review(candidate, identity), creator))
        store.submit_typed(batch("science", science))
        route = ClaimUseRoute(ref("route", "support_route", "justification"),
            [ClaimUsePremise(ref("premise", "premise", "claim"), None)],
            [ref("route-review", "support_assessment", "review")])
        downstream = ClaimUseRoute(ref("down-route", "support_route", "justification"),
            [ClaimUsePremise(ref("candidate", "premise", "claim"), ref("U", "premise_use", "promotion_eligibility"))],
            [ref("down-route-review", "support_assessment", "review")])
        original = batch("register", [use_envelope("D", 1, use("down", [downstream]), creator),
            use_envelope("U", 1, use("candidate", [route]), creator),
            use_envelope("I", 1, use("independent-claim", target="independent"), creator)])
        receipt = store.submit_typed(original)  # D's forward U@1 pin is exact.
        historical = store.inspect_claim_use("U", limits=limits).to_dict()["binding"]
        advance = batch("advance-evidence-scope", [encode_envelope("evidence-scope", 2,
            replace(scope, question="Potentially material prose change"), creator)])
        advanced_receipt = store.submit(advance)
        upstream = store.inspect_claim_use("U", limits=limits).to_dict()
        downstream_view = store.inspect_claim_use("D", limits=limits).to_dict()
        assert upstream["version"] == 4 and upstream["generation"] == downstream_view["generation"] == 2
        assert store.inspect_claim_use("I", limits=limits).to_dict()["generation"] == 1
        assert {o["source_role"] for o in upstream["observed_support_contexts"]} == {
            "candidate_claim", "support_route", "premise", "evidence"}
        occurrence = upstream["observed_support_contexts"][3]
        assert occurrence["source"] == {"record_id": "evidence", "revision": 1, "target_kind": "evidence"}
        assert occurrence["binding"] == {"record_id": "U", "revision": 1, "target_kind": "promotion_eligibility"}
        assert (occurrence["route_ordinal"], occurrence["premise_ordinal"], occurrence["evidence_ordinal"]) == (0, -1, 0)
        assert occurrence["bound_context"]["revision"] == 1 and occurrence["observed_context"]["revision"] == 2
        assert occurrence["bound_content"]["question"] == "evidence-scope"
        assert occurrence["observed_content"]["question"] == "Potentially material prose change"
        assert occurrence["superseded"] and occurrence["attributed"]
        assert upstream["binding"] == historical == downstream_view["upstream_bindings"][0]
        assert any(c["type"] == "support_context_changed" for c in downstream_view["mechanical_freshness"]["last_transition"]["causes"])
        assert not upstream["eligible"] and upstream["requires_reassessment"]
        assert not upstream["authorized_disposition"]["available"]
        assert any("Evidence evidence@1" in s for s in upstream["limitations"])
        # Rebinding U does not redirect D's immutable U@1 upstream pin.
        store.submit_typed(batch("rebind-U", [use_envelope("U", 2,
            use("independent-claim", target="independent"), creator)]))
        store.submit(batch("old-scope-again", [encode_envelope("evidence-scope", 3,
            replace(scope, question="Old historical support changed again"), creator)]))
        assert store.inspect_claim_use("D", limits=limits).to_dict()["upstream_bindings"][0] == historical
        expected_inspection = store.inspect_claim_use("D", limits=limits).to_dict()
        expected_history = store.claim_use_history("D", limits=limits).to_dict()
    config = Path(temporary)/"config.json"
    config.write_text(json.dumps({"format": "research_pipeline.cli_config", "version": 1,
        "store": str(root), "protected_roots": []}), encoding="utf-8")
    config.chmod(0o600)

    def cli(command, **selections):
        """Run an actual candidate CLI and require canonical bytes and acknowledged complete output."""
        arguments = [sys.executable, "-B", "-m", "research_pipeline", command,
                     "--config", str(config), "--use-id", "D"]
        for name, value in selections.items():
            arguments.extend(["--"+name.replace("_", "-"), str(value)])
        process = subprocess.run(arguments, cwd=temporary, env=os.environ.copy(),
                                 capture_output=True, timeout=30)
        assert process.returncode == 0, process.stderr
        assert process.stderr == b""
        outer = json.loads(process.stdout)
        assert process.stdout == (json.dumps(outer, sort_keys=True, separators=(",", ":"),
            ensure_ascii=True, allow_nan=False)+"\n").encode("ascii")
        assert set(outer) == {"format", "version", "command", "status", "result"}
        assert outer["format"] == "research_pipeline.cli_result" and outer["version"] == 1
        assert outer["command"] == command and outer["status"] == "ok"
        assert outer["result"]["store"] == str(root) and outer["result"]["use_id"] == "D"
        return outer["result"]

    current = cli("inspect-claim-use")
    assert set(current) == {"store", "use_id", "inspection"}
    assert current["inspection"] == expected_inspection
    complete = cli("inspect-claim-use-history")
    assert set(complete) == {"store", "use_id", "after_generation", "page_limit", "history"}
    assert complete["after_generation"] == 0 and complete["page_limit"] == 256
    assert complete["history"] == expected_history
    cursor, transitions = 0, []
    while True:
        page = cli("inspect-claim-use-history", after_generation=cursor, page_limit=1)
        with RecordStore.open(root) as store:
            assert page["history"] == store.claim_use_history("D", after_generation=cursor,
                limit=1, limits=limits).to_dict()
        transitions.extend(page["history"]["transitions"])
        following = page["history"]["next_cursor"]
        if following is None:
            break
        cursor = following
    assert transitions == expected_history["transitions"]
    empty = cli("inspect-claim-use-history", after_generation=9223372036854775807)
    assert empty["history"]["transitions"] == [] and empty["history"]["next_cursor"] is None
    with RecordStore.open(root) as store:
        assert empty["history"] == store.claim_use_history("D", after_generation=9223372036854775807,
            limits=limits).to_dict()
    # Successful mechanical observations never certify scientific support or authority.
```
