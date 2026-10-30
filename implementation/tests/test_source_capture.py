"""Real explicit Source capture, bounded filesystem checks and strict detached proposals."""

from copy import deepcopy
from dataclasses import replace
import hashlib
import json
import os
from pathlib import Path
import stat
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from research_pipeline import checkout, source_capture as capturing, work_product_import
from research_pipeline.artifacts import ArtifactError
from research_pipeline.checkout import CheckoutError, CheckoutIntegrityError, CheckoutLayoutError
from research_pipeline.domain import CreationProvenance, DomainValidationError, RecordReference
from research_pipeline.source import decode_envelope, encode_envelope
from research_pipeline.source_capture import (
    PreparedSourceCapture, dumps_prepared_submission, loads_prepared_submission,
    prepare_source_capture,
)
from research_pipeline.store import (
    RecordStore, ReferenceResolutionError, RevisionConflictError, SubmissionConflictError,
)
from tests.test_assessment_store import metadata
from tests import test_checkout as checkout_tests
from tests.test_source import at_path, dictionaries, known, source, uninspected
from tests.test_store import CREATOR, CONTROLLER, record, request
from tests.test_work_product import manifest
from research_pipeline.work_product import encode_envelope as product_envelope


class CaptureTests(unittest.TestCase):
    """Use disposable synthetic files and real stores, preserving every application table on previews."""

    child = checkout_tests.CheckoutTests.child

    def setUp(self):
        """Build explicit original/derived inventories with mapped names and inert representative bytes."""
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.parent = Path(temporary.name)
        self.root = self.parent / "runtime"
        self.input = self.parent / "inputs"
        self.input.mkdir(mode=0o755)
        self.software = self.parent / "software"
        self.backup = self.parent / "backup"
        self.controls = self.parent / "controls"
        for path in (self.software, self.backup, self.controls):
            path.mkdir(mode=0o700)
            (path / "sentinel").write_bytes(b"Excluded synthetic material")
        self.store = RecordStore.create(self.root)
        self.addCleanup(self.store.close)
        self.marker = self.parent / "EXECUTED"
        code = f"from pathlib import Path\nPath({str(self.marker)!r}).write_text('bad')\n"
        self.payloads = {
            "physical/α.tex": b"Synthetic TeX-like $x^2$\n", "LICENSE": b"Synthetic license\n",
            "copy.tex": b"Synthetic TeX-like $x^2$\n", "raw.bin": b"\x00\xff\x80",
            "empty": b"", "paper.pdf": b"%PDF-synthetic-not-a-parsed-paper\n",
            "run.py": code.encode(), "notebook.ipynb": json.dumps({"cells": [{"cell_type": "code", "source": code}]}).encode(),
            "settings.py": code.encode(), "data.csv": b"x,y\n1,2\n", "output.txt": b"Supplied extraction: x squared\n",
        }
        (self.input / "physical").mkdir(mode=0o755)
        for name, payload in self.payloads.items():
            path = self.input / name
            path.write_bytes(payload)
            path.chmod(0o755 if name == "run.py" else 0o644)
        self.meta = source().to_dict()
        for key in ("format", "version", "kind"):
            del self.meta[key]
        self.meta["reading"] = uninspected().reading.to_dict()
        self.meta["related_sources"] = []
        self.meta["statements"] = self.meta["statements"][:2]
        self.meta["locations"][1]["end"] = len(self.payloads["output.txt"])
        prototype = deepcopy(self.meta["originals"][0])
        for name in list(self.payloads)[3:-1]:
            item = deepcopy(prototype)
            item.update(artifact_id=name.replace(".", "-"), path="materials/" + name)
            self.meta["originals"].append(item)
        entries = self.entries(self.meta)
        self.selection = []
        for entry, name in zip(entries, self.payloads):
            del entry["artifact"]
            del entry["original_mode"]
            entry["provenance"].update(method="supplied_local", outcome="available",
                supplied_locator=known(str(self.input / name)).to_dict())
            self.selection.append(dict(artifact_id=entry["artifact_id"], input_path=name))
        self.options = dict(selected_files=self.selection, metadata=self.meta, record_id="capture",
            revision=1, expected_head=0, submission_id="initial", record_provenance=CREATOR,
            submission_provenance=CONTROLLER, source_root=self.software,
            backup_roots=[self.backup], control_roots=[self.controls],
            max_file_bytes=1_000_000, max_total_bytes=2_000_000, max_files=20)

    @staticmethod
    def entries(meta):
        """Return mutable template entries in originals-then-output order for test mutations."""
        return [*meta["originals"], *(entry for extraction in meta["extractions"] for entry in extraction["outputs"])]

    def prepare(self, **options):
        """Call the public boundary with complete explicit fixture declarations and trusted bounds."""
        return prepare_source_capture(self.store, self.input, **{**self.options, **options})

    def reject(self, operation, error=(DomainValidationError, CheckoutError)):
        """Assert useful rejection and exact equality of every application table before/after."""
        before = metadata(self.root)
        with self.assertRaises(error) as caught:
            operation()
        self.assertTrue(str(caught.exception))
        self.assertEqual(metadata(self.root), before)
        return caught.exception

    def only(self, name="empty"):
        """Select one real original with no lineage/location references for isolated edge cases."""
        index = list(self.payloads).index(name)
        entry = deepcopy(self.entries(self.meta)[index])
        meta = {**deepcopy(self.meta), "originals": [entry], "extractions": [], "locations": [], "statements": []}
        return dict(metadata=meta, selected_files=[deepcopy(self.selection[index])])

    def test_inert_capture_mapping_detachment_and_no_reservation(self):
        """Preserve bytes/modes and explicit declarations; snapshots and detached views grant no commit."""
        before = metadata(self.root)
        signatures = {name: checkout._signature((self.input / name).stat()) for name in self.payloads}
        with patch.object(os, "listdir", side_effect=AssertionError("enumeration")), \
                patch.object(os, "scandir", side_effect=AssertionError("enumeration")):
            prepared = self.prepare()
        self.assertEqual(metadata(self.root), before)
        self.assertIsNone(self.store.get_submission("initial"))
        value = decode_envelope(prepared.submission.records[0])
        self.assertEqual(value.reading.coverage, "uninspected")
        self.assertEqual(value.reading.reproduction, "unreported")
        self.assertEqual(value.title.to_dict(), self.meta["title"])
        self.assertEqual(value.provenance.to_dict(), self.meta["provenance"])
        self.assertEqual(value.extractions[0].original_inputs, ("original", "license"))
        self.assertEqual(len(value.extractions[0].mappings), 1)
        self.assertEqual(value.originals[0].artifact, value.originals[2].artifact)
        mapping = prepared.mapping
        self.assertEqual(set(mapping), {"input_root", "files"})
        self.assertEqual(mapping["input_root"], str(self.input))
        self.assertEqual([item["input_path"] for item in mapping["files"]], list(self.payloads))
        for item, (name, payload) in zip(mapping["files"], self.payloads.items()):
            self.assertEqual(item["supplied_path"], str(self.input / name))
            self.assertEqual(item["artifact"], dict(digest=hashlib.sha256(payload).hexdigest(), size=len(payload)))
            self.assertEqual(item["provenance"]["supplied_locator"]["value"], str(self.input / name))
            self.assertEqual(item["original_mode"], 0o755 if name == "run.py" else 0o644)
            self.assertEqual(checkout._signature((self.input / name).stat()), signatures[name])
            self.assertEqual((self.input / name).read_bytes(), payload)
        frozen = dumps_prepared_submission(prepared.submission)
        self.meta["authors"].clear()
        self.selection.clear()
        mapping["files"][0]["provenance"]["notes"].clear()
        object.__setattr__(prepared.submission.records[0].provenance, "actor", "changed")
        self.assertEqual(dumps_prepared_submission(prepared.submission), frozen)
        self.assertNotEqual(prepared.mapping, mapping)
        receipt = self.store.submit_typed(loads_prepared_submission(frozen))
        self.assertEqual(receipt.revisions, (("capture", 1),))
        for item, payload in zip(capturing._inventory(value), self.payloads.values()):
            self.assertEqual(self.store.read_artifact(item.artifact), payload)
        self.assertFalse(self.marker.exists())
        for root in (self.software, self.backup, self.controls):
            self.assertEqual((root / "sentinel").read_bytes(), b"Excluded synthetic material")

    def test_mapping_constructor_rejects_inconsistent_explanations(self):
        """A public detached-result constructor cannot attach arbitrary or reordered summaries."""
        prepared = self.prepare()
        for key, value in (("input_path", "other"), ("supplied_path", "/other"), ("artifact_id", "other"),
                           ("path", "other"), ("original_mode", True), ("artifact", {}), ("provenance", {})):
            mapping = prepared.mapping
            mapping["files"][0][key] = value
            with self.subTest(key=key), self.assertRaises(DomainValidationError):
                PreparedSourceCapture(prepared.submission, mapping)
        for mapping in ({}, {"input_root": "relative", "files": []},
                        {"input_root": str(self.input), "files": prepared.mapping["files"][::-1]}):
            with self.assertRaises(DomainValidationError):
                PreparedSourceCapture(prepared.submission, mapping)

    def test_template_fields_and_nested_shapes_before_open(self):
        """Every required standalone field is checked without opening selected leaves or fabricating hashes."""
        for path in dictionaries(self.meta):
            for key in (*at_path(self.meta, path), "unexpected"):
                # CreationProvenance details are not in this template; all dictionaries here are closed values.
                altered = deepcopy(self.meta)
                node = at_path(altered, path)
                if key == "unexpected":
                    node[key] = None
                else:
                    del node[key]
                with self.subTest(path=path, key=key), patch.object(capturing, "_capture_leaf", side_effect=AssertionError("opened")):
                    self.reject(lambda: self.prepare(metadata=altered))
        for key in ("artifact", "original_mode"):
            altered = deepcopy(self.meta)
            altered["originals"][0][key] = None
            self.reject(lambda: self.prepare(metadata=altered))
        for value in (None, [], {**self.meta, "authors": ()}, {**self.meta, "authors": []},
                      {**self.meta, "title": {"value": "\ud800", "unknown_reason": None}},
                      {**self.meta, "limitations": [float("nan")]}):
            self.reject(lambda: self.prepare(metadata=value))
        for value in (None, {}, True):
            self.reject(lambda: self.prepare(record_provenance=value))
            self.reject(lambda: self.prepare(submission_provenance=value))
        for key in ("record_id", "submission_id"):
            for value in (None, True, "", "../bad"):
                self.reject(lambda: self.prepare(**{key: value}))

    def test_selection_shapes_order_aliases_and_provenance_agreement(self):
        """Explicit ordered IDs and physical/logical path inventories are independent and never normalized."""
        for value in (None, [], (), "empty", iter(self.selection), set(), [None], [{}],
                      [{**self.selection[0], "extra": 1}], self.selection[:-1], self.selection[::-1],
                      [*self.selection, self.selection[0]]):
            self.reject(lambda: self.prepare(selected_files=value))
        for path in ("../a", "/absolute", "a\\b", "a//b", "a/./b", "CON", "a:", "x" * 4097):
            for logical in (False, True):
                options = self.only()
                if logical:
                    options["metadata"]["originals"][0]["path"] = path
                else:
                    options["selected_files"][0]["input_path"] = path
                self.reject(lambda: self.prepare(**options))
        for paths in (("a", "a/b"), ("A/x", "a/y"), ("é", "e\u0301"), ("same", "same")):
            for logical in (False, True):
                options = dict(metadata=deepcopy(self.meta), selected_files=deepcopy(self.selection))
                for i, path in enumerate(paths):
                    if logical:
                        options["metadata"]["originals"][i]["path"] = path
                    else:
                        options["selected_files"][i]["input_path"] = path
                self.reject(lambda: self.prepare(**options))
        for key, value in (("method", "supplied_artifact"), ("outcome", "partial"),
                           ("supplied_locator", known(str(self.input / "different")).to_dict())):
            altered = deepcopy(self.meta)
            altered["originals"][0]["provenance"][key] = value
            self.reject(lambda: self.prepare(metadata=altered))
        altered = deepcopy(self.meta)
        altered["originals"][1]["artifact_id"] = altered["originals"][0]["artifact_id"]
        self.reject(lambda: self.prepare(metadata=altered))

    def test_integer_count_and_byte_boundaries_before_reads(self):
        """Finite bounds count repeated bytes, reject invalid types and gate aggregate allocation."""
        total = sum(map(len, self.payloads.values()))
        self.prepare(max_files=len(self.payloads), max_file_bytes=max(map(len, self.payloads.values())), max_total_bytes=total)
        for key in ("revision", "expected_head", "max_files", "max_file_bytes", "max_total_bytes"):
            for value in (True, False, 1.0, None, -1, 2**63, float("inf")):
                self.reject(lambda: self.prepare(**{key: value}))
        for key, value in (("revision", 0), ("max_files", 0), ("expected_head", 2**63 - 1), ("revision", 2)):
            self.reject(lambda: self.prepare(**{key: value}))
        with patch.object(capturing, "_read_bytes", side_effect=AssertionError("allocated")):
            self.reject(lambda: self.prepare(max_total_bytes=total - 1))
            self.reject(lambda: self.prepare(max_file_bytes=1))
        with patch.object(capturing, "_capture_leaf", side_effect=AssertionError("opened")):
            self.reject(lambda: self.prepare(max_files=len(self.payloads) - 1))
            self.reject(lambda: self.prepare(selected_files=[None] * 1025, max_files=1025))
        prepared = self.prepare(**self.only(), max_file_bytes=0, max_total_bytes=0, max_files=1)
        self.assertEqual(prepared.mapping["files"][0]["artifact"]["size"], 0)
        self.reject(lambda: self.prepare(**self.only("raw.bin"), max_file_bytes=0, max_total_bytes=0))
        # The largest legal CAS pair is structurally valid and fails only actual history admission.
        self.reject(lambda: self.prepare(**self.only(), revision=2**63 - 1, expected_head=2**63 - 2,
                                        max_files=2**63 - 1, max_file_bytes=2**63 - 1,
                                        max_total_bytes=2**63 - 1), RevisionConflictError)

    def test_actual_bounded_read_requests_and_oversize_no_reads(self):
        """Retain real os.read while observing chunk requests, exact completion and one-byte EOF probes."""
        path = self.input / "raw.bin"
        payload = b"x" * (2 * checkout._CHUNK + 17)
        path.write_bytes(payload)
        identity = (path.stat().st_dev, path.stat().st_ino)
        reads = []
        real_read = os.read
        def observed(fd, size):
            """Observe only the selected inode while keeping actual operating-system reads."""
            info = os.fstat(fd)
            if (info.st_dev, info.st_ino) == identity:
                reads.append(size)
            return real_read(fd, size)
        with patch.object(os, "read", observed):
            self.prepare(**self.only("raw.bin"))
        self.assertEqual(reads, [checkout._CHUNK, checkout._CHUNK, 17, 1])
        reads.clear()
        with patch.object(os, "read", observed):
            self.reject(lambda: self.prepare(**self.only("raw.bin"), max_file_bytes=len(payload) - 1))
        self.assertEqual(reads, [])

    def test_exclusions_are_explicit_trusted_and_checked_before_open(self):
        """Exclude actual runtime/software/backup/control overlaps in either direction without scanning."""
        for name in ("backup_roots", "control_roots"):
            for value in (None, iter([]), "", {}):
                self.reject(lambda: self.prepare(**{name: value}))
            for value in ([self.input], [self.parent], [self.input / "nested"]):
                self.reject(lambda: self.prepare(**{name: value}))
        for value in (self.input, self.input / "nested", self.parent):
            self.reject(lambda: self.prepare(source_root=value))
        for root in (self.root, self.root / "objects", self.parent):
            self.reject(lambda: prepare_source_capture(self.store, root, **{
                **self.options, "source_root": self.software, "backup_roots": [], "control_roots": []}))
        self.prepare(backup_roots=(), control_roots=[])
        self.assertFalse(self.marker.exists())

    def test_unsafe_files_missing_links_and_nonregular(self):
        """Refuse unreadable/shared-write/special modes, hard links, missing files and directory leaves."""
        path = self.input / "raw.bin"
        for mode in (0, 0o200, 0o620, 0o602, 0o4600, 0o2600, 0o1600):
            path.chmod(mode)
            self.reject(self.prepare)
        path.chmod(0o644)
        link = self.parent / "hardlink"
        os.link(path, link)
        self.reject(self.prepare)
        link.unlink()
        path.unlink()
        self.reject(self.prepare)
        path.mkdir(mode=0o755)
        self.reject(self.prepare)
        path.rmdir()
        path.symlink_to(self.input / "copy.tex")
        self.reject(self.prepare)
        path.unlink()
        path.symlink_to(self.parent / "missing")
        self.reject(self.prepare)
        with self.assertRaises(CheckoutLayoutError):
            checkout._capture_regular(os.lstat("/dev/null"), "/dev/null")

    def test_fifo_socket_and_device_link_in_finite_subprocess(self):
        """Use real nonregular leaves with subprocess deadlines, never reading device content."""
        options = {**self.options, **self.only("raw.bin")}
        for name in ("record_provenance", "submission_provenance"):
            options[name] = options[name].to_dict()
        for name in ("source_root",):
            options[name] = str(options[name])
        for name in ("backup_roots", "control_roots"):
            options[name] = list(map(str, options[name]))
        program = '''
import json, os, socket, sys
from pathlib import Path
from research_pipeline.checkout import CheckoutError
from research_pipeline.domain import CreationProvenance
from research_pipeline.source_capture import prepare_source_capture
from research_pipeline.store import RecordStore
root, inputs, kind = map(Path, sys.argv[1:4])
options = json.loads(sys.argv[4])
for key in ('record_provenance', 'submission_provenance'):
    options[key] = CreationProvenance.from_dict(options[key])
path = inputs / 'raw.bin'
path.unlink()
server = None
if str(kind) == 'fifo': os.mkfifo(path, 0o600)
elif str(kind) == 'device': path.symlink_to('/dev/null')
else:
    server = socket.socket(socket.AF_UNIX)
    os.chdir(inputs)
    server.bind(path.name)
try:
    with RecordStore.open(root) as store:
        try: prepare_source_capture(store, inputs, **options)
        except CheckoutError: pass
        else: raise AssertionError('nonregular leaf accepted')
finally:
    if server is not None: server.close()
'''
        for kind in ("fifo", "device", "socket"):
            before = metadata(self.root)
            self.child(program, self.root, self.input, kind, json.dumps(options))
            self.assertEqual(metadata(self.root), before)

    def test_directory_policy_safe_modes_unsafe_modes_and_symlink_depths(self):
        """Support 0700/0755 selected directories and reject unsafe modes and ancestor substitutions."""
        nested = self.input / "physical"
        for mode in (0o700, 0o755):
            self.input.chmod(mode)
            nested.chmod(mode)
            self.prepare()
        for target in (nested, self.input, self.parent):
            old = stat.S_IMODE(target.stat().st_mode)
            for mode in (0o777, 0o775, 0o1700, 0o2700, 0o4700):
                target.chmod(mode)
                try:
                    self.reject(self.prepare)
                finally:
                    target.chmod(old)
        nested.rename(self.input / "saved")
        nested.symlink_to(self.input / "saved", target_is_directory=True)
        self.reject(self.prepare)
        nested.unlink()
        (self.input / "saved").rename(nested)
        self.input.rename(self.parent / "saved-input")
        self.input.symlink_to(self.parent / "saved-input", target_is_directory=True)
        self.reject(self.prepare)
        self.input.unlink()
        (self.parent / "saved-input").rename(self.input)
        # A lexical symlink ancestor outside the input is also refused.
        alias = self.parent / "alias"
        alias.symlink_to(self.parent, target_is_directory=True)
        altered = deepcopy(self.meta)
        for entry, selected in zip(self.entries(altered), self.selection):
            entry["provenance"]["supplied_locator"] = known(str(alias / "inputs" / selected["input_path"])).to_dict()
        self.reject(lambda: prepare_source_capture(self.store, alias / "inputs", **{**self.options, "metadata": altered}))

    def test_unsafe_ownership_and_directory_stability_checks(self):
        """Exercise ownership rules with stat-shaped observations without requiring privileged chown."""
        path = self.input / "raw.bin"
        raw = list(path.stat())
        raw[4] = os.geteuid() + 10000
        with self.assertRaises(CheckoutLayoutError):
            checkout._capture_regular(os.stat_result(raw), path)
        for target in (self.input, self.input.parent):
            original = capturing._stat
            def observed(parent, name):
                """Substitute only observed uid for a held real directory, retaining actual binding identity."""
                result = original(parent, name)
                if (result.st_dev, result.st_ino) == (target.stat().st_dev, target.stat().st_ino):
                    values = list(result)
                    values[4] = os.geteuid() + 10000
                    return os.stat_result(values)
                return result
            with patch.object(capturing, "_stat", observed):
                self.reject(self.prepare)

    def test_growth_truncation_edit_and_same_byte_substitution(self):
        """Real mutations at open/read seams fail despite bounded reads or identical replacement bytes."""
        path = self.input / "raw.bin"
        for mutation in ("grow", "truncate", "edit", "replace-read", "replace-open", "chmod"):
            payload = b"x" * (checkout._CHUNK + 10)
            path.write_bytes(payload)
            path.chmod(0o644)
            fired = False
            def mutate(boundary):
                """Mutate the selected real file once at the requested private capture boundary."""
                nonlocal fired
                trigger = "before_leaf_open" if mutation == "replace-open" else "chunk_read"
                if fired or boundary != trigger:
                    return
                fired = True
                if mutation == "grow":
                    with path.open("ab") as stream:
                        stream.write(b"added")
                elif mutation == "truncate":
                    path.write_bytes(b"short")
                elif mutation == "edit":
                    with path.open("r+b") as stream:
                        stream.write(b"y")
                elif mutation == "chmod":
                    path.chmod(0o600)
                else:
                    path.unlink()
                    path.write_bytes(payload)
                    path.chmod(0o644)
            with self.subTest(mutation=mutation), patch.object(capturing, "_fault", mutate):
                self.reject(lambda: self.prepare(**self.only("raw.bin")))
            self.assertTrue(fired)

    def test_earlier_file_mutations_rebinding_and_permissions_at_final_gate(self):
        """Establish valid previews, then reject mutations at publication/final gates without table writes."""
        for mutation in ("earlier", "nested", "root", "ancestor", "directory-mode", "file-mode"):
            with self.subTest(mutation=mutation):
                base = self.parent / ("case-" + mutation)
                base.mkdir(mode=0o755)
                inputs = base / "inputs"
                inputs.mkdir(mode=0o755)
                (inputs / "nested").mkdir(mode=0o755)
                # Disposable fixture modes must be safe independently of the process umask.
                for directory in (base, inputs, inputs / "nested"):
                    directory.chmod(0o755)
                for name in ("nested/a", "b"):
                    (inputs / name).write_bytes(b"original")
                    (inputs / name).chmod(0o644)
                meta = self.only()["metadata"]
                prototype = meta["originals"][0]
                meta["originals"] = []
                selected = []
                for index, name in enumerate(("nested/a", "b")):
                    entry = deepcopy(prototype)
                    entry.update(artifact_id="a" + str(index), path=name)
                    entry["provenance"]["supplied_locator"] = known(str(inputs / name)).to_dict()
                    meta["originals"].append(entry)
                    selected.append(dict(artifact_id=entry["artifact_id"], input_path=name))
                options = {**self.options, "metadata": meta, "selected_files": selected}
                before = metadata(self.root)
                prepare_source_capture(self.store, inputs, **options)
                self.assertEqual(metadata(self.root), before)
                self.assertIsNone(self.store.get_submission(options["submission_id"]))

                boundaries = []
                mutations = []
                def mutate(boundary):
                    """Record actual mutations after two publications or at the valid preview's final gate.

                    The enclosing test checks rejection and unchanged tables; unrelated
                    callbacks are boundary observations, never evidence of mutation.
                    """
                    boundaries.append(boundary)
                    captured = boundaries.count("file_captured")
                    if mutations:
                        return
                    if mutation == "earlier" and boundary == "file_captured" and captured == 2:
                        first = inputs / "nested/a"
                        # The held original inode prevents same-byte replacement from reusing it.
                        first.unlink()
                        first.write_bytes(b"original")
                        first.chmod(0o644)
                    elif mutation != "earlier" and boundary == "before_return":
                        if mutation == "directory-mode":
                            (inputs / "nested").chmod(0o777)
                        elif mutation == "file-mode":
                            (inputs / "b").chmod(0o666)
                        else:
                            target = {"nested": inputs / "nested", "root": inputs, "ancestor": base}[mutation]
                            target.rename(target.with_name(target.name + "-saved"))
                            target.mkdir(mode=0o755)
                            target.chmod(0o755)
                    else:
                        return
                    mutations.append((boundary, captured))

                with patch.object(capturing, "_fault", mutate):
                    error = self.reject(
                        lambda: prepare_source_capture(self.store, inputs, **options), CheckoutIntegrityError)
                diagnostic = (f"{type(error).__name__}: {error}; "
                              f"boundaries={boundaries!r}; mutations={mutations!r}")
                self.assertEqual(boundaries.count("file_captured"), 2, diagnostic)
                trigger = "file_captured" if mutation == "earlier" else "before_return"
                self.assertEqual(mutations, [(trigger, 2)], diagnostic)
                if mutation != "earlier":
                    self.assertEqual(boundaries.count("before_return"), 1, diagnostic)

    def test_unselected_sibling_activity_is_not_content_evidence(self):
        """Unrelated sibling changes neither require enumeration nor cause directory mtime false positives."""
        def mutate(boundary):
            """Create unrelated siblings after capture without changing any selected binding."""
            if boundary == "before_return":
                (self.input / "unselected").write_bytes(b"opaque")
                (self.parent / "unrelated").mkdir()
        with patch.object(capturing, "_fault", mutate):
            self.prepare()

    def test_lineage_byte_ranges_and_admission_failures_retain_orphans(self):
        """Validate actual sizes/lineage after capture and use existing typed preview without metadata writes."""
        variants = []
        bad = deepcopy(self.meta)
        bad["locations"][1]["end"] = 9999
        variants.append(bad)
        bad = deepcopy(self.meta)
        bad["extractions"][0]["original_inputs"] = ["text"]
        variants.append(bad)
        bad = deepcopy(self.meta)
        bad["extractions"][0]["mappings"][0]["original_location"] = "upstream"
        variants.append(bad)
        for bad in variants:
            self.reject(lambda: self.prepare(metadata=bad))
        self.assertTrue(list((self.root / "objects").iterdir()))
        bad = deepcopy(self.meta)
        bad["related_sources"] = [dict(reference=RecordReference("missing", 1, "related_source", "source").to_dict(), relation="declared")]
        self.reject(lambda: self.prepare(metadata=bad), ReferenceResolutionError)
        # Failure during a later read leaves earlier published objects, never an application reservation.
        calls = 0
        def mutate(boundary):
            """Grow a later held file after the first real publication."""
            nonlocal calls
            if boundary == "file_captured":
                calls += 1
                if calls == 1:
                    (self.input / "LICENSE").write_bytes(b"later modified input")
        with patch.object(capturing, "_fault", mutate):
            self.reject(self.prepare)
        self.assertEqual(calls, 1)
        digest = hashlib.sha256(self.payloads["physical/α.tex"]).hexdigest()
        self.assertEqual((self.root / "objects" / digest).read_bytes(), self.payloads["physical/α.tex"])

    def test_publication_failure_retains_prior_objects_and_chained_error(self):
        """A corrupt later object fails publication without repairing storage or altering selected files."""
        artifact = self.store.put_artifact(self.payloads["LICENSE"])
        path = self.root / "objects" / artifact.digest
        path.chmod(0o600)
        path.write_bytes(b"damaged")
        path.chmod(0o400)
        error = self.reject(self.prepare)
        self.assertIsInstance(error.__cause__, ArtifactError)
        digest = hashlib.sha256(self.payloads["physical/α.tex"]).hexdigest()
        self.assertTrue((self.root / "objects" / digest).exists())
        self.assertEqual(path.read_bytes(), b"damaged")
        for name, data in self.payloads.items():
            self.assertEqual((self.input / name).read_bytes(), data)

    def test_preview_history_and_reference_roles(self):
        """Constrained malformed history/dangling or wrong references fail; shallow sources stay shallow."""
        self.store.submit(request("generic", [record("opaque", kind="source", content={"format": "unsupported"}),
                                              record("wrong", kind="run"), record("report", kind="work_product_manifest")]))
        bad = deepcopy(self.meta)
        bad["related_sources"] = [dict(reference=RecordReference("opaque", 1, "related_source", "source").to_dict(), relation="distinct")]
        self.prepare(metadata=bad)
        for target in ("missing", "wrong"):
            bad["related_sources"][0]["reference"]["record_id"] = target
            self.reject(lambda: self.prepare(metadata=bad), ReferenceResolutionError)
        bad = deepcopy(self.meta)
        bad["reading"]["report"] = RecordReference("report", 1, "reading_report", "work_product_manifest").to_dict()
        self.reject(lambda: self.prepare(metadata=bad), ReferenceResolutionError)
        first = self.prepare().submission
        receipt = self.store.submit_typed(first)
        self.reject(lambda: self.prepare(revision=2, expected_head=1, submission_id="no-link"), ReferenceResolutionError)
        next_meta = deepcopy(self.meta)
        next_meta["supersedes"] = RecordReference("capture", 1, "supersedes", "source").to_dict()
        next_meta["work_id"] = "changed"
        self.reject(lambda: self.prepare(metadata=next_meta, revision=2, expected_head=1,
                                        submission_id="changed-work"), ReferenceResolutionError)
        self.assertEqual(self.store.get_submission("initial"), receipt)
        # Locally coherent generic history can still violate constrained report content.
        value = replace(decode_envelope(first.records[0]), reading=replace(uninspected().reading,
            report=RecordReference("report", 1, "reading_report", "work_product_manifest")))
        self.store.submit(request("bad-history", [encode_envelope("bad-history", 1, value, CREATOR)]))
        next_meta.update(work_id=self.meta["work_id"], supersedes=RecordReference("bad-history", 1, "supersedes", "source").to_dict())
        self.reject(lambda: self.prepare(metadata=next_meta, record_id="bad-history", revision=2,
                                        expected_head=1, submission_id="next"), ReferenceResolutionError)

    def test_strict_proposal_fields_duplicates_types_and_product_separation(self):
        """Pure Source serialization preserves order and rejects omitted nested fields and other products."""
        submission = request("serialized", [encode_envelope("capture", 1, source(), CREATOR)], {"capture": 0})
        encoded = dumps_prepared_submission(submission)
        document = json.loads(encoded)
        self.assertEqual(encoded, json.dumps(document, sort_keys=True, separators=(",", ":"), ensure_ascii=True))
        for data in (encoded, encoded.encode(), json.dumps(document, ensure_ascii=False).encode()):
            self.assertEqual(loads_prepared_submission(data), submission)
        for path in dictionaries(document):
            if path[-1:] in (("details",), ("expected_heads",)) or "details" in path:
                continue
            for key in (*at_path(document, path), "unexpected"):
                bad = deepcopy(document)
                node = at_path(bad, path)
                if key == "unexpected":
                    node[key] = None
                else:
                    del node[key]
                with self.subTest(path=path, key=key), self.assertRaises(DomainValidationError):
                    loads_prepared_submission(json.dumps(bad))
        for path, key, value in (((), "version", True), ((), "version", 2), ((), "format", work_product_import._FORMAT),
                (("submission", "expected_heads"), "capture", False),
                (("submission", "records", 0), "revision", True),
                (("submission", "records", 0, "artifact_references", 0), "size", 1.0),
                (("submission", "records", 0, "content", "originals", 0), "original_mode", True)):
            bad = deepcopy(document)
            at_path(bad, path)[key] = value
            with self.assertRaises(DomainValidationError):
                loads_prepared_submission(json.dumps(bad))
        for raw in (None, {}, b"\xff", "{", encoded.replace('"version":1', '"version":1,"version":1', 1),
                    encoded.replace('"outcome":"partial"', '"outcome":"partial","outcome":"partial"', 1),
                    encoded.replace('"version":1', '"version":NaN', 1), '"\ud800"'):
            with self.assertRaises(DomainValidationError):
                loads_prepared_submission(raw)
        with self.assertRaises(DomainValidationError):
            work_product_import.loads_prepared_submission(encoded)
        artifact = submission.records[0].artifact_references[0]
        product = replace(manifest(artifact), supersedes=RecordReference("product", 1, "supersedes", "work_product_manifest"))
        other = work_product_import.dumps_prepared_submission(request("product", [product_envelope("product", 2, product, CREATOR)], {"product": 1}))
        with self.assertRaises(DomainValidationError):
            loads_prepared_submission(other)
        # Serialize only memory: even open/read access is forbidden in this block.
        with patch.object(os, "open", side_effect=AssertionError("filesystem")), \
                patch.object(RecordStore, "_check_prepared_typed", side_effect=AssertionError("admission")):
            self.assertEqual(dumps_prepared_submission(loads_prepared_submission(encoded)), encoded)

    def test_forged_typed_values_and_ordered_projections(self):
        """Bypassing frozen classes cannot launder invalid provenance, references or projection order."""
        submission = request("serialized", [encode_envelope("capture", 1, source(), CREATOR)], {"capture": 0})
        for target, field, value in ((submission.provenance, "actor", None),
                (submission.records[0].provenance, "created_at", "bad"),
                (submission.provenance, "created_at", "2026-10-30T12:00:00.000Z"),
                (submission.records[0].artifact_references[0], "size", True),
                (submission.records[0], "artifact_references", submission.records[0].artifact_references[::-1]),
                (submission, "records", [])):
            original = getattr(target, field)
            object.__setattr__(target, field, value)
            try:
                with self.assertRaises(DomainValidationError):
                    dumps_prepared_submission(submission)
            finally:
                object.__setattr__(target, field, original)
        bad = submission.to_dict()
        bad["expected_heads"]["capture"] = 1
        from research_pipeline.domain import Submission
        with self.assertRaises(DomainValidationError):
            dumps_prepared_submission(Submission.from_dict(bad))

    def test_documented_capture_example(self):
        """Execute the exact durable-save/capture/commit Markdown block in a fresh candidate interpreter."""
        document = (Path(__file__).resolve().parents[2] / "docs" / "source-capture.md").read_text()
        section = document.split("## Runnable synthetic capture example\n", 1)[1]
        program = section.split("```python\n", 1)[1].split("```", 1)[0]
        self.child(program)

    def test_maximum_inventory_and_logical_path_bounds(self):
        """Capture the full 1,024-entry empty inventory and preserve a maximal portable logical name."""
        options = self.only()
        prototype = options["metadata"]["originals"][0]
        options["metadata"]["originals"] = []
        options["selected_files"] = []
        for index in range(1024):
            name = "empty-" + str(index)
            path = self.input / name
            path.write_bytes(b"")
            path.chmod(0o600)
            entry = deepcopy(prototype)
            entry.update(artifact_id=name, path="x" * 4096 if index == 0 else name)
            entry["provenance"]["supplied_locator"] = known(str(path)).to_dict()
            options["metadata"]["originals"].append(entry)
            options["selected_files"].append(dict(artifact_id=name, input_path=name))
        before = metadata(self.root)
        result = self.prepare(**options, max_files=1024, max_file_bytes=0, max_total_bytes=0)
        self.assertEqual(metadata(self.root), before)
        self.assertEqual(len(result.mapping["files"]), 1024)
        self.assertEqual(len(result.mapping["files"][0]["path"]), 4096)
        self.assertEqual(len(result.submission.records[0].artifact_references), 1)
        options["metadata"]["originals"][0]["path"] += "x"
        self.reject(lambda: self.prepare(**options, max_files=1024), DomainValidationError)

    def test_descriptors_closed_after_success_read_failure_and_return_mutation(self):
        """All actually opened operation descriptors close on every outcome, including retained earlier leaves."""
        actual_open, actual_close, actual_read = os.open, os.close, os.read
        opened = set()
        path = self.input / "raw.bin"
        def open_file(*args, **kwargs):
            """Track real opens so leak checks require no descriptor-directory enumeration."""
            fd = actual_open(*args, **kwargs)
            opened.add(fd)
            return fd
        def close_file(fd):
            """Keep actual close behavior and remove only descriptors seen by this operation."""
            actual_close(fd)
            opened.discard(fd)
        def read_file(fd, size):
            """Raise an actual I/O-shaped failure only for the selected inode after opens succeed."""
            if os.fstat(fd).st_ino == path.stat().st_ino:
                raise OSError("synthetic selected read failure")
            return actual_read(fd, size)
        def mutate(boundary):
            """Modify one held leaf only after the detached result has been built."""
            if boundary == "before_return":
                path.write_bytes(b"late")
        with patch.object(os, "open", open_file), patch.object(os, "close", close_file):
            self.prepare(**self.only("raw.bin"))
            self.assertEqual(opened, set())
            with patch.object(os, "read", read_file):
                error = self.reject(lambda: self.prepare(**self.only("raw.bin")))
                self.assertIsInstance(error.__cause__, OSError)
            self.assertEqual(opened, set())
            with patch.object(capturing, "_fault", mutate):
                self.reject(lambda: self.prepare(**self.only("raw.bin")))
            self.assertEqual(opened, set())

    def test_capture_keeps_declared_partial_reading_and_generic_transition_rules(self):
        """Bytes neither upgrade selected-material coverage nor retroactively certify a generic predecessor."""
        meta = deepcopy(self.meta)
        meta["reading"].update(coverage="selected_material", locations=["page"],
                                reproduction="not_attempted", limitations=["Partial supplied declaration"])
        value = decode_envelope(self.prepare(metadata=meta).submission.records[0])
        self.assertEqual(value.reading.coverage, "selected_material")
        self.assertEqual(value.reading.reproduction, "not_attempted")
        self.store.submit(request("generic", [record("capture", kind="source", content={"legacy": True})]))
        request2 = self.prepare(metadata=meta, revision=2, expected_head=1, submission_id="typed-transition").submission
        self.assertIsNone(decode_envelope(request2.records[0]).supersedes)
        self.store.submit_typed(request2)
        self.assertEqual(self.store.get_revision("capture", 1).content, {"legacy": True})
        self.assertEqual(self.store.head("capture"), 2)

    def test_relative_input_root_and_exact_spelling_are_preserved(self):
        """Anchor a relative root lexically and open the supplied Unicode spelling without renaming it."""
        previous = Path.cwd()
        try:
            os.chdir(self.parent)
            prepared = prepare_source_capture(self.store, "inputs", **self.options)
        finally:
            os.chdir(previous)
        self.assertEqual(prepared.mapping["input_root"], str(self.input))
        self.assertEqual(prepared.mapping["files"][0]["input_path"], "physical/α.tex")
        self.assertEqual(prepared.mapping["files"][0]["path"], "originals/α.tex")

    def test_inert_module_import(self):
        """Fresh candidate import performs no filesystem writes, process launches or network connections."""
        self.child('''
import sys
from pathlib import Path
before = sorted(str(path) for path in Path.cwd().rglob('*'))
def guard(event, args):
    """Reject writes and execution/network effects during the actual candidate import."""
    if event == 'open':
        mode, flags = args[1:3]
        if (isinstance(mode, str) and any(c in mode for c in 'wax+')) or flags & (1 | 2 | 64 | 512 | 1024):
            raise AssertionError((event, args))
    if event in ('os.mkdir', 'os.remove', 'os.rename', 'subprocess.Popen', 'socket.connect'):
        raise AssertionError((event, args))
sys.addaudithook(guard)
import research_pipeline.source_capture
assert sorted(str(path) for path in Path.cwd().rglob('*')) == before
''')
