# Safe durable work-product checkout

Import directly from `research_pipeline.checkout`; there are no package re-exports.
The [local CLI](local-cli.md) also exposes exact historical checkout and offline
original-descriptor inspection with explicit trusted configuration and limits. Checkout materializes an **exact committed revision**, never an
implicit current head or caller-supplied manifest. It checks the selected envelope's
typed structural coherence and directly referenced artifact bytes. It does not
traverse semantic targets, establish past typed admission, or read/execute build
inputs. Every file, including scripts, Python/configuration files and notebook
cells, is inert bytes.

```text
checkout_work_product(
    source: RecordStore, base: RecordReference, destination, *,
    source_root, protected_roots,
    max_file_bytes: int, max_total_bytes: int,
    max_files: int, max_descriptor_bytes: int,
) -> CheckoutInfo
inspect_checkout(root, *, max_descriptor_bytes: int) -> CheckoutInfo
```

`source` is an open thread-confined store. `base` must explicitly identify a valid
record/revision with relationship `checkout_base` and target kind
`work_product_manifest`. `CheckoutInfo` is frozen and defensively detached, with
only `base: RecordReference` and `envelope: RecordEnvelope`. Its original envelope
preserves manifest ordering, entry file, provenance, declared attribution and all
original digest/size pairs. There is no second mutable file inventory.

All four limits are required ordinary integers, excluding booleans, floats, null
and infinity. File/total byte limits may be zero; file count and descriptor bytes
must be positive. Repeated objects count separately toward both total bytes and
file count. Inventory and descriptor-size budget violations fail before reserving
the destination. Capture uses bounded chunks and at most a one-byte EOF probe
beyond a declared object size; it rejects truncation, growth, hash mismatch and
observed changes/replacement. It never buffers the complete bundle.

## Destination and caller responsibilities

`destination` must be absent, with an existing parent. Existing files, directories
and dangling symlinks are refused unchanged. Ancestors are never created. Relative
paths are anchored to caller cwd without resolving symlinks; parent traversal is
forbidden and POSIX `//` is normalized to `/`. Containment checks use components,
not textual prefixes, and reject overlap in **either direction** with:

- The explicitly supplied `source_root`, identifying the software source tree.
- The selected store runtime (automatically added), including objects and staging.
- Every explicitly supplied `protected_roots` entry, including backups, controller
  internals and external Git administration where applicable.

`protected_roots` must be an explicit list/tuple. An empty collection declares no
additional exclusions. These paths are trusted caller inputs, never descriptor
fields or environment-derived defaults. The library cannot discover every arbitrary
external backup/control directory; callers must supply them. Ancestor traversal
also refuses recognizable runtime/backup/checkout layouts and incomplete markers,
without opening databases or importing content. Tests use disposable software and
control trees, never the actual repository as a write target.

Held directory descriptors, no-follow relative opens, lstat/fstat identity checks,
nonblocking leaf opens and prepublication binding checks detect observed rename,
symlink, type and file substitutions. Canonical objects must satisfy the existing
owned read-only regular-file contract. Directories are created private `0700`,
product files owned `0600`, controls owned `0400`. Product copies have independent
inodes, never hard links to canonical objects or each other. They are writable and
non-executable. These checks constrain ordinary access and detect observed changes;
they do **not** authenticate or sandbox a hostile same-owner or privileged process.

## Descriptor and local controls

The top-level component `.work-product` is reserved, including every alias under
the manifest's `NFKC(NFKC(component).casefold())` rule. A file or directory under
`.WORK-PRODUCT` or `.ｗork-product`, for example, cannot be checked out. This is a
checkout restriction, not a change to accepted manifest wire/path rules. Previously
valid reserved-name manifests remain readable. `.work-product-other` is distinct.

The local descriptor `.work-product/checkout.json` is compact sorted-key
ASCII-escaped JSON with exactly:

| Field | Meaning |
| --- | --- |
| `format` | `research_pipeline.work_product_checkout` |
| `version` | Ordinary integer `1` |
| `base` | Complete exact serialized `RecordReference` |
| `envelope` | Complete exact serialized original `RecordEnvelope` |

Original hashes/sizes are the artifact references in `envelope.content.files`.
All nested serialized fields are required, including explicit defaults/nulls.
Inspection rejects duplicates at any depth, missing/extra fields, invalid UTF-8
or scalar Unicode, nonfinite numbers, coercion, unsupported versions and incoherent
base/envelope values. Boolean and integer values remain distinct. Whitespace and
JSON key order need not match the writer's canonical encoding. There is no runtime
locator, authority flag, inferred date or invented attribution. Read-only controls
are an accidental-change precaution, not authentication.

`inspect_checkout` is read-only local publication/descriptor inspection. It rejects
any `.work-product/incomplete` entry, including dangling symlinks and unexpected
types, missing/unsafe controls, extra entries within the control directory, oversized
or growing descriptors and detected substitutions. It does not consult canonical
storage, authenticate the descriptor, certify current product hashes or require
files outside controls to retain their original bytes. Edits, additions and removals
remain available for later preparation. A coherent same-owner rewrite can alter
local base/attribution claims and still pass inspection; comparison with a trusted
caller-pinned canonical base belongs to preparation.

