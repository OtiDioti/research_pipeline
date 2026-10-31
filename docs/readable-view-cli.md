# Immutable readable views through the local CLI

These four source-local commands expose the existing [snapshot](readable-snapshots.md)
and [preserved refresh](readable-refresh.md) APIs. They neither import edits nor
activate configuration, submit metadata, execute research or grant export permission.
The [local CLI contract](local-cli.md) also governs configuration, output and saved
work-product round trips. Full research/runtime and broader R-082 obligations remain pending.

```text
generate-readable-view --config FILE --limits FILE --selection FILE --destination PATH
refresh-readable-view --config FILE --limits FILE --selection FILE --prior-view PATH --baseline-manifest FILE --expected-base-plan-id SHA256 --expected-base-manifest-sha256 SHA256 --destination PATH
inspect-readable-view --config FILE --limits FILE --view PATH [--expected-plan-id SHA256]
inspect-readable-refresh --config FILE --limits FILE --attempt PATH --destination PATH [--expected-refresh-id SHA256]
```

Invoke each using `python3 -B -m research_pipeline` with an absolute candidate-local
`implementation/src` on `PYTHONPATH`. All options are singletons. There are no
positionals, abbreviations, environment settings, stdin controls or execution hooks.
Pins are exactly 64 lowercase hexadecimal characters. Scalar options are validated
before inputs open. The required config is the unchanged
`research_pipeline.cli_config` version 1 schema: exactly `format`, `version`,
absolute `store`, and explicit `protected_roots`. Offline commands use it only for
exclusions: the runtime can be absent and is never opened or created.

## Complete authored controls

A selection has exactly these fields. Every selector requires `revision`; ordinary
integer 1..9223372036854775807 means exact, and explicit `null` means current head.
Missing revision is invalid. `roots` is a required ordered array, including `[]`.
Domain identifier and duplicate-selector rules apply. Capture resolves the project
first, then ordered roots, and retains historical outgoing links even after a head advances.

```json
{"format":"research_pipeline.cli_snapshot_selection","version":1,"project":{"record_id":"project","revision":1},"roots":[]}
```

Every limits file has exactly `format: "research_pipeline.cli_readable_limits"`,
ordinary integer `version: 1`, `command` equal to the invoking command, and:

| Command | Required additional fields |
| --- | --- |
| `generate-readable-view` | `snapshot_limits`, `view_limits` |
| `refresh-readable-view` | `snapshot_limits`, `refresh_limits` |
| `inspect-readable-view` | `view_limits` |
| `inspect-readable-refresh` | `refresh_limits` |

`snapshot_limits` and every `plan_limits`/`successor_limits` have exactly
`max_roots`, `max_records`, `max_references`, `max_record_bytes`,
`max_metadata_bytes`, `max_artifacts`, `max_files`, `max_file_bytes`, `max_total_bytes`.
`view_limits` has exactly `plan_limits`, `max_entries`, `max_depth`, `max_open_descriptors`.
`refresh_limits` has exactly `capture_limits`, `successor_limits`, plus the nine
scalar fields `max_entries`, `max_files`, `max_directories`, `max_depth`,
`max_file_bytes`, `max_total_bytes`, `max_metadata_bytes`, `max_diagnostics`,
`max_open_descriptors`. `capture_limits` has exactly `plan_limits` and those same
nine scalar fields. Each group is independently decoded. There are no inherited
values, nested defaults or coercions. The executable example below writes complete
working documents for all commands; its values are caller choices, not defaults.

All numeric limits require ordinary integers; booleans and floats are invalid.
Every occurrence has the following inclusive ceiling:

| Field | Ceiling |
| --- | ---: |
| `max_roots` | 1024 |
| `max_records`, `max_references`, `max_artifacts`, `max_files`, `max_entries`, `max_directories`, `max_diagnostics` | 65536 |
| `max_record_bytes` | 16777216 |
| `max_metadata_bytes` | 268435456 |
| `max_file_bytes` | 1073741824 |
| `max_total_bytes` | 4294967296 |
| `max_depth` | 64 |
| `max_open_descriptors` | 4096 |

Minima are 1 except snapshot `max_references`, `max_artifacts`, `max_total_bytes`
permit 0, and capture/refresh `max_file_bytes`, `max_total_bytes` permit 0.
Wrong types are `invalid_input`; integers outside the range are `limit_exceeded`.

