"""Real draft capture, strict proposals, explicit commits and durable original-ID recovery."""

from copy import deepcopy
from dataclasses import replace
import json
import os
from pathlib import Path
import socket
import unittest
from unittest.mock import patch

from research_pipeline import work_product_import as importing
from research_pipeline.backup import create_backup, restore_backup
from research_pipeline.checkout import CheckoutError, checkout_work_product
from research_pipeline.domain import (
    CreationProvenance, DomainValidationError, RecordReference, Submission,
)
from research_pipeline.store import (
    RecordStore, ReferenceResolutionError, RevisionConflictError, SubmissionConflictError,
)
from research_pipeline.work_product import WorkProductFile, decode_envelope, encode_envelope
from research_pipeline.work_product_import import (
    dumps_prepared_submission, loads_prepared_submission, prepare_work_product_import,
)
from tests import test_checkout as checkout_tests
from tests.test_assessment_store import metadata
from tests.test_store import CONTROLLER, CREATOR, record, request
from tests.test_work_product import manifest


EDITOR = CreationProvenance("editor", "2026-10-30T14:00:00Z", {"edit": [1, True]})


def proposed_metadata(value):
    """Extract the complete explicit editable field set from an existing serialized manifest."""
    return {key: value.to_dict()[key] for key in importing._METADATA}


