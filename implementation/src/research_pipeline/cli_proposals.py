"""Strict saved work-product packages, offline observations and private publication.

The destination is reserved exclusively. Removing its empty incomplete marker is
logical publication, not an atomic directory-visibility or historical-fsync claim.
"""

from contextlib import ExitStack
import hashlib
import json
import os
import re
import stat

from research_pipeline import checkout, work_product_import as importer
from research_pipeline.cli_controls import CliError, causes, complete_codec, read_control, strict_json
from research_pipeline.domain import (
    ArtifactReference, CreationProvenance, DomainValidationError, RecordReference,
    _fields, _integer, _snapshot,
)
from research_pipeline.snapshot import _bounded_json
from research_pipeline.vault import _not_layout
from research_pipeline.work_product import WorkProductManifest, _path, _validate_paths, decode_envelope

_CONTROL = ".work-product-proposal"
_MANIFEST = "manifest.json"
_MARKER = "incomplete"
_PAYLOADS = {"proposal.json", "summary.json"}


def _fault(boundary):
    """Private deterministic fault seam before real checks; never selected by input or environment."""


def not_proposal(fd, path):
    """Reject saved-package ancestors by fixed-name no-follow probe without consuming content."""
    try:
        checkout._stat(fd, _CONTROL)
    except FileNotFoundError:
        return
    raise checkout.CheckoutLayoutError(f"path {path}: saved proposal control ancestor")


def _json(value, maximum):
    """Encode sorted compact ASCII JSON incrementally within the caller's exact byte budget."""
    return _bounded_json(value, maximum, "saved package").encode("ascii")


def _digest(data):
    """Return the content binding for exact saved bytes, without implying authentication."""
    return dict(sha256=hashlib.sha256(data).hexdigest(), bytes=len(data))


def _conflict():
    """Raise a fixed diagnostic for contradictory saved evidence without exposing its contents."""
    raise CliError(4, "conflict", "Saved package evidence conflicts or changed during observation.")


def _unselected(value):
    """Validate the preview's ordered visited-directory report, including opaque and escaped names."""
    if type(value) is not list:
        raise DomainValidationError("unselected report requires an array")
    keys = []
    for entry in value:
        _fields(entry, {"path", "path_escaped", "kind", "opaque"}, set(), "unselected entry")
        path, escaped, kind = entry["path"], entry["path_escaped"], entry["kind"]
        if (type(path) is not str or not path or type(escaped) is not bool
                or type(entry["opaque"]) is not bool or type(kind) is not str
                or kind not in ("file", "directory", "symlink", "other")
                or entry["opaque"] != (kind == "directory")):
            raise DomainValidationError("invalid unselected entry")
        logical = path
        if escaped:
            try:
                logical = json.loads('"' + path + '"')
            except ValueError as error:
                raise DomainValidationError("invalid escaped path") from error
            if (not any(0xD800 <= ord(char) <= 0xDFFF for char in logical)
                    or json.dumps(logical, ensure_ascii=True)[1:-1] != path):
                raise DomainValidationError("noncanonical escaped path")
        if "\0" in logical or any(part in ("", ".", "..") for part in logical.split("/")):
            raise DomainValidationError("invalid unselected relative path")
        keys.append((path, escaped))
    if keys != sorted(set(keys)):
        raise DomainValidationError("unordered or repeated unselected entries")
    return value


def _proposal(data):
    """Apply CLI depth/token/Unicode gates before the existing narrow proposal codec."""
    value = strict_json(data)
    submission = importer.loads_prepared_submission(data)
    if importer.dumps_prepared_submission(submission).encode("ascii") != data:
        raise DomainValidationError("proposal is not its exact canonical encoding")
    return value, submission