All four commands retain `--max-control-bytes` (default 65536, range
1..1048576) per config/limits file and `--max-output-bytes` (default 2097152,
range 1..16777216), including the final LF. Both writers have
`--max-selection-bytes` (default 65536, range 1..1048576). Refresh and view
inspection have `--max-manifest-bytes` (default 16777216, range 1..67108864).
The historical manifest must also fit its independently supplied plan's
`max_file_bytes` and `max_total_bytes`.

Authored JSON uses strict UTF-8, duplicate/unknown-field rejection, finite scalar
values, numeric tokens at most 128 characters and nesting at most 64. Historical
manifests instead go directly from stable bounded raw bytes to the existing
canonical ASCII reconstruction boundary, which allows 69 wrapper levels for
stored depth-64 provenance. Whitespace changes are noncanonical. Every embedded
allowance must fit its corresponding independently supplied allowance even if
actual content is small. Embedded limits are never rewritten to force admission.

## Filesystem and admission boundaries

Controls are owned single-link regular leaves, mode `0400` or `0600`, in existing
owned `0700` parents. Held no-follow directories and bounded reads with EOF probes,
binding comparisons and checked closes reject observed replacement, growth,
truncation and disappearance of held ancestors as integrity failures. Initially
absent explicit inputs remain missing-input failures. Parents are never created.
Paths are normalized lexically and limited to 4096 UTF-8 bytes, including derived
output paths. Refresh admits its complete successor and preservation inventory
(including native/authored descendants, empty directories and controls) beneath
both the destination and preparation roots before reserving any output. The actual
attempt root and all possible evidence markers are also bounded. Equality at 4096
bytes is permitted. The complete executing checkout,
configured runtime, protected roots and explicit controls are excluded in both
containment directions. Runtime versus source/protected-root checks remain lexical
even offline. Recognizable storage, backup, checkout, proposal, view and refresh
ancestors are refused without arbitrary scans. The exact `generation` child of a
published refresh package is supported as a view or subsequent prior; arbitrary
traversal through `preservation` is not.

Initial and refresh destinations must be absent (including no dangling symlink)
under an existing owned `0700` parent. No in-place replacement, current pointer,
cleanup, replay or automatic retry exists. Copies have independent inodes.
Baseline manifests must be independently retained outside prior, destination,
source, runtime and protected trees in both directions, with safe control ancestry.
A baseline in a sibling private controls directory is valid. Hardlinks are refused.
Both exact-byte SHA-256 and reconstructed plan ID must match supplied pins before
opening the store or reading prior payloads. Pins and baselines are caller assertions,
not authenticated scientific history. Retaining an already edited prior manifest
cannot establish which historical base was intended.

Generation captures metadata exactly once, plans without artifact reads, then
reconstructs under independent view plan limits before materializing. Refresh
captures once and delegates prior preservation and successor publication with
independent capture/successor/outer allowances. Same-plan refresh still publishes
a new package. Opening a live store retains legitimate journal recovery semantics.

For generation and view inspection, canonical relative depth counts POSIX components,
with root at zero. Admission reserves `R = 64 + 2*A + 2*D + 2*F + 2*U` descriptors.
`A` is the sum of normalized destination-parent and runtime ancestor-component counts
for generation, or selected-view ancestor-component count for inspection (including
root). `D` is canonical directories including root; `F` is generated files plus artifact
copies; `U` is distinct copied canonical digests for generation, zero for inspection.
The ancestor-only reservation precedes traversal. The constant and doubled terms
cover adapter pins, transient descriptors, source pins and traversal; this is a
conservative admission reservation, not exact observed usage.

Refresh preflight separately requires `P + 1 <= capture_limits.max_open_descriptors`
and `64 + 2*max(B + 1, D + P + 1, D + R + 2) <= max_open_descriptors` in
`refresh_limits`. Here `B`, `D`, `P` and `R` count normalized path components,
including root, for the baseline parent, destination parent, prior view and runtime.
The terms cover sequential baseline reading, simultaneous destination/prior guards,
and simultaneous destination/runtime guards plus `objects` and `.staging`.
Independent traversals do not share descriptors even for common ancestors; doubled
terms allow the store's independent runtime traversal and the fixed reserve covers
transient descriptors and store resources. Neither allowance compensates for the other.
Admission occurs immediately after limits decoding, before baseline or preflight
chain acquisition. Config/limits bootstrap reads close sequentially. Prior guards
close before runtime opening, and adapter guards close before library entry. The
library continues to enforce its separate nested and outer depth/descriptor accounting.

