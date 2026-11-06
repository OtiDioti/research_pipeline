# Saved Source-proposal CLI

Inspect a caller's already saved ordinary Source proposal offline, then explicitly
submit that exact request to an existing runtime. Preparation remains **library-only**
through [prepare_source_capture](source-capture.md); saving/publication is caller-controlled.
These commands neither acquire original material nor execute supplied content.
Put the candidate's `implementation/src` first on `PYTHONPATH`; installation is unnecessary.

```text
python3 -B -m research_pipeline inspect-source-proposal --config FILE --proposal FILE [LIMIT OPTIONS]
python3 -B -m research_pipeline submit-source-capture --config FILE --proposal FILE [LIMIT OPTIONS]
```

Both controls are required. There are no positional inputs, optional config,
environment-selected paths, stdin, separate IDs/revisions, limits file, kind selector,
preparation/publication switch or automatic retry. `--help` requires no controls or
runtime access. Unknown, abbreviated, repeated or missing options exit 2. All six
accounts use numeric spelling `0` or `[1-9][0-9]*`; leading zeros, signs, whitespace,
Unicode digits, fractional and exponent aliases exit 2. Canonical oversized or
out-of-range numbers produce `limit_exceeded`. Existing commands retain their contracts.
Every argv value is validated before acquisition.

## Controls and trust boundary

Config is the unchanged [version-one local CLI config](local-cli.md), with exactly
`format="research_pipeline.cli_config"`, ordinary integer `version=1`, absolute
`store` and explicit `protected_roots` array (at most 64 distinct normalized paths).
Inspection requires config solely to establish trusted exclusions. It does not
open or stat the configured runtime to test availability; absent, unreadable or
otherwise unavailable runtime and absent/poisoned original inputs do not prevent
inspection of a valid proposal.

Control paths normalize lexically to absolute paths without resolving symlinks.
They require Unicode scalar strings of at most 4096 UTF-8 bytes before and after
normalization, without NUL or parent traversal. Both leaves must be owned,
single-link regular files, mode 0600 or 0400, in owned exact-0700 immediate parents.
Nonblocking no-follow reads retain initial signatures, bounded reads/EOF probes,
checked closes and held directories. Fixed-name ancestor probes reject recognizable
storage, backup, checkout, readable-view/refresh and proposal layouts without
listing directories or reading sentinel contents. Control overlap with executing
source is refused before control acquisition where lexically detectable. Runtime
cannot overlap source/protected roots; controls cannot overlap those roots, runtime
or one another in either direction. Source declarations never choose exclusions,
operating paths, permissions or allowances.

Held leaf/directory observations remain pinned through store close and final
reobservation, including failed later acquisitions. Initially unsafe layouts remain
`unsafe_layout`; later identity/type/uid/gid/mode changes to established directories
are integrity failures, including changes to otherwise permitted tuples. Directory
size/mtime are not compared. Checked input, store and held-directory closes precede
stdout. These trusted-owner/mount observations do not sandbox a hostile same-owner
or privileged process or detect filesystem aliases omitted from trusted exclusions.

Strict UTF-8 parsing rejects duplicate decoded keys, unpaired surrogates, nonfinite
numbers, numeric tokens longer than 128 characters and more than 64 container levels
before domain reconstruction. Source retains its existing JSON numeric semantics,
including integer negative zero in descriptive JSON. Excessive authored depth is
`invalid_input`. The existing pure `loads_prepared_submission` and
`dumps_prepared_submission` own all Source validation: exactly
`{format:"research_pipeline.source_capture_submission",version:1,submission:<complete Submission>}`,
one coherent Source envelope and `expected_heads={record_id:revision-1}`. Complete
nested fields and ordered projections are required; no defaults, inferred declarations
or normalization are inserted. Equivalent whitespace/key ordering/string escapes
are accepted. Work-product packages, Tool/generic/mixed batches and unsupported
wrappers are refused without fallback. Hashing and decoding never rewrite the file.

Inspection reads only its selected controls and necessary ancestor observations.
It opens no RecordStore, scientific locator, artifact or reference; performs no
head/history/receipt/admission/backup operation; and does not prepare a capture.
It establishes no admission, execution, original-byte authenticity, durability,
scientific support, authentication or permission. Attributed restrictions, reading,
unknowns and limitations remain declarations. A locally valid request can fail fresh
historical admission.

## Independent finite accounts

All six options are always finite and independently enforced; ranges are inclusive.
Actual UTF-8 file bytes include whitespace. Canonical JSON counts use compact,
sorted-key, ASCII encoding, including supplementary Unicode escape expansion and
every repeated nested occurrence. Nothing is omitted or truncated to fit.