def _changes(value, info, submission):
    """Validate complete nested comparison shapes before testing their semantic equality to the baseline."""
    _fields(value, {"base", "proposed_revision", "paths", "old_files", "new_files", "metadata_changes",
                   "provenance_changes", "structural_changes", "unselected_material"}, set(), "changes")
    checkout._base(complete_codec(value["base"], RecordReference))
    _integer(value["proposed_revision"], "proposed revision", 1)
    for name in ("paths", "old_files", "new_files"):
        if type(value[name]) is not list:
            raise DomainValidationError("comparison membership requires arrays")
    for name in ("old_files", "new_files"):
        _validate_paths(value[name])
    for entry in value["paths"]:
        _fields(entry, {"path", "status", "old", "new"}, set(), "path comparison")
        _path(entry["path"], "comparison path")
        if type(entry["status"]) is not str or entry["status"] not in ("added", "removed", "changed", "unchanged"):
            raise DomainValidationError("invalid path comparison status")
        for name in ("old", "new"):
            if entry[name] is not None:
                complete_codec(entry[name], ArtifactReference)
    metadata = _fields(value["metadata_changes"], set(), set(importer._METADATA), "metadata changes")
    provenance = _fields(value["provenance_changes"], set(), {"record", "submission"}, "provenance changes")
    structural = _fields(value["structural_changes"], {"revision", "supersedes"}, set(), "structural changes")
    for category in (metadata, provenance, structural):
        for comparison in category.values():
            _fields(comparison, {"before", "after"}, set(), "comparison")
    for comparison in provenance.values():
        for item in comparison.values():
            complete_codec(item, CreationProvenance)
    for item in structural["revision"].values():
        _integer(item, "compared revision", 1)
    for item in structural["supersedes"].values():
        if item is not None:
            complete_codec(item, RecordReference)
    # Existing manifest codecs validate nested metadata types and explicit fields;
    # the later recomputation decides whether well-formed values tell the truth.
    if submission is not None:
        for side, manifest in (("before", checkout._inventory(info)),
                               ("after", decode_envelope(submission.records[0]))):
            document = manifest.to_dict()
            document.update({name: comparison[side] for name, comparison in metadata.items()})
            complete_codec(document, WorkProductManifest)
    return _unselected(value["unselected_material"])


def _summary(data, proposal_data=None, submission=None):
    """Validate a complete offline baseline and recompute every displayed change when proposal exists."""
    value = strict_json(data)
    _fields(value, {"format", "version", "proposal_sha256", "base_checkout",
                    "base_submission_provenance", "changes"}, set(), "saved summary")
    if (value["format"] != "research_pipeline.cli_work_product_summary"
            or type(value["version"]) is not int or value["version"] != 1
            or type(value["proposal_sha256"]) is not str
            or re.fullmatch(r"[0-9a-f]{64}", value["proposal_sha256"]) is None):
        raise DomainValidationError("invalid summary identity/format")
    if _snapshot(value, "summary").encode("ascii") != data:
        raise DomainValidationError("summary is not its exact canonical encoding")
    try:
        info = checkout._decode(_snapshot(value["base_checkout"], "baseline").encode("ascii"))
    except checkout.CheckoutIntegrityError as error:
        raise DomainValidationError("invalid saved baseline") from error
    provenance = complete_codec(value["base_submission_provenance"], CreationProvenance)
    changes = value["changes"]
    unselected = _changes(changes, info, submission)
    if submission is not None:
        envelope = submission.records[0]
        if (value["proposal_sha256"] != hashlib.sha256(proposal_data).hexdigest()
                or info.base.record_id != envelope.record_id or info.base.revision + 1 != envelope.revision):
            _conflict()
        expected = importer._summary(info, checkout._inventory(info), decode_envelope(envelope),
                                     submission, provenance, unselected)
        if _snapshot(changes, "changes") != _snapshot(expected, "changes"):
            _conflict()
    return value, info


def _manifest(data):
    """Validate canonical manifest fields and exact ordinary scalar types before comparing payloads."""
    value = strict_json(data)
    _fields(value, {"format", "version", "proposal", "summary", "submission_id", "record_id",
                    "base_revision", "proposed_revision"}, set(), "package manifest")
    if (value["format"] != "research_pipeline.cli_saved_work_product"
            or type(value["version"]) is not int or value["version"] != 1):
        raise DomainValidationError("invalid saved package format")
    from research_pipeline.domain import _identifier, _integer
    for name in ("submission_id", "record_id"):
        _identifier(value[name], name)
    for name in ("base_revision", "proposed_revision"):
        _integer(value[name], name, 1)
    for name in ("proposal", "summary"):
        binding = _fields(value[name], {"sha256", "bytes"}, set(), "file binding")
        if (type(binding["bytes"]) is not int or binding["bytes"] <= 0
                or type(binding["sha256"]) is not str
                or re.fullmatch(r"[0-9a-f]{64}", binding["sha256"]) is None):
            raise DomainValidationError("invalid file binding")
    if _snapshot(value, "manifest").encode("ascii") != data:
        raise DomainValidationError("manifest is not its exact canonical encoding")
    return value


