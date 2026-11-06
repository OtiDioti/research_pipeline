"""Candidate-local subprocess evidence for bounded exact CLI inspection and checkout."""

from dataclasses import replace
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import unittest

from research_pipeline import checkout
from research_pipeline.cli_controls import source_root
from research_pipeline.cli_inspection import exact_record, exact_receipt
from research_pipeline.snapshot import SnapshotLimitError
from research_pipeline.domain import RecordReference
from research_pipeline.work_product import WorkProductFile, encode_envelope
from tests import test_checkout as checkout_tests
from tests.test_store import CREATOR, record, request

SRC = Path(__file__).resolve().parents[1] / "src"


class CliOperationTests(unittest.TestCase):
    """Use actual private stores and fresh working directories; faults are private test wrappers only."""

    def setUp(self):
        """Reuse the real multi-file checkout seed and add explicit private operating configuration."""
        checkout_tests.CheckoutTests.setUp(self)
        self.config = self.parent / "config.json"
        self.config_value = dict(format="research_pipeline.cli_config", version=1,
                                 store=str(self.root), protected_roots=[str(self.protected)])
        self.write_config(self.config_value)

    def write_config(self, value):
        """Write synthetic trusted configuration with the CLI's explicit ownership/mode contract."""
        self.config.write_text(json.dumps(value), encoding="utf-8")
        self.config.chmod(0o600)

    def arguments(self, command="inspect-record", **options):
        """Build explicit command arguments, preserving each caller's exact base and destination."""
        defaults = {"config": self.config}
        if command in ("inspect-record", "checkout-work-product"):
            defaults.update(record_id="bundle", revision=1)
        if command == "checkout-work-product":
            defaults["destination"] = self.destination
        if command == "inspect-receipt":
            defaults["submission_id"] = "submit"
        if command == "inspect-checkout":
            defaults = {"checkout": self.destination}
        defaults.update(options)
        return [command, *(item for name, value in defaults.items()
                           for item in ("--" + name.replace("_", "-"), str(value)))]

    def invoke(self, arguments=None, *, prelude=None, expected=0):
        """Execute the actual candidate module, optionally installing private faults before runpy entry."""
        arguments = self.arguments() if arguments is None else arguments
        if prelude is None:
            command = ["-m", "research_pipeline", *arguments]
        else:
            program = prelude + '\nimport runpy\nrunpy.run_module("research_pipeline", run_name="__main__")\n'
            command = ["-c", program, *arguments]
        result = subprocess.run([sys.executable, "-B", *command], cwd=self.parent,
                                env={**os.environ, "PYTHONPATH": str(SRC), "PYTHONDONTWRITEBYTECODE": "1"},
                                capture_output=True, timeout=40)
        self.assertEqual(result.returncode, expected, result.stderr.decode(errors="replace"))
        if expected == 0:
            self.assertEqual(result.stderr, b"")
        return result

    def diagnostic(self, result, code):
        """Require the exact inert diagnostic schema and no accidental machine success output."""
        self.assertEqual(result.stdout, b"")
        self.assertLessEqual(len(result.stderr), 65536)
        self.assertTrue(result.stderr.isascii())
        self.assertEqual(result.stderr.count(b"\n"), 1)
        value = json.loads(result.stderr)
        self.assertEqual(set(value), {"format", "version", "command", "code", "message", "context"})
        self.assertEqual(value["format"], "research_pipeline.cli_diagnostic")
        self.assertEqual(value["version"], 1)
        self.assertEqual(value["code"], code)
        self.assertEqual(set(value["context"]), {
            "store", "destination", "record_id", "revision", "submission_id", "next_action"})
        return value

    def snapshot(self):
        """Capture application tables and original object bytes separately from physical journal recovery."""
        return checkout_tests.CheckoutTests.snapshot(self)

    def advance(self):
        """Append a later canonical revision without changing the original historical attribution."""
        second = encode_envelope("bundle", 2, replace(self.value, title="Later title"), CREATOR)
        self.store.submit_typed(request("advance", [second], {"bundle": 1}))

    def test_exact_history_generic_and_original_receipt(self):
        """Historical lookup and original receipts preserve complete ordered domain values after later commits."""
        original = self.store.get_submission("submit").to_dict()
        self.advance()
        generic = record("generic")
        self.store.submit(request("generic_submit", [generic]))
        before = self.snapshot()
        result = self.invoke()
        value = json.loads(result.stdout)
        self.assertEqual(set(value), {"format", "version", "command", "status", "result"})
        self.assertEqual(value["format"], "research_pipeline.cli_result")
        self.assertEqual(value["status"], "ok")
        self.assertEqual(value["result"], dict(record_id="bundle", revision=1,
                         envelope=self.envelope.to_dict(), commit={key: original[key] for key in
                         ("submission_id", "committed_at", "fingerprint")}))
        self.assertEqual(result.stdout, (json.dumps(value, sort_keys=True, separators=(",", ":"),
                                                   ensure_ascii=True, allow_nan=False) + "\n").encode())
        receipt = json.loads(self.invoke(self.arguments("inspect-receipt")).stdout)
        self.assertEqual(receipt["result"]["receipt"], original)
        value = json.loads(self.invoke(self.arguments(record_id="generic")).stdout)
        self.assertEqual(value["result"]["envelope"], generic.to_dict())
        self.assertEqual(self.snapshot(), before)

    def test_metadata_never_reads_artifacts(self):
        """Both metadata commands work with deleted/damaged objects under an audited object-open guard."""
        (self.root / "objects" / self.a.digest).unlink()
        broken = self.root / "objects" / self.b.digest
        broken.chmod(0o600)
        broken.write_bytes(b"wrong")
        broken.chmod(0o400)
        guard = '''
import sys
from pathlib import Path
def guard(event, arguments):
    """Reject any file open of an object digest while permitting layout directory opens."""
    if event == "open" and isinstance(arguments[0], (str, bytes)):
        name = Path(str(arguments[0])).name
        if len(name) == 64 and all(c in "0123456789abcdef" for c in name):
            raise AssertionError("artifact read attempted")
sys.addaudithook(guard)
'''
        for command in ("inspect-record", "inspect-receipt"):
            self.invoke(self.arguments(command), prelude=guard)
        result = self.invoke(self.arguments("checkout-work-product"), expected=6)
        self.diagnostic(result, "integrity_error")
        self.assertTrue((self.destination / ".work-product/incomplete").is_file())

    def test_absence_is_exact_and_bounded(self):
        """Only absent exact revisions/submission IDs produce the documented null result shapes."""
        for arguments, expected in (
            (self.arguments(revision=2), dict(record_id="bundle", revision=2, envelope=None, commit=None)),
            (self.arguments("inspect-receipt", submission_id="unknown"), dict(submission_id="unknown", receipt=None)),
        ):
            result = self.invoke(arguments, expected=3)
            value = json.loads(result.stdout)
            self.assertEqual(value["status"], "absent")
            self.assertEqual(value["result"], expected)
            self.assertEqual(result.stderr, b"")
            self.diagnostic(self.invoke(arguments + ["--max-output-bytes", "1"], expected=5), "limit_exceeded")

    def test_missing_incomplete_and_inaccessible_store(self):
        """A missing runtime is not created; incomplete layouts and denied I/O remain distinct."""
        missing = self.parent / "missing"
        self.write_config({**self.config_value, "store": str(missing)})
        self.diagnostic(self.invoke(expected=3), "missing")
        self.assertFalse(missing.exists())
        missing.mkdir(mode=0o700)
        self.diagnostic(self.invoke(expected=5), "unsafe_layout")
        self.write_config(self.config_value)
        prelude = '''
import errno, os
real = os.stat
def denied(path, *args, **kwargs):
    """Inject actual EACCES at runtime traversal, before store access."""
    if str(path) == "runtime": raise PermissionError(errno.EACCES, "denied", path)
    return real(path, *args, **kwargs)
os.stat = denied
'''
        self.diagnostic(self.invoke(prelude=prelude, expected=6), "operational_error")
        self.diagnostic(self.invoke(prelude='''
import errno
from research_pipeline.store import RecordStore, StoreLayoutError
from research_pipeline.artifacts import ArtifactLayoutError
def denied(*args):
    """Preserve the same chained errno path as actual store layout translation."""
    try:
        try: raise PermissionError(errno.EACCES, "denied")
        except OSError as error: raise ArtifactLayoutError("layout") from error
    except ArtifactLayoutError as error: raise StoreLayoutError("layout") from error
RecordStore.open = denied
''', expected=6), "operational_error")

    def test_usage_errors_and_help_do_not_open_dependencies(self):
        """Real help/version and invalid invocations cannot read controls, open stores or create destinations."""
        guard = '''
from research_pipeline import cli
from research_pipeline.store import RecordStore
def forbidden(*args, **kwargs):
    """Fail if parsing performs dependent operations."""
    raise AssertionError("dependent operation")
cli.read_config = forbidden
RecordStore.open = forbidden
cli.checkout.checkout_work_product = forbidden
'''
        before = self.snapshot()
        for arguments in ([], ["--help"], ["--version"], ["checkout-work-product", "--help"]):
            self.invoke(arguments, prelude=guard)
        for arguments in (
            ["run"], ["--ver"], ["--unknown"], ["--he"], ["inspect-record"],
            self.arguments() + ["--revis", "1"], self.arguments() + ["--revision", "1"],
            self.arguments(revision="1.0"), self.arguments(revision="+1"),
            self.arguments() + ["--max-links", "1e3"],
            self.arguments() + ["--config", str(self.config)],
            ["run\x1b[31m\n" + "x" * 100000],
        ):
            result = self.invoke(arguments, prelude=guard, expected=2)
            self.assertEqual(result.stdout, b"")
            self.assertIn(b"usage:", result.stderr)
            self.assertNotIn(b"\x1b", result.stderr)
            self.assertLessEqual(len(result.stderr), 65536)
        self.assertFalse(self.destination.exists())
        self.assertEqual(self.snapshot(), before)

    def test_invalid_values_precede_control_reads(self):
        """Identifiers, path scalars and numeric ranges fail before opening even a missing config."""
        for options in (
            dict(record_id="../bad"), dict(revision=0), dict(revision=2**63),
            dict(revision="9" * 1000), dict(max_links=65537), dict(max_control_bytes=0),
            dict(config="../missing"), dict(config="x" * 4097),
        ):
            arguments = self.arguments(**options)
            result = self.invoke(arguments, expected=5)
            self.assertIn(json.loads(result.stderr)["code"], ("invalid_input", "limit_exceeded", "unsafe_layout"))
            self.assertEqual(result.stdout, b"")

    def test_strict_config_types_fields_and_json(self):
        """Controls reject coercions, extra/duplicate fields, malformed scalars and excessive nesting/size."""
        values = [
            {**self.config_value, "version": True}, {**self.config_value, "version": 1.0},
            {**self.config_value, "version": 2}, {**self.config_value, "source_root": "/tmp"},
            {**self.config_value, "permissions": {}}, {**self.config_value, "store": "relative"},
            {**self.config_value, "store": ""}, {**self.config_value, "store": None},
            {**self.config_value, "store": "/tmp/../runtime"},
            {**self.config_value, "store": "/tmp/\0runtime"},
            {**self.config_value, "store": "/tmp/\ud800"},
            {**self.config_value, "protected_roots": None},
            {**self.config_value, "protected_roots": ["/tmp//x", "/tmp/x/"]},
            {**self.config_value, "protected_roots": ["/" + str(i) for i in range(65)]},
            {key: value for key, value in self.config_value.items() if key != "protected_roots"},
        ]
        for value in values:
            self.write_config(value)
            self.invoke(expected=5)
        raw_values = [b'\xff', b'{"version":1,"version":1}', b'{"x":NaN}', b'{"x":1e999}',
                      b'{"x":' + b'9' * 129 + b'}', b'[' * 65 + b']' * 65,
                      b' ' * 65537, b'{"x":Infinity}']
        for data in raw_values:
            self.config.write_bytes(data)
            self.invoke(expected=5)
        self.write_config({**self.config_value, "protected_roots": []})
        self.invoke()

    def test_control_byte_boundaries_and_relative_normalization(self):
        """Exact control bytes and relative CLI paths work; config store paths remain absolute."""
        self.write_config({**self.config_value, "store": "//" + str(self.root).lstrip("/") + "//"})
        size = self.config.stat().st_size
        self.invoke(self.arguments(config="./config.json", max_control_bytes=size))
        self.diagnostic(self.invoke(self.arguments(max_control_bytes=size - 1), expected=5), "limit_exceeded")
        self.invoke(self.arguments("checkout-work-product", config="config.json", destination="draft"))
        result = self.invoke(self.arguments("inspect-checkout", checkout="./draft"))
        self.assertEqual(json.loads(result.stdout)["result"]["checkout"], str(self.destination))

    def test_unsafe_control_leaves_and_ancestors(self):
        """Links, FIFOs, sockets, directories and unsafe modes fail without consuming their contents."""
        original = self.config.read_bytes()
        for kind in ("symlink", "hardlink", "fifo", "socket", "directory", "mode"):
            self.config.unlink()
            other = self.parent / (kind + "-other")
            prelude = None
            if kind == "symlink":
                other.write_bytes(original)
                self.config.symlink_to(other)
            elif kind == "hardlink":
                other.write_bytes(original)
                other.chmod(0o600)
                os.link(other, self.config)
            elif kind == "fifo":
                os.mkfifo(self.config, 0o600)
            elif kind == "socket":
                self.config.write_bytes(original)
                self.config.chmod(0o600)
                prelude = '''
import os, socket
from research_pipeline import checkout
special = socket.socket(socket.AF_UNIX)
real = checkout._stat
def socket_stat(parent, name):
    """Supply genuine unbound socket metadata before the real regular-control gate, without binding a service."""
    return os.fstat(special.fileno()) if name == "config.json" else real(parent, name)
checkout._stat = socket_stat
'''
            elif kind == "directory":
                self.config.mkdir(mode=0o700)
            else:
                self.config.write_bytes(original)
                self.config.chmod(0o644)
            self.diagnostic(self.invoke(prelude=prelude, expected=5), "unsafe_layout")
            if kind == "directory":
                self.config.rmdir()
                self.config.touch()
            elif kind != "mode":
                self.config.unlink()
                self.config.touch()
        self.write_config(self.config_value)
        alias = self.parent / "alias"
        alias.symlink_to(self.parent, target_is_directory=True)
        self.diagnostic(self.invoke(self.arguments(config=alias / "config.json"), expected=5), "unsafe_layout")
        self.parent.chmod(0o755)
        try:
            self.diagnostic(self.invoke(expected=5), "unsafe_layout")
        finally:
            self.parent.chmod(0o700)

    def test_changed_control_reads(self):
        """Private seams expose equal-byte replacement, growth, truncation and parent rebinding before real checks."""
        for action in ("replace", "grow", "truncate", "parent"):
            with self.subTest(action=action):
                prelude = f'''
import os
from pathlib import Path
from research_pipeline import cli_controls
path = Path({str(self.config)!r})
action = {action!r}
def change(boundary):
    """Mutate a disposable control deterministically before the held-inode checks."""
    if boundary != "before_control_open": return
    if action == "replace":
        copy = path.with_name("replacement")
        copy.write_bytes(path.read_bytes()); copy.chmod(0o600); copy.replace(path)
    elif action == "grow":
        with path.open("ab") as stream: stream.write(b" ")
    elif action == "truncate": path.write_bytes(b"{{}}")
    else:
        moved = path.parent.with_name(path.parent.name + "-moved")
        path.parent.rename(moved)
        path.parent.mkdir(mode=0o700)
cli_controls._fault = change
'''
                self.diagnostic(self.invoke(prelude=prelude, expected=6), "integrity_error")
                if action == "parent":
                    moved = self.parent.with_name(self.parent.name + "-moved")
                    self.parent.rmdir()
                    moved.rename(self.parent)
                self.write_config(self.config_value)

    def test_overlap_and_recognizable_layouts(self):
        """Containment works in both directions; source protection and fixed control sentinels cannot be overridden."""
        before = self.snapshot()
        for destination in (source_root(), source_root() / "draft", source_root().parent,
                            self.root, self.root / "draft", self.root.parent,
                            self.protected, self.protected / "draft", self.config):
            self.diagnostic(self.invoke(self.arguments("checkout-work-product", destination=destination),
                                        expected=5), "unsafe_layout")
        for runtime in (source_root(), source_root().parent, source_root() / "runtime", self.protected):
            self.write_config({**self.config_value, "store": str(runtime)})
            self.diagnostic(self.invoke(expected=5), "unsafe_layout")
        self.write_config(self.config_value)
        for sentinel in ("manifest.json", "intent.json", "ready.json", "published.json", "refresh.json",
                         ".backup-incomplete", ".restore-incomplete", ".work-product"):
            marker = self.parent / sentinel
            marker.symlink_to("nonexistent")
            self.diagnostic(self.invoke(self.arguments("checkout-work-product"), expected=5), "unsafe_layout")
            marker.unlink()
        self.assertEqual(self.snapshot(), before)
        self.assertFalse(self.destination.exists())

    def test_checkout_historical_independence_and_offline_edits(self):
        """Historical text/binary/empty/repeated copies are independent and edits preserve original descriptor inspection."""
        self.advance()
        before = self.snapshot()
        value = json.loads(self.invoke(self.arguments("checkout-work-product")).stdout)["result"]
        self.assertEqual(value, dict(destination=str(self.destination), base=self.base.to_dict(),
                                    descriptor=".work-product/checkout.json"))
        identities = set()
        for entry in self.value.files:
            path = self.destination / entry.path
            info = path.stat()
            self.assertEqual(path.read_bytes(), self.store.read_artifact(entry.artifact))
            self.assertEqual(stat.S_IMODE(info.st_mode), 0o600)
            self.assertEqual(info.st_nlink, 1)
            self.assertNotEqual(info.st_ino, (self.root / "objects" / entry.artifact.digest).stat().st_ino)
            identities.add(info.st_ino)
        self.assertEqual(len(identities), len(self.value.files))
        (self.destination / "copy.txt").write_text("edited")
        (self.destination / "empty").unlink()
        self.config.unlink()
        observed = json.loads(self.invoke(self.arguments("inspect-checkout")).stdout)["result"]
        self.assertEqual(observed, dict(checkout=str(self.destination), base=self.base.to_dict(),
                         envelope=self.envelope.to_dict(), observation="published_descriptor",
                         historical_durability="unknown"))
        self.assertEqual(self.snapshot(), before)

    def test_checkout_limits_and_predictable_output(self):
        """Each checkout bound is enforced before destination reservation, including encoded output LF."""
        info = checkout.CheckoutInfo(self.base, self.envelope)
        for options in (dict(max_files=3), dict(max_file_bytes=1), dict(max_total_bytes=1),
                        dict(max_descriptor_bytes=len(checkout._encode(info)) - 1),
                        dict(max_output_bytes=1), dict(max_links=len(self.envelope.artifact_references) - 1)):
            self.diagnostic(self.invoke(self.arguments("checkout-work-product", **options), expected=5), "limit_exceeded")
            self.assertFalse(self.destination.exists())
        options = dict(max_files=len(self.value.files), max_file_bytes=max(e.artifact.size for e in self.value.files),
                       max_total_bytes=sum(e.artifact.size for e in self.value.files),
                       max_descriptor_bytes=len(checkout._encode(info)))
        self.invoke(self.arguments("checkout-work-product", **options))
        data = self.invoke().stdout
        self.assertEqual(self.invoke(self.arguments(max_output_bytes=len(data))).stdout, data)
        self.diagnostic(self.invoke(self.arguments(max_output_bytes=len(data) - 1), expected=5), "limit_exceeded")

    def test_collisions_and_exclusive_creation_race(self):
        """Existing files, directories, dangling links and exclusive-mkdir races remain retained conflicts."""
        for kind in ("file", "directory", "symlink", "race"):
            if kind == "file": self.destination.write_bytes(b"retained")
            elif kind == "directory": self.destination.mkdir(mode=0o700)
            elif kind == "symlink": self.destination.symlink_to("missing")
            prelude = None
            if kind == "race":
                prelude = '''
from pathlib import Path
from research_pipeline import checkout
real = checkout.checkout_work_product
def collide(source, base, destination, **kwargs):
    """Reserve the target immediately before the real exclusive creation attempt."""
    Path(destination).mkdir(mode=0o700)
    return real(source, base, destination, **kwargs)
checkout.checkout_work_product = collide
'''
            self.diagnostic(self.invoke(self.arguments("checkout-work-product"), prelude=prelude, expected=4), "conflict")
            if self.destination.is_dir(): self.destination.rmdir()
            else: self.destination.unlink()

    def test_receipt_membership_and_metadata_boundaries(self):
        """Record and receipt preflights enforce inclusive byte/count boundaries with actual reconstruction."""
        self.store.submit(request("pair", [record("one"), record("two")]))
        self.invoke(self.arguments("inspect-receipt", submission_id="pair", max_receipt_records=2))
        self.diagnostic(self.invoke(self.arguments("inspect-receipt", submission_id="pair", max_receipt_records=1),
                                    expected=5), "limit_exceeded")
        for command, operation in (
            ("inspect-record", lambda maximum: exact_record(self.store, "bundle", 1, maximum, 4096)),
            ("inspect-receipt", lambda maximum: exact_receipt(self.store, "submit", maximum, 1024)),
        ):
            low, high = 1, 2**21
            while low < high:
                middle = (low + high) // 2
                try:
                    operation(middle)
                    high = middle
                except SnapshotLimitError:
                    low = middle + 1
            self.invoke(self.arguments(command, max_metadata_bytes=low))
            self.diagnostic(self.invoke(self.arguments(command, max_metadata_bytes=low - 1), expected=5), "limit_exceeded")

    def test_corrupt_canonical_metadata_is_not_absence(self):
        """Canonical JSON/provenance, incomplete joins and membership ordinals fail integrity checks."""
        connection = self.store._connection
        original = connection.execute("SELECT provenance_json FROM audit_events WHERE submission_id='submit'").fetchone()[0]
        for text in ('{"actor":"author","created_at":"2026-10-30T10:00:00.000000Z"}',
                     '{"actor":"x","actor":"y"}', '[' * 65 + ']' * 65, ' {"x":1}', '{"x":1e999}'):
            connection.execute("UPDATE audit_events SET provenance_json=? WHERE submission_id='submit'", (text,))
            self.diagnostic(self.invoke(self.arguments("inspect-receipt"), expected=6), "integrity_error")
        connection.execute("UPDATE audit_events SET provenance_json=? WHERE submission_id='submit'", (original,))
        connection.execute("UPDATE revisions SET ordinal=4 WHERE record_id='bundle'")
        self.diagnostic(self.invoke(self.arguments("inspect-receipt"), expected=6), "integrity_error")
        connection.execute("UPDATE revisions SET ordinal=0 WHERE record_id='bundle'")
        connection.execute("DELETE FROM audit_events WHERE submission_id='submit'")
        for command in ("inspect-record", "inspect-receipt"):
            self.diagnostic(self.invoke(self.arguments(command), expected=6), "integrity_error")

    def test_strict_offline_descriptor_and_control_inventory(self):
        """Offline observation rejects incomplete/extra controls, malformed nested provenance and excessive descriptors."""
        self.invoke(self.arguments("checkout-work-product"))
        descriptor = self.destination / ".work-product/checkout.json"
        original = descriptor.read_bytes()
        for data in (b'[' * 65 + b']' * 65, b'{"x":NaN}', b'\xff', b'{"x":' + b'9' * 129 + b'}'):
            descriptor.chmod(0o600)
            descriptor.write_bytes(data)
            descriptor.chmod(0o400)
            self.diagnostic(self.invoke(self.arguments("inspect-checkout"), expected=5), "invalid_input")
        value = json.loads(original)
        del value["envelope"]["provenance"]["details"]
        descriptor.chmod(0o600)
        descriptor.write_text(json.dumps(value))
        descriptor.chmod(0o400)
        self.diagnostic(self.invoke(self.arguments("inspect-checkout"), expected=5), "invalid_input")
        descriptor.chmod(0o600)
        descriptor.write_bytes(original)
        descriptor.chmod(0o400)
        self.invoke(self.arguments("inspect-checkout", max_descriptor_bytes=len(original)))
        self.diagnostic(self.invoke(self.arguments("inspect-checkout", max_descriptor_bytes=len(original) - 1),
                                    expected=5), "limit_exceeded")
        for name in ("incomplete", "extra"):
            marker = descriptor.parent / name
            marker.symlink_to("missing")
            self.diagnostic(self.invoke(self.arguments("inspect-checkout"), expected=5), "unsafe_layout")
            marker.unlink()
        descriptor.unlink()
        os.mkfifo(descriptor, 0o400)
        self.diagnostic(self.invoke(self.arguments("inspect-checkout"), expected=5), "unsafe_layout")

    def test_publication_failure_and_abrupt_termination(self):
        """Pre/post-publication failures retain evidence; abrupt exits never imply historical synchronization."""
        before = self.snapshot()
        for index, (boundary, abrupt) in enumerate((
            ("after_marker", False), ("before_publication", False), ("after_publication", False),
            ("before_publication", True), ("after_publication", True),
        )):
            destination = self.parent / ("attempt" + str(index))
            prelude = f'''
import os
from research_pipeline import checkout
def fault(point):
    """Fail after a deterministic real publication boundary without cleanup or rollback."""
    if point == {boundary!r}:
        if {abrupt!r}: os._exit(73)
        raise OSError("injected synchronization failure")
checkout._fault = fault
'''
            result = self.invoke(self.arguments("checkout-work-product", destination=destination),
                                 prelude=prelude, expected=73 if abrupt else 7)
            if not abrupt:
                value = self.diagnostic(result, "effects_uncertain")
                self.assertEqual(value["context"]["destination"], str(destination))
                self.assertIn("inspect-checkout", value["context"]["next_action"])
            marker = destination / ".work-product/incomplete"
            self.assertEqual(marker.exists(), boundary != "after_publication")
            observed = self.invoke(self.arguments("inspect-checkout", checkout=destination),
                                   expected=0 if boundary == "after_publication" else 5)
            if boundary == "after_publication":
                self.assertEqual(json.loads(observed.stdout)["result"]["historical_durability"], "unknown")
        self.assertEqual(self.snapshot(), before)

    def test_output_short_zero_broken_flush_and_close(self):
        """Short writes drain fully; zero/protocol/write/flush/close failures disavow acknowledgment without retries."""
        for command in ("inspect-record", "checkout-work-product"):
            for index, fault in enumerate(("short", "zero", "broken", "flush", "close", "exhaustion")):
                destination = self.parent / (command + str(index))
                options = dict(destination=destination) if command == "checkout-work-product" else {}
                prelude = f'''
import os, sys
original = sys.stdout
real_open = os.open
def opened(path, *args, **kwargs):
    """Exercise failed-output cleanup even when opening its null sink exhausts descriptors."""
    if {fault!r} == "exhaustion" and path == os.devnull: raise OSError("descriptor exhaustion")
    return real_open(path, *args, **kwargs)
os.open = opened
class Output:
    """Expose deterministic byte-write/flush/close failures around the real output stream."""
    buffer = property(lambda self: self)
    def fileno(self):
        """Retain a real descriptor so failed buffered output can be redirected safely."""
        return original.fileno()
    def write(self, data):
        """Exercise short, zero and broken writes before real complete acknowledgment."""
        if {fault!r} in ("zero", "exhaustion"): return 0
        if {fault!r} == "broken": raise BrokenPipeError("closed reader")
        return original.buffer.write(data[:3] if {fault!r} == "short" else data)
    def flush(self):
        """Permit successful writes but fail the requested acknowledgment barrier."""
        if {fault!r} == "flush": raise OSError("flush failed")
        original.flush()
    def close(self):
        """Fail close after bytes were delivered when selected."""
        if {fault!r} == "close": raise OSError("close failed")
        original.close()
sys.stdout = Output()
'''
                status = 0 if fault == "short" else (7 if options else 6)
                result = self.invoke(self.arguments(command, **options), prelude=prelude, expected=status)
                if fault == "short":
                    self.assertEqual(json.loads(result.stdout)["status"], "ok")
                else:
                    diagnostic = json.loads(result.stderr)
                    self.assertEqual(diagnostic["code"], "output_failed")
                    self.assertIn("no complete acknowledgment", diagnostic["message"])
                    self.assertNotIn(b"Traceback", result.stderr)
                    self.assertIn("inspect-checkout" if options else "Repeat", diagnostic["context"]["next_action"])
                    if options:
                        self.invoke(self.arguments("inspect-checkout", checkout=destination))

    def test_documented_cli_example(self):
        """Execute the complete synthetic guide block verbatim using fresh candidate-local CLI subprocesses."""
        document = Path(__file__).resolve().parents[2] / "docs/local-cli.md"
        program = document.read_text(encoding="utf-8").split("```python\n", 1)[1].split("```", 1)[0]
        result = subprocess.run([sys.executable, "-B", "-c", program], cwd=self.parent,
                                env={**os.environ, "PYTHONPATH": str(SRC), "PYTHONDONTWRITEBYTECODE": "1"},
                                capture_output=True, timeout=45)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, b"")
        self.assertEqual(result.stderr, b"")

    def test_stream_changes_and_descriptor_close_errors(self):
        """Growth/truncation during real reads and failures closing checked descriptors cannot acknowledge success."""
        for action in ("grow", "truncate", "replace", "close"):
            self.write_config(self.config_value)
            prelude = f'''
import os
from pathlib import Path
from research_pipeline import cli_controls
path = Path({str(self.config)!r})
identity = path.stat().st_ino
real_read, real_close = os.read, os.close
fired = False
def read(fd, count):
    """Change bytes after a real bounded read, before EOF and signature checks."""
    global fired
    data = real_read(fd, count)
    if not fired and os.fstat(fd).st_ino == identity:
        fired = True
        if {action!r} == "grow":
            with path.open("ab") as stream: stream.write(b" ")
        elif {action!r} == "truncate": path.write_bytes(b"{{}}")
        elif {action!r} == "replace":
            other = path.with_name("replacement")
            other.write_bytes(path.read_bytes()); other.chmod(0o600); other.replace(path)
    return data
def close(fd):
    """Report a descriptor close error only after actually closing the checked control."""
    inode = os.fstat(fd).st_ino
    real_close(fd)
    if inode == identity and {action!r} == "close": raise OSError("close failure")
os.read, os.close = read, close
'''
            result = self.invoke(prelude=prelude, expected=6)
            self.diagnostic(result, "operational_error" if action == "close" else "integrity_error")
        self.write_config(self.config_value)
        self.invoke(self.arguments("checkout-work-product"))
        descriptor = self.destination / ".work-product/checkout.json"
        prelude = f'''
import os
identity = os.stat({str(descriptor)!r}).st_ino
real = os.close
def close(fd):
    """Fail after closing the original local descriptor, preventing read-only acknowledgment."""
    inode = os.fstat(fd).st_ino
    real(fd)
    if inode == identity: raise OSError("descriptor close failure")
os.close = close
'''
        self.diagnostic(self.invoke(self.arguments("inspect-checkout"), prelude=prelude, expected=6), "operational_error")
        self.invoke(self.arguments("inspect-checkout"))

    def test_post_checkout_resource_failure_and_interrupt(self):
        """Store-close and interruption after checkout starts preserve exact recovery identities and uncertain status."""
        for index, prelude in enumerate(('''
from research_pipeline.store import RecordStore
real = RecordStore.close
def close(self):
    """Fail after real connection closure, after the checkout publication call returned."""
    real(self)
    raise OSError("store close failure")
RecordStore.close = close
''', '''
from research_pipeline import checkout
def interrupt(point):
    """Interrupt at a deterministic post-marker boundary with retained evidence."""
    if point == "after_marker": raise KeyboardInterrupt()
checkout._fault = interrupt
''')):
            destination = self.parent / ("resource-failure" + str(index))
            result = self.invoke(self.arguments("checkout-work-product", destination=destination),
                                 prelude=prelude, expected=7)
            diagnostic = self.diagnostic(result, "effects_uncertain")
            self.assertEqual(diagnostic["context"]["destination"], str(destination))
            self.invoke(self.arguments("inspect-checkout", checkout=destination), expected=0 if index == 0 else 5)

    def test_real_broken_pipe_and_partial_output(self):
        """A physically closed reader and delivered partial JSON both return failure without shutdown retries."""
        process = subprocess.Popen([sys.executable, "-B", "-m", "research_pipeline", *self.arguments()],
                                   cwd=self.parent, env={**os.environ, "PYTHONPATH": str(SRC),
                                                        "PYTHONDONTWRITEBYTECODE": "1"},
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        process.stdout.close()
        diagnostic = process.stderr.read()
        process.stderr.close()
        self.assertEqual(process.wait(timeout=30), 6, diagnostic)
        self.assertEqual(json.loads(diagnostic)["code"], "output_failed")
        prelude = '''
import os, sys
original = sys.stdout
class Partial:
    """Physically deliver one prefix then fail, retaining the original descriptor for silencing."""
    buffer = property(lambda self: self)
    wrote = False
    def fileno(self):
        """Expose the real output channel to the normal failed-buffer cleanup."""
        return original.fileno()
    def write(self, data):
        """Write an incomplete JSON prefix directly before raising on the next write."""
        if self.wrote: raise BrokenPipeError("lost reader")
        self.wrote = True
        return os.write(self.fileno(), data[:17])
    def flush(self):
        """Delegate flush when called by cleanup."""
        original.flush()
    def close(self):
        """Close the original output stream without publishing another document."""
        original.close()
sys.stdout = Partial()
'''
        result = self.invoke(prelude=prelude, expected=6)
        self.assertEqual(len(result.stdout), 17)
        with self.assertRaises(json.JSONDecodeError):
            json.loads(result.stdout)
        self.assertEqual(json.loads(result.stderr)["code"], "output_failed")

    def test_hot_journal_opening_uses_existing_recovery(self):
        """CLI metadata opening recovers an actual hot rollback journal without admitting interrupted records."""
        before = self.snapshot()
        program = '''
import os, sys
from research_pipeline import store as module
from research_pipeline.domain import RecordEnvelope, CreationProvenance, Submission
provenance = CreationProvenance("author", "2026-10-30T12:00:00Z", {})
with module.RecordStore.open(sys.argv[1]) as store:
    envelope = RecordEnvelope("interrupted", 1, "research_context", {"large": "x" * 3000000}, provenance)
    def crash(point):
        """Terminate only after real first-revision writes have forced page spill."""
        if point == "after_first_revision": os._exit(73)
    module._fault = crash
    store.submit(Submission("interrupted", provenance, [envelope], {"interrupted": 0}))
raise AssertionError("crash seam not reached")
'''
        result = subprocess.run([sys.executable, "-B", "-c", program, str(self.root)], cwd=self.parent,
                                env={**os.environ, "PYTHONPATH": str(SRC), "PYTHONDONTWRITEBYTECODE": "1"},
                                capture_output=True, timeout=40)
        self.assertEqual(result.returncode, 73, result.stderr)
        journal = self.root / "metadata.sqlite3-journal"
        self.assertGreater(journal.stat().st_size, 512)
        value = json.loads(self.invoke().stdout)
        self.assertEqual(value["result"]["envelope"], self.envelope.to_dict())
        self.assertFalse(journal.exists())
        self.assertEqual(self.snapshot(), before)
        self.invoke(self.arguments("inspect-receipt", submission_id="interrupted"), expected=3)

    def test_fixed_ancestor_probes_and_bounded_inventory(self):
        """Ancestor guards never list arbitrary directories; exact inventories stop after one excess entry."""
        prelude = '''
import os
def forbidden(*args, **kwargs):
    """Reject unbounded listdir in this operation, including all ancestor checks."""
    raise AssertionError("unbounded directory enumeration")
os.listdir = forbidden
'''
        self.invoke(self.arguments("checkout-work-product"), prelude=prelude)
        control = self.destination / ".work-product"
        for index in range(20):
            (control / ("extra" + str(index))).touch(mode=0o400)
        prelude += '''
real = os.scandir
class Entries:
    """Limit actual enumeration steps so rejection must occur after one excess control entry."""
    def __init__(self, fd):
        """Retain the real scanner and count consumed entries."""
        self.entries, self.count = real(fd), 0
    def __enter__(self):
        """Return the bounded iterator to the existing exact-inventory loop."""
        return self
    def __exit__(self, *args):
        """Close the real directory iterator on early refusal."""
        self.entries.close()
    def __iter__(self):
        """Expose this counter as the iterator."""
        return self
    def __next__(self):
        """Fail if inspection consumes more than expected count plus one."""
        self.count += 1
        if self.count > 2: raise AssertionError("unbounded inventory")
        return next(self.entries)
os.scandir = Entries
'''
        self.diagnostic(self.invoke(self.arguments("inspect-checkout"), prelude=prelude, expected=5), "unsafe_layout")

    def test_descriptor_symlink_hardlink_and_replacement(self):
        """Original local controls reject linked leaves and equal-byte replacement before acknowledgment."""
        self.invoke(self.arguments("checkout-work-product"))
        descriptor = self.destination / ".work-product/checkout.json"
        original = descriptor.read_bytes()
        other = self.parent / "other-descriptor"
        other.write_bytes(original)
        other.chmod(0o400)
        for kind in ("symlink", "hardlink"):
            descriptor.unlink()
            if kind == "symlink": descriptor.symlink_to(other)
            else: os.link(other, descriptor)
            self.diagnostic(self.invoke(self.arguments("inspect-checkout"), expected=5), "unsafe_layout")
        descriptor.unlink()
        descriptor.write_bytes(original)
        descriptor.chmod(0o400)
        prelude = f'''
from pathlib import Path
from research_pipeline import cli_controls
path = Path({str(descriptor)!r})
def replace(point):
    """Replace equal descriptor bytes after reading but before the held leaf's final binding check."""
    if point == "after_control_read":
        other = path.with_name("replacement")
        other.write_bytes(path.read_bytes()); other.chmod(0o400); other.replace(path)
cli_controls._fault = replace
'''
        self.diagnostic(self.invoke(self.arguments("inspect-checkout"), prelude=prelude, expected=6), "integrity_error")

    def test_inert_scripts_and_unavailable_build_dependencies(self):
        """CLI checkout copies inert script/notebook/config bytes without executing or reading build dependencies."""
        sentinel = self.parent / "executed"
        script = f"from pathlib import Path; Path({str(sentinel)!r}).write_text('executed')"
        payloads = {"run.py": script.encode(), "settings.py": script.encode(),
                    "notebook.ipynb": json.dumps({"cells": [{"source": script}]}).encode()}
        dependency = self.store.put_artifact(b"unavailable dependency")
        self.store.submit(request("dependency", [record("dependency", kind="source", artifact_references=[dependency])]))
        manifest = replace(self.value, files=[WorkProductFile(path, self.store.put_artifact(data))
                                              for path, data in payloads.items()], entry_file="run.py",
                           build_dependencies=[RecordReference("dependency", 1, "build_dependency", "source")])
        self.store.submit_typed(request("scripts", [encode_envelope("scripts", 1, manifest, CREATOR)]))
        (self.root / "objects" / dependency.digest).unlink()
        before = self.snapshot()
        self.invoke(self.arguments("checkout-work-product", record_id="scripts"))
        self.assertEqual({path: (self.destination / path).read_bytes() for path in payloads}, payloads)
        self.assertFalse(sentinel.exists())
        self.assertEqual(self.snapshot(), before)

    def test_empty_files_and_zero_budgets(self):
        """A genuine empty bundle succeeds with zero per-file/total bytes and exact logical counts."""
        manifest = replace(self.value, files=[WorkProductFile("empty", self.empty)], entry_file="empty")
        self.store.submit_typed(request("empty", [encode_envelope("empty", 1, manifest, CREATOR)]))
        self.invoke(self.arguments("checkout-work-product", record_id="empty", max_file_bytes=0,
                                   max_total_bytes=0, max_files=1))
        self.assertEqual((self.destination / "empty").read_bytes(), b"")
        self.assertEqual(stat.S_IMODE((self.destination / "empty").stat().st_mode), 0o600)

    def test_source_layout_failure_and_unsafe_destination_parent(self):
        """Unknown executing layout fails closed, and a shared destination parent never reserves a draft."""
        prelude = f'''
from research_pipeline import cli_controls
cli_controls.__file__ = {str(self.config)!r}
'''
        self.diagnostic(self.invoke(prelude=prelude, expected=5), "unsafe_layout")
        shared = self.parent / "shared"
        shared.mkdir(mode=0o755)
        self.diagnostic(self.invoke(self.arguments("checkout-work-product", destination=shared / "draft"), expected=5),
                        "unsafe_layout")
        self.assertFalse((shared / "draft").exists())
        alias = self.parent / "alias"
        alias.symlink_to(shared)
        self.diagnostic(self.invoke(self.arguments("checkout-work-product", destination=alias / "draft"), expected=5),
                        "unsafe_layout")

    def test_corrupt_receipt_orphan_membership(self):
        """An orphan original ID or missing member identity is corruption rather than absent receipt."""
        connection = self.store._connection
        connection.execute("PRAGMA foreign_keys=OFF")
        original = connection.execute("SELECT * FROM submissions WHERE submission_id='submit'").fetchone()
        connection.execute("DELETE FROM submissions WHERE submission_id='submit'")
        self.diagnostic(self.invoke(self.arguments("inspect-receipt"), expected=6), "integrity_error")
        connection.execute("INSERT INTO submissions VALUES(?,?,?)", original)
        connection.execute("DELETE FROM identities WHERE record_id='bundle'")
        self.diagnostic(self.invoke(self.arguments("inspect-receipt"), expected=6), "integrity_error")

    def test_escaped_diagnostic_preserves_recovery_destination(self):
        """Control/non-ASCII path text stays inert while recovery context retains the exact destination."""
        destination = self.parent / "draft-\x1b[31m\nα"
        prelude = '''
from research_pipeline import checkout
def fail(point):
    """Retain a real incomplete checkout whose path requires diagnostic escaping."""
    if point == "after_marker": raise OSError("publication failed")
checkout._fault = fail
'''
        result = self.invoke(self.arguments("checkout-work-product", destination=destination),
                             prelude=prelude, expected=7)
        diagnostic = self.diagnostic(result, "effects_uncertain")
        self.assertEqual(diagnostic["context"]["destination"], str(destination))
        self.assertNotIn(b"\x1b", result.stderr)

    def test_help_version_output_failure_has_documented_status(self):
        """Witness complete buffered help/version drains after redirection, with status 6 and no output."""
        for index, arguments in enumerate(([], ["--help"], ["--version"], ["inspect-record", "--help"])):
            normal = self.invoke(arguments).stdout
            witness = self.parent / f"help-output-{index}.bin"
            prelude = f'''
import io
import sys
from pathlib import Path
original = sys.stdout
class Output:
    """Buffer complete text independently of stdout capacity, then fail its acknowledgment."""
    def __init__(self):
        """Hold all emitted bytes until cleanup tests recipient redirection by draining them."""
        self.buffer = io.BytesIO()
    def fileno(self):
        """Expose the recipient descriptor for failed-buffer redirection."""
        return original.fileno()
    def flush(self):
        """Inject failure after the complete help/version document enters the private buffer."""
        raise OSError("help flush failed")
    def close(self):
        """Drain to the real stream, close it, then witness bytes; redirection must precede this."""
        pending = self.buffer.getvalue()
        original.buffer.write(pending)
        original.close()
        Path({str(witness)!r}).write_bytes(pending)
sys.stdout = Output()
'''
            result = self.invoke(arguments, prelude=prelude, expected=6)
            self.diagnostic(result, "output_failed")
            payload = witness.read_bytes()
            self.assertTrue(payload)
            self.assertEqual(payload, normal)