| Option | Default | Range | Account |
| --- | ---: | --- | --- |
| `--max-control-bytes` | 65536 | 1..1048576 | Actual UTF-8 config bytes |
| `--max-proposal-bytes` | 2097152 | 1..16777216 | Actual UTF-8 saved-file bytes |
| `--max-metadata-bytes` | 16777216 | 1..67108864 | Two complete canonical Submission representations |
| `--max-result-bytes` | 4194304 | 1..16777216 | Complete canonical Source wrapper (inspection) or receipt (submission), excluding CLI framing/LF |
| `--max-serialization-bytes` | 67108864 | 1..134217728 | Aggregate adapter representation/serialization reservation below |
| `--max-output-bytes` | 8388608 | 1..16777216 | Complete canonical CLI document including LF |

Let `J` denote that JSON encoding, `S=bytes(J(complete Submission))`,
`P=bytes(J(complete saved wrapper))`,
`F=bytes(J({fingerprint_version:1,submission:<complete Submission>}))`,
`D=bytes(J(domain result))`, and `O=bytes(J(outer CLI success document excluding LF))`.
Metadata requires `2*S`; serialization requires `2*S + 2*P + F + D + O + 1`.
Repeated raw/revalidated request, wrapper, domain and output representations count
independently. These are conservative adapter work/representation reservations,
not total RAM, all internal codec allocations, total store work or wall-clock bounds.
Counting is incremental before whole escaped representations are allocated. Raw S/P
and preliminary serialization gates precede pure reconstruction; every full success
reservation precedes store opening. Actual output is checked again.

For submission, D/O reserve the complete saved-request receipt using its exact ID,
provenance and ordered revision pairs, a 64-character fingerprint, maximum signed-64-bit
event ID and `9999-12-31T23:59:59.999999Z`. Those are sizing placeholders and are never
emitted as receipts. Returned receipt type, original identity/provenance/membership,
scalar bounds, reserved bytes and semantic fingerprint are validated before success.
Increasing another allowance cannot bypass a smaller account. A locally over-limit
retry fails locally: retain sufficient original-request limits. No artifact-read
accounts are needed because this adapter performs no artifact reads. Existing
Source codec and store ceilings remain unchanged.

## Complete results and acknowledgement

Success is exit 0 and exactly one compact sorted-key ASCII
`research_pipeline.cli_result` version-1 document plus LF, with command and status `ok`.
Array order, repeated inventory occurrences and all declared fields are preserved.
Inspection result fields are exactly `proposal_path`, `proposal_sha256`,
`submission_fingerprint`, `proposal`. `proposal_path` is normalized absolute;
`proposal` is the complete decoded canonical version-one Source wrapper, including
Submission and Source envelope. There is no invented `input_root` or reconstructed
`PreparedSourceCapture.mapping`.

Submission result fields are exactly `store`, `proposal_path`, `proposal_sha256`,
`submission_fingerprint`, `receipt`. The receipt is the complete actual API document.
No fresh/replayed/admitted label or history decoration is added. `proposal_sha256`
hashes actual saved bytes; `submission_fingerprint` hashes ASCII
`J({fingerprint_version:1,submission:<complete decoded Submission.to_dict()>})`, matching
the store. Neither authenticates provenance or proves a commit.

Submission opens only the configured **existing** runtime, with existing
runtime/objects/.staging checks and `RecordStore.open` schema validation, five-second
busy timeout and legitimate recovery. It creates, migrates, repairs or cleans no
runtime; normal opening/recovery may physically write SQLite state. After predictable
capacity checks and immediate control reobservation, it calls `submit_typed` exactly
once with the detached loaded request. No CLI input reread, head/reference/history,
admission preview, backup, receipt or artifact check precedes that call. Store-owned
opening and internal submission retain their semantics. Fresh requests retain exact
CAS, Source continuity/stable work identity, constrained/shallow links and direct-byte
admission. Schema 1 may open but refuses fresh Source admission; it is not migrated.

## Diagnostics and original-ID recovery

Errors retain `research_pipeline.cli_diagnostic` version 1, capped at 65536 ASCII
bytes including LF. Context fields are exactly `config`, `proposal`, `record_id`,
`revision`, `submission_id`, `proposal_sha256`, `submission_fingerprint`, `next_action`.
Unavailable/unvalidated values are null. Paths and identities are retained only
after validation; runtime is omitted so two worst-case escaped control paths fit.
Guidance refers to context rather than repeating paths.

| Exit | Category | Meaning |
| ---: | --- | --- |
| 2 | usage | Invalid argv spelling/shape |
| 3 | missing | Initially absent proposal or configured runtime; absent config is invalid input |
| 4 | conflict | CAS or changed request under an original ID |
| 5 | invalid_input | Malformed config/proposal or local domain refusal |
| 5 | limit_exceeded | Independent finite account overflow |
| 5 | unsafe_layout | Initially unsafe controls/layout or unsupported store schema |
| 6 | integrity_error | Recognized canonical/reference/artifact or held-observation corruption |
| 6 | operational_error | Substantive chained EACCES/EIO, read/open/busy/checked-close failure before submission |
| 6 | output_failed | Inspection/help acknowledgement failed; no canonical submission effect |
| 7 | effects_uncertain | Unknown operational/interruption failure after entry, or any post-return conversion/observation/close failure |
| 7 | output_failed | Submission acknowledgement failed; canonical effects may already exist |