def documents(prepared, info, provenance, arguments):
    """Build and validate all exact bounded package documents in memory before destination reservation."""
    submission = prepared.submission
    # Bound escaping before calling the established exact codec as the final authority.
    _json(dict(format=importer._FORMAT, version=1, submission=submission.to_dict()), arguments.max_proposal_bytes)
    proposal = importer.dumps_prepared_submission(submission).encode("ascii")
    summary = _json(dict(format="research_pipeline.cli_work_product_summary", version=1,
                         proposal_sha256=_digest(proposal)["sha256"],
                         base_checkout=strict_json(checkout._encode(info)),
                         base_submission_provenance=provenance.to_dict(), changes=prepared.summary),
                    arguments.max_summary_bytes)
    manifest = _json(dict(format="research_pipeline.cli_saved_work_product", version=1,
                          proposal=_digest(proposal), summary=_digest(summary),
                          submission_id=submission.submission_id, record_id=info.base.record_id,
                          base_revision=info.base.revision, proposed_revision=submission.records[0].revision),
                     min(arguments.max_control_bytes, 16384))
    _proposal(proposal)
    _summary(summary, proposal, submission)
    _manifest(manifest)
    return {"proposal.json": proposal, "summary.json": summary, _MANIFEST: manifest}


def _binding_conflict():
    """Refuse lost or substituted saved bindings with the fixed content-free diagnostic."""
    raise CliError(4, "conflict", "Saved package bindings or contents changed during observation.")


class _InitialAbsence(Exception):
    """Signal a never-observed missing path component beneath rechecked stable ancestors."""


class _PackageDirectories(checkout._Directories):
    """Keep initial absence distinct from races while reusing checkout's descriptor ownership."""

    def open(self, name, parent=None, *, private=False, exact=False, path=None):
        """Retain the first no-follow identity across delegated opening; only its absence is initial."""
        try:
            before = checkout._stat(parent, name)
        except FileNotFoundError as error:
            # A detached held ancestor must not turn a missing child into absence.
            self.check()
            raise _InitialAbsence() from error
        if not stat.S_ISDIR(before.st_mode):
            raise checkout.CheckoutLayoutError(f"open directory {path or name}: symlink or non-directory")
        try:
            descriptor = super().open(name, parent, private=private, exact=exact, path=path)
        except (checkout.CheckoutError, OSError) as error:
            if (isinstance(error, checkout.CheckoutIntegrityError)
                    or any(isinstance(cause, FileNotFoundError) for cause in causes(error))):
                _binding_conflict()
            # A no-follow refusal can mean a directory was replaced by an
            # unsafe entry. Compare identity before treating it as initial layout.
            try:
                current = checkout._stat(parent, name)
            except FileNotFoundError:
                _binding_conflict()
            if (not stat.S_ISDIR(current.st_mode)
                    or checkout._identity(current) != checkout._identity(before)):
                _binding_conflict()
            self.check()
            raise
        # The delegate stats again; it must not silently adopt a replacement
        # between our initial observation and its own opening checks.
        opened = os.fstat(descriptor)
        if not stat.S_ISDIR(opened.st_mode) or checkout._identity(opened) != checkout._identity(before):
            _binding_conflict()
        return descriptor

    def check(self):
        """Recheck all held bindings, translating their loss or substitution into saved-package conflict."""
        try:
            super().check()
        except checkout.CheckoutIntegrityError:
            _binding_conflict()
        except checkout.CheckoutOperationalError as error:
            if any(isinstance(cause, FileNotFoundError) for cause in causes(error)):
                _binding_conflict()
            raise