## Durability, errors and retained output

The exclusively created destination is the private construction area. There is no
rename-overwrite staging or abandoned-directory reuse. Before descriptor/product
creation, checkout creates and fsyncs the empty incomplete marker, control directory,
checkout root and destination parent. An earlier crash still lacks the required
controls/descriptor and is unusable. Files are streamed independently, checked and
fsynced. Checkout verifies exact constructed inventory, entry-file presence, sizes,
hashes, private writable modes, single links and distinct copy identities. It writes
and fsyncs the descriptor while the marker remains, then syncs product directories
bottom-up, controls, root and parent. Held bindings and the original marker identity
are rechecked before removal.

**Marker unlink is logical publication.** Successful return additionally requires
final control/root/parent synchronization. Prepublication failures (including failed
unlink) retain incomplete material. There is no automatic cleanup, repair, finishing
or retry in place. Use a new absent destination for another checkout attempt.

Failures after removal preserve the directory and explicitly report:
`marker removed; final synchronization/acknowledgment uncertain; inspect retained checkout`.
The marker is never recreated to imply rollback. Fresh inspection can observe a
structurally published checkout but cannot prove a prior acknowledgment or
authenticate subsequent owner mutations.

`CheckoutError` has `CheckoutLayoutError`, `CheckoutIntegrityError` and
`CheckoutOperationalError` subclasses with operation/path diagnostics and chained
causes. Invalid input values can raise `DomainValidationError`; existing missing-record
and closed-store errors retain their meaning. Output is retained on all failures.
Checkout writes no canonical objects, submissions, records, heads, receipts/events
or views. Editing a checkout changes no canonical data.

Kind labels confer no execution authority or scientific certification. Authors and
provenance are declared attribution, not authenticated authorship.
[Preview and explicit import](work-product-import.md) compares the canonical base,
captures explicit edited selections and returns frozen proposals for separate commit.
Full vault/intake, research
execution and scientific sufficiency remain deferred; D02 is partial.

## Runnable checkout-only example

Run with candidate `implementation/src` on `PYTHONPATH`. The test suite executes
this exact block in a fresh interpreter. The temporary parent contains explicitly
separate runtime, destination, disposable software-source and additional exclusion
paths. A real caller must substitute its actual trusted source/exclusion locations.

```python
from pathlib import Path
from tempfile import TemporaryDirectory

from research_pipeline.checkout import checkout_work_product, inspect_checkout
from research_pipeline.domain import CreationProvenance, RecordReference, Submission
from research_pipeline.store import RecordStore
from research_pipeline.work_product import WorkProductFile, WorkProductManifest, encode_envelope

creator = CreationProvenance("author", "2026-10-30T12:00:00Z", {"source": "synthetic"})
controller = CreationProvenance("controller", "2026-10-30T12:01:00Z", {})
with TemporaryDirectory(prefix="checkout-example-") as temporary:
    parent = Path(temporary)
    runtime = parent / "runtime"
    destination = parent / "draft"
    source_root = parent / "software-source"
    backup_root = parent / "backups"
    controller_root = parent / "controller-and-external-git"
    for path in (source_root, backup_root, controller_root):
        path.mkdir(mode=0o700)
    with RecordStore.create(runtime) as store:
        text = store.put_artifact("Synthetic note α\n".encode("utf-8"))
        binary = store.put_artifact(b"\x00\xff\x80")
        product = WorkProductManifest(
            product_kind="note", title="Synthetic bundle", purpose="Demonstrate checkout",
            authors=["Declared author α"], task=None, branch=None, context=None, run=None,
            linked_claims=[], linked_sources=[], supersedes=None, build_dependencies=[],
            files=[WorkProductFile("notes/α.txt", text), WorkProductFile("data/raw.bin", binary),
                   WorkProductFile("copy.txt", text)],
            entry_file="notes/α.txt", limitations=["No scientific validation"],
        )
        envelope = encode_envelope("bundle", 1, product, creator)
        store.submit_typed(Submission("initial", controller, [envelope], {"bundle": 0}))
        base = RecordReference("bundle", 1, "checkout_base", "work_product_manifest")
        info = checkout_work_product(
            store, base, destination, source_root=source_root,
            protected_roots=[backup_root, controller_root],
            max_file_bytes=1024, max_total_bytes=4096, max_files=10,
            max_descriptor_bytes=65536,
        )
        assert info.envelope == envelope
        (destination / "notes/α.txt").write_text("Locally edited note\n", encoding="utf-8")
        assert (destination / "copy.txt").read_bytes() == "Synthetic note α\n".encode("utf-8")
        assert store.read_artifact(text) == "Synthetic note α\n".encode("utf-8")
        assert store.head("bundle") == 1
    observed = inspect_checkout(destination, max_descriptor_bytes=65536)
    assert observed.base == base and observed.envelope == envelope
    # This is original local base information, not certification of edited bytes.
```

Preserved direct view edits can enter this explicit route using the exact historical
record/revision and logical path in the [readable refresh continuation](readable-refresh.md).
Refresh itself never previews or imports; stale expected bases conflict without rebasing.