View inspection performs one bounded manifest preflight, pins that observation,
admits canonical depth/descriptors, then requires the API's identities and hash to
match. Both passes are bounded; these limits do not promise one lifetime physical-read
budget. Unexpected subtrees retain the inspector's non-traversal behavior. Selected-data
and per-pass limits do not bound total SQLite validation/recovery work, elapsed wall
time or OS resource availability. Local mutation checks do not defeat a coherent
hostile same-owner or privileged rewrite.

## Output, failures and recovery

Success is compact sorted ASCII JSON plus LF in the unchanged
`research_pipeline.cli_result` version 1 envelope, with `command`, `status: "ok"`
and `result`. Successful observations, including divergence or incomplete evidence,
exit 0; they are not acceptance verdicts. Result field sets are exactly:

- Generation: `snapshot_id`, `plan_id`, `manifest_sha256`, `destination`, `attempt_path`,
  `verification`, `selection`, `resolutions`.
- Refresh: `refresh_id`, `prior_view`, `prior_snapshot_id`, `prior_plan_id`, `capture_id`,
  `preservation_plan_id`, `successor_snapshot_id`, `successor_plan_id`, `destination`,
  `successor_path`, `preservation_path`, `attempt_path`, `same_plan`, `verification`,
  `selection`, `resolutions`, `baseline_manifest_sha256`.
- View inspection: normalized `view`, `snapshot_id`, `plan_id`, `manifest_sha256`,
  `status`, `differences`, `historical_acknowledgment`.
- Refresh inspection: `attempt_path`, `destination`, `status`, `refresh_id`,
  `verified_package_path`, `successor_path`, `preservation_path`, `readiness_observation`,
  `publication_observation`, `historical_acknowledgment`, `differences`.

Generation reports `verification: "verified_at_materialization"`; refresh reports
`verification: "verified_at_refresh"`. Result `selection` has the domain `project`
and `roots` fields, and `resolutions` preserves domain order with exact revisions.
Differences are ordered objects with exactly `relative_path`, `code`, `detail`.
View status is `verified` or `diverged`. Refresh states are `incomplete_preparation`,
`complete_unpublished`, `published`, `competing_destination`, `inconsistent`.
Null paths remain null. Historical acknowledgment is always `not_established`.
No full manifests, artifact payloads or invented acknowledgment timestamps appear.
Writers reserve the complete predictable output size before reservations, including
escaped repeated paths, derived paths and the LF. Only unallocated token paths and
unknown hashes use fixed-length conservative placeholders during size admission.
Success output uses established values after all inputs and the store have closed.

Exit/code mapping uses the existing diagnostic envelope:

| Exit | Meaning |
| --- | --- |
| 2 | bounded argparse usage error |
| 3 / `missing` | explicit selection/limits/baseline/view or selected root absent; writer runtime absent |
| 4 / `conflict` | occupied destination or definite kernel no-replace collision |
| 5 / `invalid_input` | malformed arguments/authored controls or noncanonical historical manifest; missing config retains this existing classification |
| 5 / `unsafe_layout` | exclusions, ownership/mode/link/type/ancestor or portable-name ambiguity; missing internal required control |
| 5 / `limit_exceeded` | explicit count, byte, depth, descriptor or output allowance exceeded |
| 6 / `integrity_error` | independent pins/expected identities disagree, mutation, corrupt metadata/artifacts or missing committed edge/artifact before publication |
| 6 / `operational_error` | actual I/O/resource/open/close failure before publication |
| 6 / `output_failed` | read-only output failure; repeat the same inspection and discard partial output |
| 7 / `effects_uncertain` | rename may have executed, or writer returned and subsequent verification/sync/close/output failed; interruption without evidence excluding publication |