class _Package:
    """Hold directory bindings and leaf signatures across a complete multi-file observation."""

    def __init__(self, path, arguments, stack):
        """Hold the private package and ancestors, distinguishing initial absence from binding races."""
        self.path, self.arguments = path, arguments
        self.directories = _PackageDirectories(stack)
        self.parent = self.directories.traverse(path.parent, private=True, exact=True)
        self.area = self.directories.open(path.name, self.parent, private=True, exact=True, path=path)
        self.control = None
        self.bindings = []
        self.inventories = []

    def inventory(self, fd, allowed):
        """Bound enumeration by the fixed inventory and remember directory signatures for later gates."""
        before = os.fstat(fd)
        names = checkout._bounded_entries(fd, len(allowed))
        if not names <= allowed:
            _conflict()
        if checkout._signature(before) != checkout._signature(os.fstat(fd)):
            _conflict()
        self.inventories.append((fd, before, names, allowed))
        return names

    def read(self, parent, name, path, maximum):
        """Read a safe bounded leaf and retain its signature after close to detect cross-file mutation."""
        before = checkout._stat(parent, name)
        data = read_control(parent, name, path, maximum, modes=(0o400,))
        self.bindings.append((parent, name, path, before))
        _fault("after_" + name)
        return data

    def check(self):
        """Recheck every earlier leaf and inventory after later reads and synchronization barriers."""
        self.directories.check()
        for parent, name, _, original in self.bindings:
            if checkout._signature(checkout._stat(parent, name)) != checkout._signature(original):
                _conflict()
        for fd, original, names, allowed in self.inventories:
            if (checkout._signature(os.fstat(fd)) != checkout._signature(original)
                    or checkout._bounded_entries(fd, len(allowed)) != names):
                _conflict()

    def load(self):
        """Validate all available evidence; expose verified identities only for a complete coherent package."""
        root_names = self.inventory(self.area, _PAYLOADS | {_CONTROL})
        control_names = set()
        if _CONTROL in root_names:
            self.control = self.directories.open(_CONTROL, self.area, private=True, exact=True,
                                                 path=self.path / _CONTROL)
            control_names = self.inventory(self.control, {_MANIFEST, _MARKER})
        if _MARKER in control_names:
            marker = self.read(self.control, _MARKER, self.path / _CONTROL / _MARKER, 0)
            if marker:
                raise DomainValidationError("nonempty incomplete marker")
        raw, proposal, submission, summary, info, manifest = {}, None, None, None, None, None
        for name, maximum in (("proposal.json", self.arguments.max_proposal_bytes),
                               ("summary.json", self.arguments.max_summary_bytes)):
            if name in root_names:
                raw[name] = self.read(self.area, name, self.path / name, maximum)
        if "proposal.json" in raw:
            proposal, submission = _proposal(raw["proposal.json"])
        if "summary.json" in raw:
            summary, info = _summary(raw["summary.json"], raw.get("proposal.json"), submission)
            if submission is None:
                _conflict()
        if _MANIFEST in control_names:
            manifest = _manifest(self.read(self.control, _MANIFEST, self.path / _CONTROL / _MANIFEST,
                                           min(self.arguments.max_control_bytes, 16384)))
            for name in ("proposal", "summary"):
                if name + ".json" not in raw or manifest[name] != _digest(raw[name + ".json"]):
                    _conflict()
        if raw and (self.control is None or (_MARKER not in control_names and manifest is None)):
            _conflict()
        result = dict(destination=str(self.path), state="incomplete", proposal_sha256=None,
                      submission_id=None, base=None, proposed_revision=None, proposal=None, summary=None,
                      historical_durability="unknown")
        if manifest is not None:
            envelope = submission.records[0]
            if (manifest["submission_id"] != submission.submission_id
                    or manifest["record_id"] != envelope.record_id
                    or manifest["base_revision"] != info.base.revision
                    or manifest["proposed_revision"] != envelope.revision):
                _conflict()
            result.update(state="complete_unpublished" if _MARKER in control_names else "published",
                          proposal_sha256=manifest["proposal"]["sha256"], submission_id=submission.submission_id,
                          base=info.base.to_dict(), proposed_revision=envelope.revision,
                          proposal=proposal, summary=summary)
        self.check()
        return result, submission

    def sync(self):
        """Durably save this invocation's verified input, requiring unchanged leaves and checked closes."""
        self.check()
        for parent, name, path, original in self.bindings:
            with checkout._leaf(parent, name, path, mode=0o400, expected=original) as (fd, _):
                checkout._sync(fd, path)
        for fd, path in ((self.control, self.path / _CONTROL), (self.area, self.path),
                          (self.parent, self.path.parent)):
            checkout._sync(fd, path)
        _fault("after_input_sync")
        self.check()