class ImportTests(unittest.TestCase):
    """Reuse real checkout fixtures without inheriting or duplicating their accepted tests."""

    run_checkout = checkout_tests.CheckoutTests.run_checkout
    child = checkout_tests.CheckoutTests.child
    rewrite = checkout_tests.CheckoutTests.rewrite

    def setUp(self):
        """Create a committed multi-file bundle and a fully published independent draft."""
        checkout_tests.CheckoutTests.setUp(self)
        self.run_checkout()
        self.meta = proposed_metadata(self.value)
        self.selection = [entry.path for entry in self.value.files]
        self.import_options = dict(**self.options, max_inventory_entries=100,
                                   expected_head=1, metadata=self.meta, selected_paths=self.selection,
                                   submission_id="import", record_provenance=EDITOR,
                                   submission_provenance=CONTROLLER)

    def prepare(self, destination=None, **options):
        """Prepare against the pinned fixture base with explicit caller metadata and limits."""
        return prepare_work_product_import(self.store, self.base, destination or self.destination,
                                           **{**self.import_options, **options})

    def reject(self, operation, error=(DomainValidationError, CheckoutError)):
        """Assert a useful failure and unchanged values in every application metadata table."""
        before = metadata(self.root)
        with self.assertRaises(error) as caught:
            operation()
        self.assertTrue(str(caught.exception))
        self.assertEqual(metadata(self.root), before)
        return caught.exception

    def test_multifile_preview_detachment_summary_and_frozen_capture(self):
        """Explicit edits/removals/additions preserve drafts and produce honest deterministic summaries."""
        edited = "Revised α ∀\n".encode()
        (self.destination / "notes/α.txt").write_bytes(edited)
        (self.destination / "added.bin").write_bytes(b"\x00\xfe")
        (self.destination / "added.bin").chmod(0o600)
        (self.destination / "unknown").write_bytes(b"private unselected text")
        (self.destination / "data/raw.bin").write_bytes(b"unselected edit")
        selection = ["copy.txt", "notes/α.txt", "empty", "added.bin"]
        meta = {**self.meta, "entry_file": "added.bin", "title": "Edited title", "authors": ["β", "α"]}
        before = metadata(self.root)
        prepared = self.prepare(metadata=meta, selected_paths=selection, submission_provenance=EDITOR)
        again = self.prepare(metadata=meta, selected_paths=selection, submission_provenance=EDITOR)
        self.assertEqual(prepared.summary, again.summary)
        self.assertEqual(dumps_prepared_submission(prepared.submission), dumps_prepared_submission(again.submission))
        self.assertEqual(metadata(self.root), before)
        summary = prepared.summary
        self.assertEqual([(p["path"], p["status"]) for p in summary["paths"]], [
            ("notes/α.txt", "changed"), ("data/raw.bin", "removed"), ("copy.txt", "unchanged"),
            ("empty", "unchanged"), ("added.bin", "added")])
        self.assertEqual(summary["paths"][0]["old"], self.a.to_dict())
        self.assertEqual(summary["paths"][1]["new"], None)
        self.assertEqual(summary["old_files"], self.selection)
        self.assertEqual(summary["new_files"], selection)
        self.assertEqual(summary["base"], self.base.to_dict())
        self.assertEqual(summary["proposed_revision"], 2)
        self.assertEqual(summary["metadata_changes"]["entry_file"], {"before": "notes/α.txt", "after": "added.bin"})
        self.assertEqual(summary["provenance_changes"]["record"], {"before": CREATOR.to_dict(), "after": EDITOR.to_dict()})
        self.assertEqual(summary["provenance_changes"]["submission"], {"before": CONTROLLER.to_dict(), "after": EDITOR.to_dict()})
        self.assertEqual(summary["structural_changes"]["supersedes"]["after"],
                         RecordReference("bundle", 1, "supersedes", "work_product_manifest").to_dict())
        self.assertEqual({entry["path"] for entry in summary["unselected_material"]}, {"data", "unknown"})
        # Omitted base files inside an unvisited directory are covered by its opaque report.
        self.assertTrue(next(e for e in summary["unselected_material"] if e["path"] == "data")["opaque"])
        frozen = dumps_prepared_submission(prepared.submission)
        meta["authors"].clear()
        selection.clear()
        summary["paths"].clear()
        exposed = prepared.submission
        object.__setattr__(exposed.records[0].provenance, "actor", "forged after access")
        self.assertEqual(dumps_prepared_submission(prepared.submission), frozen)
        self.assertEqual((self.destination / "notes/α.txt").read_bytes(), edited)
        self.assertEqual((self.destination / "data/raw.bin").read_bytes(), b"unselected edit")
        self.assertEqual((self.destination / "unknown").read_bytes(), b"private unselected text")
        (self.destination / "notes/α.txt").write_bytes(b"later edit")
        (self.destination / "added.bin").unlink()
        receipt = self.store.submit_typed(loads_prepared_submission(frozen))
        self.assertEqual(receipt.revisions, (("bundle", 2),))
        new = self.store.get_typed_revision("bundle", 2)[1]
        self.assertEqual(self.store.read_artifact(new.files[1].artifact), edited)
        self.assertEqual(self.store.read_artifact(self.a), self.text)
        self.assertEqual(self.store.get_revision("bundle", 1), self.envelope)

    def test_ordering_only_and_repeated_bytes(self):
        """File/author order is visible even when all exact bytes and path membership are unchanged."""
        selected = self.selection[::-1]
        prepared = self.prepare(selected_paths=selected, metadata={**self.meta, "authors": self.meta["authors"][::-1]},
                                record_provenance=CREATOR)
        self.assertTrue(all(entry["status"] == "unchanged" for entry in prepared.summary["paths"]))
        self.assertEqual(prepared.summary["new_files"], selected)
        self.assertEqual(prepared.summary["provenance_changes"], {})
        self.assertEqual(list(prepared.summary["metadata_changes"]), ["authors"])
        value = decode_envelope(prepared.submission.records[0])
        self.assertEqual(value.files[1].artifact, value.files[3].artifact)
        self.assertEqual(len(prepared.submission.records[0].artifact_references), 3)

    def test_strict_metadata_selection_and_head(self):
        """Reject omitted/extra fields, malformed nested JSON, paths, entry and implicit rebasing."""
        for field in importing._METADATA:
            bad = dict(self.meta)
            del bad[field]
            with self.subTest(missing=field):
                self.reject(lambda: self.prepare(metadata=bad))
        bad_meta = [None, [], {**self.meta, "files": []}, {**self.meta, "authors": ("author",)},
                    {**self.meta, "title": ""}, {**self.meta, "purpose": "\ud800"},
                    {**self.meta, "entry_file": "COPY.TXT"}, {**self.meta, "task": {}},
                    {**self.meta, "limitations": [float("nan")]},
                    {**self.meta, "task": {"record_id": "t", "revision": 1, "relationship": "task"}}]
        for value in bad_meta:
            with self.subTest(metadata=repr(value)):
                self.reject(lambda: self.prepare(metadata=value))
        for paths in (None, [], "copy.txt", {"copy.txt"}, [1], ["copy.txt", "copy.txt"],
                      ["a", "a/b"], ["A/x", "a/y"], ["é", "e\u0301"], ["../a"], ["/a"],
                      ["CON"], ["a\\b"], ["a//b"], ["a:"] , [".WORK-PRODUCT/a"], [".ｗork-product/a"]):
            with self.subTest(paths=paths):
                self.reject(lambda: self.prepare(selected_paths=paths))
        self.reject(lambda: self.prepare(expected_head=2))
        self.reject(lambda: self.prepare(selected_paths=["missing"], metadata={**self.meta, "entry_file": "missing"}))
        self.reject(lambda: self.prepare(protected_roots=None))
        self.reject(lambda: self.prepare(source_root=self.destination))
        self.reject(lambda: self.prepare(protected_roots=[self.parent]))

    def test_budget_boundaries_base_and_selection_independently(self):
        """Exact limits pass; repeated logical bytes, selection growth and invalid integers fail honestly."""
        total = 2 * len(self.text) + len(self.binary)
        descriptor_size = (self.destination / ".work-product/checkout.json").stat().st_size
        # Root has five entries including controls; each visited nested directory has one.
        self.prepare(max_files=4, max_file_bytes=len(self.text), max_total_bytes=total,
                     max_descriptor_bytes=descriptor_size, max_inventory_entries=7)
        for key, value in (("max_files", 3), ("max_file_bytes", len(self.text) - 1),
                           ("max_total_bytes", total - 1), ("max_descriptor_bytes", descriptor_size - 1),
                           ("max_inventory_entries", 6)):
            with self.subTest(key=key):
                self.reject(lambda: self.prepare(**{key: value}))
        for key in ("expected_head", "max_files", "max_file_bytes", "max_total_bytes",
                    "max_descriptor_bytes", "max_inventory_entries"):
            for value in (True, 1.0, None, float("inf"), -1):
                with self.subTest(key=key, value=value):
                    self.reject(lambda: self.prepare(**{key: value}))
        for key in ("expected_head", "max_files", "max_descriptor_bytes", "max_inventory_entries"):
            self.reject(lambda: self.prepare(**{key: 0}))
        self.reject(lambda: self.prepare(selected_paths=["empty"], metadata={**self.meta, "entry_file": "empty"},
                                         max_total_bytes=0))
        (self.destination / "copy.txt").write_bytes(b"x" * 100)
        self.reject(lambda: self.prepare(max_file_bytes=99))
        self.reject(lambda: self.prepare(max_total_bytes=total))
        (self.destination / "new").write_bytes(b"")
        self.reject(lambda: self.prepare(selected_paths=[*self.selection, "new"], max_files=4))

    def test_zero_byte_budgets_for_empty_base_and_proposal(self):
        """Zero is a valid byte budget when both logical inventories consist of empty files."""
        value = replace(manifest(self.empty), files=[WorkProductFile("empty", self.empty)], entry_file="empty")
        self.store.submit_typed(request("zero-base", [encode_envelope("zero", 1, value, CREATOR)]))
        base = RecordReference("zero", 1, "checkout_base", "work_product_manifest")
        destination = self.parent / "zero-draft"
        checkout_work_product(self.store, base, destination, **self.options)
        result = prepare_work_product_import(self.store, base, destination, **{
            **self.import_options, "metadata": proposed_metadata(value), "selected_paths": ["empty"],
            "max_file_bytes": 0, "max_total_bytes": 0})
        self.assertEqual(result.submission.records[0].artifact_references, (self.empty,))

    def test_descriptor_coherent_substitutions_and_incomplete_controls(self):
        """Even coherent local metadata changes fail canonical comparison, including bool/int details."""
        path = self.destination / ".work-product/checkout.json"
        original = path.read_bytes()
        document = json.loads(original)
        variants = []
        for key, value in (("title", "coherently edited"), ("purpose", "other")):
            altered = deepcopy(document)
            altered["envelope"]["content"][key] = value
            variants.append(altered)
        altered = deepcopy(document)
        altered["envelope"]["provenance"]["details"]["source"][1]["run"] = True
        variants.append(altered)
        altered = deepcopy(document)
        altered["envelope"]["provenance"]["actor"] = "new-declared-author"
        variants.append(altered)
        altered = deepcopy(document)
        altered["base"]["revision"] = altered["envelope"]["revision"] = 2
        variants.append(altered)
        altered = deepcopy(document)
        altered["base"]["record_id"] = altered["envelope"]["record_id"] = "another"
        variants.append(altered)
        altered = deepcopy(document)
        for entry in altered["envelope"]["content"]["files"]:
            if entry["artifact"]["digest"] == self.a.digest:
                entry["artifact"]["digest"] = "f" * 64
        altered["envelope"]["artifact_references"][0]["digest"] = "f" * 64
        variants.append(altered)
        for value in variants:
            self.rewrite(path, json.dumps(value).encode())
            self.reject(self.prepare)
        self.rewrite(path, original)
        for name in ("incomplete", "extra"):
            extra = path.parent / name
            extra.symlink_to(self.parent / "absent")
            self.reject(self.prepare)
            extra.unlink()
        path.unlink()
        self.reject(self.prepare)

    def test_control_and_descriptor_types_and_modes(self):
        """Unsafe controls and product directory permissions fail before any content capture."""
        descriptor = self.destination / ".work-product/checkout.json"
        descriptor.chmod(0o600)
        self.reject(self.prepare)
        descriptor.chmod(0o400)
        control = descriptor.parent
        control.chmod(0o755)
        self.reject(self.prepare)
        control.chmod(0o700)
        nested = self.destination / "notes"
        nested.chmod(0o755)
        self.reject(self.prepare)
        nested.chmod(0o700)
        control.rename(self.destination / "saved-controls")
        control.symlink_to(self.destination / "saved-controls", target_is_directory=True)
        self.reject(self.prepare)

    def test_missing_corrupt_original_even_when_removed(self):
        """Preparation verifies all base originals, including artifacts omitted from proposed files."""
        path = self.root / "objects" / self.b.digest
        self.rewrite(path, b"bad", 0o400)
        options = dict(selected_paths=["copy.txt"], metadata={**self.meta, "entry_file": "copy.txt"})
        self.reject(lambda: self.prepare(**options))
        path.unlink()
        self.reject(lambda: self.prepare(**options))

    def test_selected_unsafe_modes_links_and_nonregular_types(self):
        """Reject hard links, shared-write/special/unreadable files and directory or socket leaves."""
        path = self.destination / "copy.txt"
        for mode in (0o620, 0o602, 0o4600, 0o2600, 0o1600, 0o200):
            path.chmod(mode)
            self.reject(self.prepare)
        path.chmod(0o600)
        linked = self.parent / "hardlink"
        os.link(path, linked)
        self.reject(self.prepare)
        linked.unlink()
        path.unlink()
        path.mkdir(mode=0o700)
        self.reject(self.prepare)
        path.rmdir()
        with socket.socket(socket.AF_UNIX) as server:
            previous = Path.cwd()
            try:
                os.chdir(path.parent)
                server.bind(path.name)
            finally:
                os.chdir(previous)
            self.reject(self.prepare)

    def test_symlink_fifo_and_device_rejection_in_finite_subprocess(self):
        """Potentially blocking leaves are refused before open; device metadata checks are exercised too."""
        program = '''
import json, os, sys
from pathlib import Path
from research_pipeline.checkout import CheckoutError
from research_pipeline.domain import RecordReference
from research_pipeline.store import RecordStore
from research_pipeline.work_product_import import prepare_work_product_import
from research_pipeline.domain import CreationProvenance
root, draft, software, kind = map(Path, sys.argv[1:])
path = draft / "copy.txt"
path.unlink()
if str(kind) == "fifo": os.mkfifo(path, 0o600)
else: path.symlink_to("/dev/null" if str(kind) == "device" else draft / "notes/α.txt")
with RecordStore.open(root) as store:
    content = store.get_typed_revision("bundle", 1)[1].to_dict()
    for key in ("format", "version", "kind", "files", "supersedes"): del content[key]
    p = CreationProvenance("author", "2026-10-30T12:00:00Z", {})
    try:
        prepare_work_product_import(store, RecordReference("bundle", 1, "checkout_base", "work_product_manifest"),
            draft, expected_head=1, metadata=content, selected_paths=["notes/α.txt", "copy.txt"],
            submission_id="child", record_provenance=p, submission_provenance=p,
            source_root=software, protected_roots=[], max_file_bytes=1024, max_total_bytes=4096,
            max_files=10, max_descriptor_bytes=100000, max_inventory_entries=100)
    except CheckoutError: pass
    else: raise AssertionError("unsafe leaf accepted")
'''
        for kind in ("fifo", "symlink", "device"):
            before = metadata(self.root)
            self.child(program, self.root, self.destination, self.source_tree, kind)
            self.assertEqual(metadata(self.root), before)
        # A real character device is owned by the host, so test its actual stat
        # without mknod privileges or attempting to read it.
        with self.assertRaises(CheckoutError):
            importing._capture_regular(os.lstat("/dev/null"), "/dev/null")

    def test_capture_mutations_and_equal_byte_replacement(self):
        """Real reads detect growth, truncation, in-place changes and same-byte inode substitutions."""
        path = self.destination / "notes/α.txt"
        for mutation in ("grow", "truncate", "in-place", "replace", "preopen"):
            path.write_bytes(b"x" * (importing._CHUNK + 10))
            path.chmod(0o600)
            fired = False
            def mutate(boundary):
                """Mutate a disposable selected file once at a real capture boundary."""
                nonlocal fired
                wanted = "before_leaf_open" if mutation == "preopen" else "chunk_read"
                # Descriptor reads also use the chunk seam; wait for the selected
                # capture to start so the mutation occurs during its actual read.
                if boundary == "before_leaf_open":
                    mutate.capturing = True
                if boundary != wanted or fired or not mutate.capturing:
                    return
                fired = True
                if mutation == "grow":
                    with path.open("ab") as stream:
                        stream.write(b"extra")
                elif mutation == "truncate":
                    path.write_bytes(b"short")
                elif mutation == "in-place":
                    with path.open("r+b") as stream:
                        stream.write(b"y")
                else:
                    data = path.read_bytes()
                    path.unlink()
                    path.write_bytes(data)
                    path.chmod(0o600)
            mutate.capturing = False
            with self.subTest(mutation=mutation), patch.object(importing, "_fault", mutate):
                self.reject(self.prepare)
            self.assertTrue(fired)

    def test_changes_to_earlier_files_and_directory_control_rebinding(self):
        """Final held-descriptor checks detect mutations after capture, including same-byte replacement."""
        for target in ("earlier", "nested", "root", "ancestor", "control", "descriptor", "inventory"):
            destination = self.parent / ("draft-" + target)
            self.run_checkout(destination)
            fired = False
            def mutate(boundary):
                """Substitute a held binding after real bytes have been published as artifacts."""
                nonlocal fired
                if boundary != "before_return" or fired:
                    return
                fired = True
                if target == "earlier":
                    (destination / "notes/α.txt").write_bytes(b"changed after capture")
                elif target == "inventory":
                    (destination / "new-extra").write_bytes(b"unknown")
                elif target == "descriptor":
                    path = destination / ".work-product/checkout.json"
                    data = path.read_bytes()
                    path.unlink()
                    path.write_bytes(data)
                    path.chmod(0o400)
                else:
                    path = {"nested": destination / "notes", "root": destination,
                            "ancestor": self.parent, "control": destination / ".work-product"}[target]
                    # Ancestor substitution uses a child parent below the fixture
                    # root, avoiding renaming the TemporaryDirectory itself.
                    if target == "ancestor":
                        path = destination.parent
                    saved = path.with_name(path.name + "-saved")
                    path.rename(saved)
                    path.mkdir(mode=0o700)
            if target == "ancestor":
                parent = self.parent / "ancestor"
                parent.mkdir(mode=0o700)
                destination.rename(parent / "draft")
                destination = parent / "draft"
            with self.subTest(target=target), patch.object(importing, "_fault", mutate):
                self.reject(lambda: self.prepare(destination))
            self.assertTrue(fired)

    def test_earlier_file_changes_while_later_file_captured(self):
        """A later capture cannot mask a prior selected inode changing under its held descriptor."""
        calls = 0
        def mutate(boundary):
            """Change the first file only after the second file has really been read/published."""
            nonlocal calls
            if boundary == "file_captured":
                calls += 1
                if calls == 2:
                    (self.destination / "notes/α.txt").write_bytes(b"late change")
        with patch.object(importing, "_fault", mutate):
            self.reject(self.prepare)
        self.assertGreaterEqual(calls, 2)

    def test_unselected_bounded_opaque_report_no_content_reads(self):
        """Unknown files/types and omitted base files are reported without descending opaque subtrees."""
        (self.destination / "opaque").mkdir(mode=0o700)
        for number in range(30):
            (self.destination / "opaque" / str(number)).write_bytes(b"never read")
        (self.destination / "outside-link").symlink_to(self.root, target_is_directory=True)
        os.mkfifo(self.destination / "pipe", 0o600)
        unreadable = self.destination / "secret"
        unreadable.write_bytes(b"never read")
        unreadable.chmod(0)
        invalid = os.fsencode(self.destination) + b"/bad-\xff"
        fd = os.open(invalid, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        os.close(fd)
        result = self.prepare(selected_paths=["notes/α.txt"], max_inventory_entries=11)
        entries = {entry["path"]: entry for entry in result.summary["unselected_material"]}
        self.assertEqual(entries["opaque"]["kind"], "directory")
        self.assertTrue(entries["data"]["opaque"])
        self.assertEqual(entries["copy.txt"]["kind"], "file")
        self.assertEqual(entries["outside-link"]["kind"], "symlink")
        self.assertEqual(entries["pipe"]["kind"], "other")
        self.assertTrue(entries["bad-\\udcff"]["path_escaped"])
        self.assertEqual(unreadable.stat().st_mode & 0o777, 0)
        self.reject(lambda: self.prepare(selected_paths=["notes/α.txt"], max_inventory_entries=10))

    def test_enumeration_membership_mutation_fails(self):
        """Directory membership changes during iterator enumeration fail rather than truncate reports."""
        original = importing._entries
        changed = False
        def entries(descriptor, path, remaining):
            """Perform real bounded enumeration then mutate its observed root membership once."""
            nonlocal changed
            result = original(descriptor, path, remaining)
            if not changed:
                changed = True
                (self.destination / "late").write_bytes(b"late")
            return result
        with patch.object(importing, "_entries", entries):
            self.reject(self.prepare)

    def test_inert_executable_python_configuration_and_notebook(self):
        """Executable permissions and content never authorize execution during preview or commit."""
        sentinel = self.parent / "EXECUTED"
        code = f"from pathlib import Path\nPath({str(sentinel)!r}).write_text('bad')\n"
        payloads = {"program.py": code.encode(), "settings.py": code.encode(),
                    "notebook.ipynb": json.dumps({"cells": [{"cell_type": "code", "source": code}]}).encode(),
                    "run.sh": f"#!/bin/sh\ntouch '{sentinel}'\n".encode()}
        for path, data in payloads.items():
            (self.destination / path).write_bytes(data)
            (self.destination / path).chmod(0o700 if path.endswith(".sh") else 0o644)
        prepared = self.prepare(metadata={**self.meta, "entry_file": "program.py"}, selected_paths=list(payloads))
        self.assertFalse(sentinel.exists())
        self.store.submit_typed(prepared.submission)
        self.assertFalse(sentinel.exists())
        for entry in decode_envelope(prepared.submission.records[0]).files:
            self.assertEqual(self.store.read_artifact(entry.artifact), payloads[entry.path])

    def test_two_prepared_drafts_cas_and_used_id(self):
        """Both independent drafts prepare at one base; only one append wins and neither is overwritten."""
        second = self.parent / "second"
        self.run_checkout(second)
        (self.destination / "copy.txt").write_bytes(b"author one")
        (second / "copy.txt").write_bytes(b"author two")
        first = self.prepare()
        other = self.prepare(second, submission_id="other")
        self.store.submit_typed(first.submission)
        self.reject(lambda: self.store.submit_typed(other.submission), RevisionConflictError)
        self.reject(lambda: self.prepare(second, submission_id="another"), RevisionConflictError)
        error = self.reject(self.prepare, SubmissionConflictError)
        self.assertIn("retry the saved proposal directly", str(error))
        self.assertEqual((self.destination / "copy.txt").read_bytes(), b"author one")
        self.assertEqual((second / "copy.txt").read_bytes(), b"author two")
        self.assertEqual(self.store.read_artifact(self.a), self.text)

    def test_proposal_codec_strict_nested_fields_and_coherence(self):
        """Proposal JSON is complete, deterministic and pure, with no permissive default reconstruction."""
        submission = self.prepare().submission
        encoded = dumps_prepared_submission(submission)
        self.assertEqual(loads_prepared_submission(encoded), submission)
        self.assertEqual(dumps_prepared_submission(loads_prepared_submission(encoded.encode())), encoded)
        doc = json.loads(encoded)
        variants = []
        for field, value in (("format", "other"), ("version", True), ("version", 2), ("extra", 1)):
            bad = deepcopy(doc)
            bad[field] = value
            variants.append(bad)
        for location, field in (((), "version"), (("submission",), "provenance"),
                                (("submission", "provenance"), "details"),
                                (("submission", "records", 0), "scientific_disposition"),
                                (("submission", "records", 0, "provenance"), "details"),
                                (("submission", "records", 0, "record_references", 0), "target_kind"),
                                (("submission", "records", 0, "content"), "task"),
                                (("submission", "records", 0, "content", "files", 0, "artifact"), "size")):
            bad = deepcopy(doc)
            item = bad
            for key in location:
                item = item[key]
            del item[field]
            variants.append(bad)
        bad = deepcopy(doc)
        bad["submission"]["expected_heads"]["bundle"] = True
        variants.append(bad)
        bad = deepcopy(doc)
        bad["submission"]["records"][0]["content"]["supersedes"] = None
        bad["submission"]["records"][0]["record_references"] = []
        variants.append(bad)
        bad = deepcopy(doc)
        bad["submission"]["records"][0]["content"]["title"] = "\ud800"
        variants.append(bad)
        for bad in variants:
            with self.subTest(bad=bad):
                with self.assertRaises(DomainValidationError):
                    loads_prepared_submission(json.dumps(bad))
        for raw in (None, {}, b"\xff", '{', encoded.replace('"version":1', '"version":1,"version":1', 1),
                    encoded.replace('"actor":"controller"', '"actor":"controller","actor":"other"', 1),
                    encoded.replace('"scope":"local engineering"', '"scope":NaN', 1)):
            with self.assertRaises(DomainValidationError):
                loads_prepared_submission(raw)
        with self.assertRaises(DomainValidationError):
            dumps_prepared_submission(request(records=[self.envelope]))
        # Serialization never rechecks storage/drafts, including after deletion.
        (self.root / "objects" / self.a.digest).unlink()
        self.assertEqual(loads_prepared_submission(encoded), submission)

    def test_typed_targets_forged_links_and_shallow_dependencies(self):
        """Preview uses the same constrained/shallow roles as admission without reading transitive bytes."""
        bad = record("generic-claim", kind="claim")
        shallow = record("generic-product", kind="work_product_manifest", content={"format": "unknown", "version": 99})
        self.store.submit(request("generic-targets", [bad, shallow]))
        for change in (
                {"linked_claims": [RecordReference("missing", 1, "linked_claim", "claim").to_dict()]},
                {"linked_claims": [RecordReference("generic-product", 1, "linked_claim", "claim").to_dict()]},
                {"linked_claims": [RecordReference("generic-claim", 1, "linked_claim", "claim").to_dict()]},
                {"context": RecordReference("generic-claim", 1, "context", "research_context").to_dict()}):
            self.reject(lambda: self.prepare(metadata={**self.meta, **change}), ReferenceResolutionError)
        dependency = RecordReference("generic-product", 1, "build_dependency", "work_product_manifest").to_dict()
        prepared = self.prepare(metadata={**self.meta, "build_dependencies": [dependency]})
        self.store.submit_typed(prepared.submission)
        with self.assertRaises(DomainValidationError):
            self.store.get_typed_revision("generic-product", 1)

    def test_canonical_base_constrained_history_is_checked(self):
        """A coherent generically stored base with an invalid claim target fails preview's typed closure."""
        self.store.submit(request("bad-claim", [record("bad", kind="claim")]))
        value = replace(manifest(self.a), linked_claims=[RecordReference("bad", 1, "linked_claim", "claim")])
        envelope = encode_envelope("bad-base", 1, value, CREATOR)
        self.store.submit(request("bad-base", [envelope]))
        destination = self.parent / "bad-base-draft"
        base = RecordReference("bad-base", 1, "checkout_base", "work_product_manifest")
        checkout_work_product(self.store, base, destination, **self.options)
        self.reject(lambda: prepare_work_product_import(self.store, base, destination, **{
            **self.import_options, "metadata": proposed_metadata(replace(value, linked_claims=[])),
            "selected_paths": ["notes/α.txt"]}), ReferenceResolutionError)

    def test_artifact_publication_failure_keeps_draft_and_metadata(self):
        """A damaged object is never repaired; failure preserves edited bytes and useful artifact causes."""
        (self.destination / "copy.txt").write_bytes(b"new damaged target")
        artifact = self.store.put_artifact(b"new damaged target")
        path = self.root / "objects" / artifact.digest
        self.rewrite(path, b"broken", 0o400)
        error = self.reject(self.prepare)
        self.assertIsNotNone(error.__cause__)
        self.assertEqual(path.read_bytes(), b"broken")
        self.assertEqual((self.destination / "copy.txt").read_bytes(), b"new damaged target")

    def test_saved_proposal_retries_after_draft_deletion_head_advance_and_damage(self):
        """Fresh processes reconcile original IDs before availability/CAS, with no duplicate metadata."""
        (self.destination / "copy.txt").write_bytes(b"new captured bytes")
        proposal = self.prepare().submission
        saved = self.parent / "proposal.json"
        saved.write_text(dumps_prepared_submission(proposal), encoding="ascii")
        program = '''
import json, sys
from pathlib import Path
from research_pipeline.store import RecordStore
from research_pipeline.work_product_import import loads_prepared_submission
with RecordStore.open(sys.argv[1]) as store:
    print(json.dumps(store.submit_typed(loads_prepared_submission(Path(sys.argv[2]).read_bytes())).to_dict()))
'''
        receipt = json.loads(self.child(program, self.root, saved))
        value = decode_envelope(proposal.records[0])
        third = replace(value, title="later head", supersedes=RecordReference("bundle", 2, "supersedes", "work_product_manifest"))
        self.store.submit_typed(request("third", [encode_envelope("bundle", 3, third, CREATOR)], {"bundle": 2}))
        (self.destination / "copy.txt").write_bytes(b"later draft edit")
        self.assertEqual(json.loads(self.child(program, self.root, saved)), receipt)
        import shutil
        shutil.rmtree(self.destination)
        before = metadata(self.root)
        new_artifact = next(entry.artifact for entry in value.files if entry.path == "copy.txt")
        for reference in (self.a, new_artifact):
            path = self.root / "objects" / reference.digest
            self.rewrite(path, b"damaged", 0o400)
            self.assertEqual(json.loads(self.child(program, self.root, saved)), receipt)
            path.unlink()
            self.assertEqual(json.loads(self.child(program, self.root, saved)), receipt)
        self.assertEqual(metadata(self.root), before)
        for variation in ("content", "provenance", "order", "submission-provenance"):
            changed = value
            provenance = proposal.records[0].provenance
            controller = proposal.provenance
            if variation == "content": changed = replace(value, title="different")
            elif variation == "order": changed = replace(value, files=value.files[::-1])
            elif variation == "provenance": provenance = CREATOR
            else: controller = EDITOR
            batch = Submission("import", controller, [encode_envelope("bundle", 2, changed, provenance)], {"bundle": 1})
            self.reject(lambda: self.store.submit_typed(batch), SubmissionConflictError)
        self.assertEqual(len(self.store.audit_events()), 3)
        self.assertEqual(len(before["submissions"]), 3)

    def test_real_process_interruptions_and_saved_id_reconciliation(self):
        """Real SQLite faults distinguish absent metadata/hot journals from post-COMMIT lost acknowledgment."""
        for boundary in ("before_metadata", "after_first_revision", "after_commit"):
            with self.subTest(boundary=boundary):
                root = self.parent / ("runtime-" + boundary)
                draft = self.parent / ("draft-" + boundary)
                with RecordStore.create(root) as source:
                    artifact = source.put_artifact(b"old")
                    value = replace(manifest(artifact), files=[WorkProductFile("file", artifact)], entry_file="file")
                    source.submit_typed(request("initial", [encode_envelope("product", 1, value, CREATOR)]))
                    base = RecordReference("product", 1, "checkout_base", "work_product_manifest")
                    checkout_work_product(source, base, draft, **self.options)
                    (draft / "file").write_bytes(b"retained edited bytes")
                    # Force real page spills before the after_first_revision exit.
                    proposed = {**proposed_metadata(value), "purpose": "large metadata " * 350000}
                    prepared = prepare_work_product_import(source, base, draft, **{
                        **self.import_options, "metadata": proposed, "selected_paths": ["file"],
                        "submission_id": boundary})
                    captured = prepared.submission.records[0].artifact_references[0]
                    before = metadata(root)
                saved = self.parent / (boundary + ".json")
                with saved.open("x", encoding="ascii") as stream:
                    stream.write(dumps_prepared_submission(prepared.submission))
                    stream.flush()
                    os.fsync(stream.fileno())
                self.child('''
import os, sys
from pathlib import Path
from research_pipeline import store as module
from research_pipeline.store import RecordStore
from research_pipeline.work_product_import import loads_prepared_submission
proposal = loads_prepared_submission(Path(sys.argv[2]).read_bytes())
def fault(boundary):
    """Exit at the selected real transaction boundary without Python cleanup."""
    if boundary == sys.argv[3]: os._exit(73)
module._fault = fault
with RecordStore.open(sys.argv[1]) as store:
    store.submit_typed(proposal)
raise AssertionError("fault not reached")
''', root, saved, boundary, expected=73)
                if boundary == "after_first_revision":
                    journal = root / "metadata.sqlite3-journal"
                    self.assertTrue(journal.exists())
                    self.assertGreater(journal.stat().st_size, 512)
                self.assertEqual((draft / "file").read_bytes(), b"retained edited bytes")
                self.assertTrue((root / "objects" / captured.digest).exists())
                self.child('''
import sys
from pathlib import Path
from research_pipeline.store import RecordStore
from research_pipeline.work_product_import import loads_prepared_submission
proposal = loads_prepared_submission(Path(sys.argv[2]).read_bytes())
committed = sys.argv[3] == "after_commit"
with RecordStore.open(sys.argv[1]) as store:
    old = store.get_submission(proposal.submission_id)
    assert (old is not None) == committed
    assert store.head("product") == (2 if committed else 1)
    assert len(store.audit_events()) == (2 if committed else 1)
    recovered = store.submit_typed(proposal)
    if committed: assert recovered == old
    assert store.submit_typed(proposal) == recovered
    assert len(store.audit_events()) == 2
''', root, saved, boundary)
                with RecordStore.open(root) as source:
                    self.assertEqual(source.get_typed_revision("product", 2)[0], prepared.submission.records[0])
                    self.assertEqual(source.read_artifact(captured), b"retained edited bytes")
                    self.assertEqual(source.read_artifact(artifact), b"old")
                    self.assertEqual(len(metadata(root)["submissions"]), len(before["submissions"]) + 1)

    def test_interrupted_checkout_cannot_prepare(self):
        """An actual prepublication process exit retains its incomplete draft and cannot import it."""
        destination = self.parent / "interrupted"
        self.child('''
import os, sys
from research_pipeline import checkout
from research_pipeline.domain import RecordReference
from research_pipeline.store import RecordStore
def fault(boundary):
    """Leave actual incomplete checkout files after prepublication interruption."""
    if boundary == "before_publication": os._exit(72)
checkout._fault = fault
with RecordStore.open(sys.argv[1]) as store:
    checkout.checkout_work_product(store, RecordReference("bundle", 1, "checkout_base", "work_product_manifest"),
        sys.argv[2], source_root=sys.argv[3], protected_roots=[], max_file_bytes=1024,
        max_total_bytes=4096, max_files=10, max_descriptor_bytes=100000)
''', self.root, destination, self.source_tree, expected=72)
        self.assertTrue((destination / ".work-product/incomplete").exists())
        self.reject(lambda: self.prepare(destination))
        self.assertEqual(self.store.read_artifact(self.a), self.text)

    def test_backup_restore_imported_history_generic_payloads_and_receipts(self):
        """Restart/exact restore preserves old/new bytes, links, provenance and malformed generic history."""
        (self.destination / "copy.txt").write_bytes(b"restorable revision")
        prepared = self.prepare()
        receipt = self.store.submit_typed(prepared.submission)
        generic = []
        for name, content in (("unsupported", {**self.value.to_dict(), "version": 99}), ("malformed", {"format": "research_pipeline.work_product_content"})):
            generic.append(record(name, kind="work_product_manifest", content=content))
        generic_request = request("generic", generic)
        generic_receipt = self.store.submit(generic_request)
        before = metadata(self.root)
        backup, restored_root = self.parent / "backup", self.parent / "restored"
        create_backup(self.store, backup)
        with restore_backup(backup, restored_root) as restored:
            self.assertEqual(metadata(restored_root), before)
            self.assertEqual(restored.get_revision("bundle", 1), self.envelope)
            self.assertEqual(restored.get_typed_revision("bundle", 2)[0], prepared.submission.records[0])
            self.assertEqual(restored.submit_typed(prepared.submission), receipt)
            self.assertEqual(restored.submit(generic_request), generic_receipt)
            for item in generic:
                self.assertEqual(restored.get_revision(item.record_id, 1), item)
                with self.assertRaises(DomainValidationError):
                    restored.get_typed_revision(item.record_id, 1)
            for entry in decode_envelope(prepared.submission.records[0]).files:
                expected = b"restorable revision" if entry.path == "copy.txt" else (self.destination / entry.path).read_bytes()
                self.assertEqual(restored.read_artifact(entry.artifact), expected)
            self.assertEqual(restored.read_artifact(self.a), self.text)
            self.assertEqual(metadata(restored_root), before)
        with RecordStore.open(restored_root) as restarted:
            self.assertEqual(restarted.submit_typed(prepared.submission), receipt)
            self.assertEqual(restarted.get_revision("bundle", 2).provenance, EDITOR)

    def test_bounded_reads_and_preallocation_size_rejection(self):
        """Selected reads consume exactly observed bytes plus one probe; oversize files are never read."""
        path = self.destination / "notes/α.txt"
        payload = bytes(range(256)) * 700
        path.write_bytes(payload)
        identity = (path.stat().st_dev, path.stat().st_ino)
        reads = []
        original_read = os.read
        def observe(fd, count):
            """Record actual selected-inode read sizes while preserving the real read operation."""
            info = os.fstat(fd)
            if (info.st_dev, info.st_ino) == identity:
                reads.append(count)
            return original_read(fd, count)
        with patch.object(importing.os, "read", observe):
            prepared = self.prepare(max_file_bytes=len(payload))
        self.assertEqual(reads, [importing._CHUNK, importing._CHUNK,
                                 len(payload) - 2 * importing._CHUNK, 1])
        reference = prepared.submission.records[0].artifact_references[0]
        self.assertEqual(self.store.read_artifact(reference), payload)
        reads.clear()
        with patch.object(importing.os, "read", observe):
            self.reject(lambda: self.prepare(max_file_bytes=len(payload) - 1))
        self.assertEqual(reads, [])

    def test_shallow_damaged_dependencies_and_ordered_metadata_differences(self):
        """Missing transitive bytes stay shallow while exact link order remains visible in previews."""
        attachment = self.store.put_artifact(b"unused dependency bytes")
        targets = [record(name, kind="work_product_manifest", content={"format": "unsupported"},
                          artifact_references=[attachment]) for name in ("dependency-a", "dependency-b")]
        self.store.submit(request("dependencies", targets))
        (self.root / "objects" / attachment.digest).unlink()
        refs = [RecordReference(item.record_id, 1, "build_dependency", item.kind).to_dict() for item in targets]
        first = self.prepare(metadata={**self.meta, "build_dependencies": refs})
        second = self.prepare(metadata={**self.meta, "build_dependencies": refs[::-1]})
        self.assertEqual(first.summary["metadata_changes"]["build_dependencies"], {"before": [], "after": refs})
        self.assertEqual(second.summary["metadata_changes"]["build_dependencies"]["after"], refs[::-1])
        self.store.submit_typed(first.submission)
        newer_base = RecordReference("bundle", 2, "checkout_base", "work_product_manifest")
        newer = self.parent / "newer"
        checkout_work_product(self.store, newer_base, newer, **self.options)
        proposal = prepare_work_product_import(self.store, newer_base, newer, **{
            **self.import_options, "expected_head": 2, "submission_id": "third",
            "metadata": {**self.meta, "build_dependencies": refs[::-1]}})
        self.assertEqual(proposal.summary["metadata_changes"]["build_dependencies"],
                         {"before": refs, "after": refs[::-1]})
        self.store.submit_typed(proposal.submission)
        self.assertFalse((self.root / "objects" / attachment.digest).exists())

    def test_inert_module_import(self):
        """Fresh import has no storage, process or network side effects under existing audit guards."""
        self.child('''
import sys
from pathlib import Path
before = sorted(str(path) for path in Path.cwd().rglob("*"))
def guard(event, args):
    """Reject observed writes, process launches and connections during module import."""
    if event == "open":
        mode, flags = args[1:3]
        if (isinstance(mode, str) and any(c in mode for c in "wax+")) or flags & (1 | 2 | 64 | 512 | 1024):
            raise AssertionError((event, args))
    if event in ("os.mkdir", "os.remove", "os.rename", "subprocess.Popen", "socket.connect"):
        raise AssertionError((event, args))
sys.addaudithook(guard)
import research_pipeline.work_product_import
assert sorted(str(path) for path in Path.cwd().rglob("*")) == before
''')

    def test_documented_round_trip_example(self):
        """Execute the exact Markdown block with candidate sources in a fresh bytecode-free interpreter."""
        document = (Path(__file__).resolve().parents[2] / "docs/work-product-import.md").read_text()
        section = document.split("## Runnable round-trip example\n", 1)[1]
        program = section.split("```python\n", 1)[1].split("```", 1)[0]
        self.child(program)