Known deterministic domain/limit/conflict/reference/artifact refusals keep meaningful
categories after entry. Real I/O causes are not hidden by outer integrity wrappers.
A failed final observation after possible submission preserves uncertainty. Success
requires checked write progress, flush and close: complete-looking physically
delivered JSON alone does not acknowledge success. Discard partial output. Inspection
and help failures suggest only repeating the same offline request.

On uncertain submission, retain the original config/runtime, proposal, ID and limits:

```text
python3 -B -m research_pipeline inspect-receipt --config FILE --submission-id ORIGINAL_ID
python3 -B -m research_pipeline submit-source-capture --config FILE --proposal ORIGINAL_FILE [SUFFICIENT ORIGINAL-REQUEST LIMITS]
```

Identical original-ID retries return their original receipt after reopen, later heads,
edited/deleted inputs and historical artifact damage permitted by the store contract,
without new records/events/receipts/generations/resource effects. Changed valid reuse
conflicts. Receipt absence does not authorize changing/regenerating the request,
refreshing expected heads, rebasing, recapturing, cleanup or replacement IDs. Never
infer rollback from exception wording or output failure; no automatic recovery occurs.

## Executable private-store example

This delimited standard-library/product-only synthetic program is executed verbatim
by a test in a fresh candidate-source interpreter. Capture preparation is library-only.
Saving remains an exclusive ordinary-file operation with explicit privacy, flush,
file fsync, parent fsync and pure reload. No new product publisher or sidecar is used.

<!-- source-capture-cli-example:begin -->
```python
import os
import json
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
import research_pipeline.source_capture as capture_api
from research_pipeline.domain import CreationProvenance
from research_pipeline.source import (
    DeclaredText, Source, SourceDeclaration, SourceProvenance,
    SourceReading, SourceRestrictions,
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
    parent.chmod(0o700)
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
        descriptor = os.open(proposal, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        with os.fdopen(descriptor, "wb") as stream:
            os.fchmod(stream.fileno(), 0o600)
            stream.write(frozen.encode("ascii"))
            stream.flush()
            os.fsync(stream.fileno())
        directory_fd = os.open(parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
        saved = loads_prepared_submission(proposal.read_bytes())
        assert dumps_prepared_submission(saved) == frozen
    config = parent / "config.json"
    config.write_text(json.dumps(dict(format="research_pipeline.cli_config", version=1,
        store=str(parent / "runtime"), protected_roots=[])), encoding="utf-8")
    config.chmod(0o600)

    def cli(command, *selection):
        """Require checked CLI acknowledgement and decode its complete domain document."""
        result = subprocess.run([sys.executable, "-B", "-m", "research_pipeline", command,
            "--config", str(config), *map(str, selection)], capture_output=True, timeout=30)
        assert result.returncode == 0, result.stderr.decode(errors="replace")
        assert result.stderr == b""
        return json.loads(result.stdout)["result"]

    inspected = cli("inspect-source-proposal", "--proposal", proposal)
    assert inspected["proposal"] == json.loads(dumps_prepared_submission(saved))
    assert "input_root" not in inspected and "mapping" not in inspected
    committed = cli("submit-source-capture", "--proposal", proposal)
    receipt = committed["receipt"]
    assert receipt["fingerprint"] == inspected["submission_fingerprint"]
    assert proposal.read_bytes() == frozen.encode("ascii")
    assert selected_path.read_bytes() == payload
    assert selected_path.stat().st_mode & 0o7777 == 0o644
    selected_path.unlink()  # Caller deletion after capture; the CLI never edits inputs.
    assert cli("inspect-source-proposal", "--proposal", proposal) == inspected
    assert cli("inspect-receipt", "--submission-id", saved.submission_id)["receipt"] == receipt
    with RecordStore.open(parent / "runtime") as store:
        events = store.audit_events()
        assert store.get_typed_revision("capture", 1)[0] == saved.records[0]
    assert cli("submit-source-capture", "--proposal", proposal) == committed
    with RecordStore.open(parent / "runtime") as reopened:
        assert reopened.get_submission(saved.submission_id).to_dict() == receipt
        assert reopened.audit_events() == events
```
<!-- source-capture-cli-example:end -->

Source preparation/publication follow-up, remaining CLI/intake/seed/project/readiness
work, all 94 requirements and 13 FOLLOWON obligations, and scientific/live/human
duties remain mandatory. This milestone completes neither R-082 nor the product;
no scientific readiness, disposition, promotion, worker authority or active-context
adoption follows from these local operations.