def observe(path, arguments, *, durable=False, recovery=None):
    """Inspect without store/artifact access, or close a reverified durable published request before submit.

    No inspection writes, repairs, chmods or synchronizes. Durable mode requires a
    complete published package and establishes only current invocation durability.
    Optional recovery receives verified identities before synchronization or closes
    can fail, so diagnostics retain the original ID even when submission is denied.
    Only initial path absence beneath stable ancestors yields an absent result.
    Disappearance during checked saved-input observation is a conflict, whether
    the underlying ENOENT is bare or wrapped in an operational exception.
    """
    with ExitStack() as stack:
        try:
            try:
                package = _Package(path, arguments, stack)
            except _InitialAbsence as error:
                if durable:
                    raise CliError(3, "missing", "Saved package is absent.") from error
                return dict(destination=str(path), state="absent", proposal_sha256=None, submission_id=None,
                            base=None, proposed_revision=None, proposal=None, summary=None,
                            historical_durability="unknown"), None
            result, submission = package.load()
            if recovery is not None and result["base"] is not None:
                recovery["verified"] = result
            if durable:
                if result["state"] != "published":
                    raise CliError(5, "invalid_input", "Only a complete published package can be submitted.")
                package.sync()
                repeated, _ = package.load()
                if repeated != result:
                    _conflict()
                package.check()
        except (_InitialAbsence, checkout.CheckoutIntegrityError, FileNotFoundError):
            _binding_conflict()
        except checkout.CheckoutOperationalError as error:
            if any(isinstance(cause, FileNotFoundError) for cause in causes(error)):
                _binding_conflict()
            raise

    return result, submission


def publish(path, documents, arguments, effects):
    """Exclusively reserve, save, verify and publish a private package, retaining all failures.

    The marker is never recreated after removal. All postpublication failures are
    acknowledgment uncertainty, including directory synchronization and close.
    Initial absence during verification is also conflict: reservation already occurred.
    """
    try:
        with ExitStack() as stack:
            directories = checkout._Directories(stack)
            parent = directories.traverse(path.parent, private=True, exact=True)
            for _, _, fd, _, _, _, location in directories.bindings:
                _not_layout(fd, checkout._path(location))
                not_proposal(fd, location)
            area = directories.create(path.name, parent, path)
            effects["reserved"] = True
            _fault("reserved")
            control = directories.create(_CONTROL, area, path / _CONTROL)
            created = []
            with checkout._new_leaf(control, _MARKER, path / _CONTROL / _MARKER, 0o400) as fd:
                checkout._sync(fd, path / _CONTROL / _MARKER)
                created.append((control, _MARKER, checkout._signature(os.fstat(fd))))
            for fd, location in ((control, path / _CONTROL), (area, path), (parent, path.parent)):
                checkout._sync(fd, location)
            _fault("marked")
            for name in ("proposal.json", "summary.json", _MANIFEST):
                target, location = (control, path / _CONTROL / name) if name == _MANIFEST else (area, path / name)
                with checkout._new_leaf(target, name, location, 0o400) as fd:
                    checkout._write_all(fd, documents[name])
                    checkout._sync(fd, location)
                    created.append((target, name, checkout._signature(os.fstat(fd))))
                _fault("wrote_" + name)
            package = _Package(path, arguments, stack)
            observed, _ = package.load()
            if observed["state"] != "complete_unpublished":
                _conflict()
            for target, name, signature in created:
                if checkout._signature(checkout._stat(target, name)) != signature:
                    _conflict()
            package.sync()
            _fault("before_publish")
            # The final full content/binding gate follows the barriers and any fault seam.
            package.check()
            repeated, _ = package.load()
            if repeated != observed:
                _conflict()
            directories.check()
            os.unlink(_MARKER, dir_fd=control)
            effects["published"] = True
            _fault("published")
            for fd, location in ((control, path / _CONTROL), (area, path), (parent, path.parent)):
                checkout._sync(fd, location)
            final = _Package(path, arguments, stack)
            result, _ = final.load()
            if result != {**observed, "state": "published"}:
                _conflict()
            for target, name, signature in created:
                if name != _MARKER and checkout._signature(checkout._stat(target, name)) != signature:
                    _conflict()
            directories.check()
            _fault("before_close")
            final.check()
        return result
    except _InitialAbsence:
        _binding_conflict()