Definite no-replace collision remains 4. A returned `competing_destination` is an
observation, not an exception. Diagnostics contain exactly `destination`, `attempt_path`,
`snapshot_id`, `plan_id`, `manifest_sha256`, `prior_snapshot_id`, `prior_plan_id`,
`capture_id`, `preservation_plan_id`, `successor_snapshot_id`, `successor_plan_id`,
`refresh_id`, `next_action`; unavailable fields are null. For view inspection,
`destination` means the explicit view. Diagnostic prose is bounded by escaped ASCII
bytes; exact recovery paths and identities are never truncated. Lines fit 65536 bytes.

An initial destination contains `manifest.json`. Its retained sibling
`.readable-view-TOKEN` contains available `intent.json`, `ready.json`, `published.json`;
the paired preparation is `.readable-generation-TOKEN`. Use `inspect-readable-view`
on the explicit destination or paired preparation, retaining the attempt for manual
association. Incomplete initial payloads may not be inspectable. Contents cannot
establish historical publication acknowledgment.

A refresh destination contains `refresh.json`, `capture.json`, `preservation-plan.json`,
`generation/manifest.json` and `preservation/controls/expected-manifest.json`, plus
preserved content. The attempt `.readable-refresh-attempt-TOKEN` holds available
`intent.json`, `ready.json`, `published.json`; its preparation sibling is
`.readable-refresh-package-TOKEN`. Use `inspect-readable-refresh` with the exact
reported attempt/destination and `--expected-refresh-id` when known. Never scan for
a newest attempt or infer association from destination presence. Keep all evidence.
A new absent destination is a separate operation and does not reconcile uncertainty.

## Runnable synthetic CLI continuation

Run this exact block in fresh candidate Python. All API calls are confined to initial
seeding; later operations use the actual CLI. The baseline is explicitly retained and
verified before editing. Native/config bytes remain inert; ambiguous renames and
generated-status edits remain unsubmitted. Cleanup is solely for this disposable example.

```python
from dataclasses import replace
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from tempfile import TemporaryDirectory
from urllib.parse import unquote

import research_pipeline
from research_pipeline.domain import CreationProvenance, RecordEnvelope, RecordReference, Submission
from research_pipeline.store import RecordStore
from research_pipeline.source import (
    DeclaredText, Source, SourceDeclaration, SourceRestrictions, SourceProvenance,
    SourceReading, SourceArtifact, encode_envelope as encode_source,
)
from research_pipeline.work_product import WorkProductManifest, WorkProductFile, encode_envelope


def known(text):
    """Construct literal supplied seed attribution, without authenticating authorship."""
    return DeclaredText(text, None)


def control(path, value):
    """Exclusively write a complete private authored JSON control; fail on collision or close error."""
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as stream:
        json.dump(value, stream)
        stream.flush()
        os.fsync(stream.fileno())
    return path


def command(name, *, expected=0, **options):
    """Execute the candidate module with explicit options and return its observed result or diagnostic."""
    argv = [sys.executable, "-B", "-m", "research_pipeline", name]
    for key, value in options.items():
        argv.extend(("--" + key.replace("_", "-"), str(value)))
    process = subprocess.run(argv, cwd=parent, env=environment, capture_output=True, timeout=90)
    assert process.returncode == expected, (process.returncode, process.stderr)
    if expected:
        assert not process.stdout
        return json.loads(process.stderr)
    assert not process.stderr
    envelope = json.loads(process.stdout)
    assert envelope["status"] == "ok"
    return envelope["result"]


def tree(path):
    """Observe exact disposable-tree bytes, modes and inode identities without changing them."""
    state = {}
    for current, directories, files in os.walk(path):
        for item in [Path(current), *(Path(current) / name for name in files)]:
            info = item.stat()
            state[str(item.relative_to(path))] = (info.st_ino, info.st_mode,
                                                 item.read_bytes() if item.is_file() else None)
    return state


source_root = Path(research_pipeline.__file__).resolve().parents[3]
environment = {**os.environ, "PYTHONPATH": str(source_root / "implementation/src"), "PYTHONDONTWRITEBYTECODE": "1"}
author = CreationProvenance("synthetic-author", "2026-10-31T12:00:00Z", {"qualification": "none"})
editor = CreationProvenance("declared-editor", "2026-10-31T13:00:00Z", {"reason": "explicit chosen edit"})
unknown = DeclaredText(None, "Not supplied")
# Complete independent choices, not implicit defaults or retained-document authority.
snapshot = dict(max_roots=16, max_records=128, max_references=1024, max_record_bytes=1000000,
                max_metadata_bytes=20000000, max_artifacts=64, max_files=2048,
                max_file_bytes=10000000, max_total_bytes=50000000)
view = dict(plan_limits=dict(snapshot), max_entries=4096, max_depth=40, max_open_descriptors=4096)
capture = dict(plan_limits=dict(snapshot), max_entries=4096, max_files=2048, max_directories=2048,
               max_depth=32, max_file_bytes=10000000, max_total_bytes=50000000,
               max_metadata_bytes=50000000, max_diagnostics=10000, max_open_descriptors=4096)
refresh = dict(capture_limits=capture, successor_limits=dict(snapshot), max_entries=10000, max_files=5000,
               max_directories=5000, max_depth=40, max_file_bytes=50000000, max_total_bytes=200000000,
               max_metadata_bytes=200000000, max_diagnostics=20000, max_open_descriptors=4096)
with TemporaryDirectory(prefix="readable-view-cli-example-", dir="/tmp") as temporary:
    parent = Path(temporary)
    try:
        inputs = parent / "inputs"
        inputs.mkdir(mode=0o700)
        supplied = inputs / "note.md"
        supplied.write_bytes(b"# Synthetic authored note\n[original link](missing.md)\n")
        supplied.chmod(0o600)
        runtime = parent / "runtime"
        with RecordStore.create(runtime) as store:
            provenance = SourceProvenance("supplied_local", known("Synthetic supplier"), unknown,
                known(str(supplied)), unknown, unknown, "available", [])
            declaration = SourceDeclaration("unknown", "No permission or endorsement inferred")
            source = Source("synthetic-note", unknown, unknown, known("Supplied note"), [unknown], provenance,
                SourceRestrictions(declaration, declaration, declaration, declaration), [], [], [],
                SourceReading("uninspected", [], None, "unreported", [], unknown, []), [], [], None,
                ["Engineering example only"])
            original = store.put_artifact(supplied.read_bytes())
            source = replace(source, originals=[SourceArtifact("note", "note.md", original, unknown, 0o600, provenance)])
            store.submit_typed(Submission("seed-source", author, [encode_source("source", 1, source, author)], {"source": 0}))
            unique = store.put_artifact(b"Unique rename payload\n")
            product = WorkProductManifest("note", "Synthetic bundle", "Exercise explicit continuation", ["Declared author"],
                None, None, None, None, [], [RecordReference("source", 1, "linked_source", "source")], None, [],
                [WorkProductFile("note.md", original), WorkProductFile("move.txt", unique),
                 WorkProductFile("dup-a.txt", original), WorkProductFile("dup-b.txt", original)], "note.md", ["No scientific evaluation"])
            bundle = encode_envelope("bundle", 1, product, author)
            project = RecordEnvelope("project", 1, "project", {"purpose": "Synthetic engineering"}, author,
                record_references=[RecordReference("bundle", 1, "work_product", "work_product_manifest")])
            store.submit_typed(Submission("initial-bundle", author, [bundle], {"bundle": 0}))
            store.submit(Submission("initial-project", author, [project], {"project": 0}))
            project2 = RecordEnvelope("project", 2, "project", {"purpose": "Later committed description"}, author,
                                      record_references=project.record_references)
            store.submit(Submission("advance-project", author, [project2], {"project": 1}))
            metadata = product.to_dict()
            for key in ("format", "version", "kind", "supersedes", "files"):
                del metadata[key]
            author_value, editor_value = author.to_dict(), editor.to_dict()
        # Seeding ends here. No later operation calls a product API.
        controls = parent / "controls"
        controls.mkdir(mode=0o700)
        config = control(controls / "config.json", dict(format="research_pipeline.cli_config", version=1,
                         store=str(runtime), protected_roots=[str(inputs)]))
        choices = {}
        for label, revision in (("exact", 1), ("current", None)):
            choices[label] = control(controls / (label + ".json"),
                dict(format="research_pipeline.cli_snapshot_selection", version=1,
                     project=dict(record_id="project", revision=revision), roots=[]))
        budgets = {}
        for name, groups in (
            ("generate-readable-view", dict(snapshot_limits=dict(snapshot), view_limits=view)),
            ("refresh-readable-view", dict(snapshot_limits=dict(snapshot), refresh_limits=refresh)),
            ("inspect-readable-view", dict(view_limits=view)),
            ("inspect-readable-refresh", dict(refresh_limits=refresh)),
        ):
            budgets[name] = control(controls / (name + ".json"),
                dict(format="research_pipeline.cli_readable_limits", version=1, command=name, **groups))
        canonical_before = tree(runtime / "objects")
        originals_before = tree(inputs)
        history_before = command("inspect-record", config=config, record_id="bundle", revision=1)
        prior = parent / "prior"
        generated = command("generate-readable-view", config=config, limits=budgets["generate-readable-view"],
                            selection=choices["exact"], destination=prior)
        assert generated["resolutions"][0]["revision"] == 1
        assert generated["selection"]["project"]["revision"] == 1

        # Retain the exact original manifest BEFORE any human edit, using a new
        # single-link inode in a separate private controls directory, never a hardlink.
        original_bytes = (prior / "manifest.json").read_bytes()
        baseline = controls / "original-manifest.json"
        fd = os.open(baseline, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, "wb") as stream:
            assert stream.write(original_bytes) == len(original_bytes)
            stream.flush()
            os.fsync(stream.fileno())
        parent_fd = os.open(controls, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            os.fsync(parent_fd)
        finally:
            os.close(parent_fd)
        retained = baseline.read_bytes()
        assert retained == original_bytes and baseline.stat().st_nlink == 1
        baseline_hash = hashlib.sha256(retained).hexdigest()
        baseline_plan_id = json.loads(retained)["plan_id"]
        assert baseline_hash == generated["manifest_sha256"]
        assert baseline_plan_id == generated["plan_id"]
        manifest = json.loads(retained)
        mappings = {row["logical_key"]["original_path"]: row["relative_path"]
                    for row in manifest["mappings"] if row["logical_key"]["record_id"] == "bundle"}
        draft = parent / "independent-draft"
        command("checkout-work-product", config=config, record_id="bundle", revision=1, destination=draft)
        draft_before = tree(draft)
        chosen_edit = b"# Explicit preserved correction\nNo scientific endorsement.\n"
        authored = prior / mappings["note.md"]
        authored.chmod(0o600)
        authored.write_bytes(chosen_edit)
        # An unchanged unique payload can be associated with its unique new name.
        moving = prior / mappings["move.txt"]
        moving.parent.chmod(0o700)
        moving.rename(moving.with_name("human-renamed.txt"))
        # Equal-content candidates provide no unique association. Leave them unsubmitted.
        for logical, renamed in (("dup-a.txt", "ambiguous-a.txt"), ("dup-b.txt", "ambiguous-b.txt")):
            old = prior / mappings[logical]
            old.rename(old.with_name(renamed))
        page = prior / next(row["page_path"] for row in manifest["records"] if row["record_id"] == "bundle")
        page.chmod(0o600)
        page.write_bytes(b"---\nstatus: displayed-only\n---\n[changed target](missing.md)\n")
        prior.chmod(0o700)
        (prior / ".obsidian").mkdir(mode=0o700)
        (prior / ".obsidian/app.json").write_bytes(b'{"inert":true}\n')
        (prior / ".obsidian/app.json").chmod(0o600)
        (prior / "native.bin").write_bytes(b"\x00\xffinert native data")
        (prior / "native.bin").chmod(0o600)
        prior_before = tree(prior)
        refreshed = command("refresh-readable-view", config=config, limits=budgets["refresh-readable-view"],
            selection=choices["current"], prior_view=prior, baseline_manifest=baseline,
            expected_base_plan_id=baseline_plan_id, expected_base_manifest_sha256=baseline_hash,
            destination=parent / "refreshed")
        assert not refreshed["same_plan"] and refreshed["resolutions"][0]["revision"] == 2
        assert tree(prior) == prior_before and tree(draft) == draft_before
        assert tree(runtime / "objects") == canonical_before and tree(inputs) == originals_before
        assert command("inspect-record", config=config, record_id="bundle", revision=1) == history_before
        generation = Path(refreshed["successor_path"])
        preserved = Path(refreshed["preservation_path"]) / "tree" / mappings["note.md"]
        assert preserved.read_bytes() == chosen_edit
        assert preserved.stat().st_ino != authored.stat().st_ino
        assert (generation / mappings["note.md"]).read_bytes() == supplied.read_bytes()
        preservation = json.loads((Path(refreshed["destination"]) / "preservation-plan.json").read_bytes())
        assert any(group["ambiguous"] for group in preservation["rename_groups"])
        assert any(not group["ambiguous"] and any(path.endswith("/human-renamed.txt") for path in group["observed_paths"])
                   for group in preservation["rename_groups"])
        assert any(row["expected_path"] == mappings["move.txt"] and "renamed" in row["codes"]
                   for row in preservation["target_diagnostics"])
        assert (Path(refreshed["preservation_path"]) / "tree/native.bin").read_bytes() == b"\x00\xffinert native data"
        for generated_file in json.loads((generation / "manifest.json").read_bytes())["files"]:
            if generated_file["hash_kind"] == "generated" and generated_file["path"].endswith(".md"):
                path = generation / generated_file["path"]
                for target in re.findall(r"\]\(([^)]+)\)", path.read_text()):
                    relative = unquote(target.split("#", 1)[0])
                    assert path.parent.joinpath(relative).is_file()
        # Offline inspection needs only exclusions, independent limits and exact evidence.
        unavailable = parent / "runtime-unavailable"
        runtime.rename(unavailable)
        offline_before = tree(parent / "refreshed")
        observed = command("inspect-readable-refresh", config=config, limits=budgets["inspect-readable-refresh"],
            attempt=refreshed["attempt_path"], destination=refreshed["destination"], expected_refresh_id=refreshed["refresh_id"])
        assert observed["status"] == "published" and observed["historical_acknowledgment"] == "not_established"
        observed = command("inspect-readable-view", config=config, limits=budgets["inspect-readable-view"],
                           view=generation, expected_plan_id=refreshed["successor_plan_id"])
        assert observed["status"] == "verified" and not runtime.exists()
        assert tree(parent / "refreshed") == offline_before
        unavailable.rename(runtime)  # Explicitly restore availability for the separate accepted import route.
        (draft / "note.md").write_bytes(preserved.read_bytes())
        base = dict(record_id="bundle", revision=1, relationship="checkout_base", target_kind="work_product_manifest")
        saved = []
        for identity in ("chosen-preserved-edit", "stale-after-preview"):
            preparation = control(controls / (identity + ".json"),
                dict(format="research_pipeline.cli_work_product_preparation", version=1, base=base,
                     expected_head=1, metadata=metadata, selected_paths=["note.md"], submission_id=identity,
                     record_provenance=editor_value, submission_provenance=author_value))
            package = parent / identity
            command("prepare-work-product", config=config, checkout=draft, request=preparation, destination=package)
            reviewed = command("inspect-proposal", proposal=package)
            assert reviewed["submission_id"] == identity
            saved.append(package)
        draft_selected = tree(draft)
        command("submit-work-product", config=config, proposal=saved[0])
        stale = command("submit-work-product", config=config, proposal=saved[1], expected=4)
        assert stale["code"] == "conflict"  # No rebase or regeneration.
        assert command("inspect-record", config=config, record_id="bundle", revision=1) == history_before
        submitted = command("inspect-record", config=config, record_id="bundle", revision=2)
        assert submitted["envelope"]["revision"] == 2
        submitted_files = submitted["envelope"]["content"]["files"]
        assert len(submitted_files) == 1 and submitted_files[0]["path"] == "note.md"
        chosen_digest = submitted_files[0]["artifact"]["digest"]
        assert chosen_digest == hashlib.sha256(chosen_edit).hexdigest()
        assert (runtime / "objects" / chosen_digest).read_bytes() == chosen_edit
        assert tree(prior) == prior_before and tree(draft) == draft_selected
        assert preserved.read_bytes() == chosen_edit and tree(inputs) == originals_before
        for digest, (_, mode, data) in canonical_before.items():
            if data is not None:
                assert (runtime / "objects" / digest).read_bytes() == data
    finally:
        for current, directories, files in os.walk(parent):
            os.chmod(current, 0o700)  # Disposable example cleanup, never a CLI recovery action.
```
