"""Strict complete authored controls, independent numeric ceilings and bounded diagnostic encoding."""

from dataclasses import asdict
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from research_pipeline import checkout, cli, cli_controls, cli_views
from research_pipeline.cli_controls import CliError, read_readable_limits, read_selection, strict_json
from research_pipeline.domain import DomainValidationError
from research_pipeline.snapshot import SnapshotLimitError
from tests.snapshot_fixtures import limits
from tests.view_refresh_fixtures import refresh_limits


class ReadableControlTests(unittest.TestCase):
    """Exercise every independently decoded field without needing a live store or publication."""

    def setUp(self):
        """Allocate private controls under the selected test temporary root."""
        temporary = TemporaryDirectory(prefix="readable-controls-")
        self.addCleanup(temporary.cleanup)
        self.parent = Path(temporary.name)
        self.path = self.parent / "limits.json"

    def save(self, value):
        """Replace the synthetic owned leaf with complete private UTF-8 JSON."""
        self.path.write_text(json.dumps(value), encoding="utf-8")
        self.path.chmod(0o600)

    def value(self):
        """Return all independent refresh groups, without relying on defaults or inherited limits."""
        return dict(format="research_pipeline.cli_readable_limits", version=1, command="refresh-readable-view",
                    snapshot_limits=limits().to_dict(), refresh_limits=asdict(refresh_limits()))

    def decode(self, value):
        """Decode a freshly written real control through guarded stable file reads."""
        self.save(value)
        return read_readable_limits(self.path, 65536, "refresh-readable-view")

    def test_every_limit_occurrence_exact_ceiling_and_one_over(self):
        """Every scalar in every nested family admits its ceiling and rejects one-over independently."""
        groups = (("snapshot_limits",), ("refresh_limits",), ("refresh_limits", "capture_limits"),
                  ("refresh_limits", "capture_limits", "plan_limits"), ("refresh_limits", "successor_limits"))
        for group in groups:
            for name, ceiling in cli_controls._READABLE_CEILINGS.items():
                value = self.value()
                target = value
                for key in group:
                    target = target[key]
                if name not in target:
                    continue
                with self.subTest(group=group, name=name):
                    target[name] = ceiling
                    self.decode(value)
                    target[name] = ceiling + 1
                    with self.assertRaises(SnapshotLimitError):
                        self.decode(value)
                    for invalid in (True, 1.0, "1", None):
                        target[name] = invalid
                        with self.assertRaises(DomainValidationError):
                            self.decode(value)
                    target.pop(name)
                    with self.assertRaises(DomainValidationError):
                        self.decode(value)

    def test_minima_and_no_nested_defaults(self):
        """Snapshot and capture/refresh zero exceptions remain distinct, with complete required groups."""
        for group in (("snapshot_limits",), ("refresh_limits",), ("refresh_limits", "capture_limits")):
            original = self.value()
            target = original
            for key in group:
                target = target[key]
            snapshot = group == ("snapshot_limits",)
            zero = {"max_references", "max_artifacts", "max_total_bytes"} if snapshot else {"max_file_bytes", "max_total_bytes"}
            for name in target:
                if name not in cli_controls._READABLE_CEILINGS:
                    continue
                value = self.value()
                changed = value
                for key in group:
                    changed = changed[key]
                changed[name] = 0
                with self.subTest(group=group, name=name):
                    if name in zero:
                        self.decode(value)
                    else:
                        with self.assertRaises(SnapshotLimitError):
                            self.decode(value)
                    changed[name] = -1
                    with self.assertRaises(SnapshotLimitError):
                        self.decode(value)
        for changes in (dict(version=True), dict(version=1.0), dict(version=2), dict(extra=1),
                        dict(command="inspect-readable-refresh"), dict(refresh_limits={})):
            with self.assertRaises(DomainValidationError):
                self.decode({**self.value(), **changes})

    def test_authored_json_rejects_hostile_scalars_and_depth(self):
        """Duplicate keys, malformed UTF-8, surrogates, excessive tokens and depth stay authored-input errors."""
        for data in (b'\xff', b'{"x":1,"x":2}', b'{"x":NaN}', b'{"x":Infinity}', b'{"x":1e999}',
                     b'{"x":"\\ud800"}', b'[' * 65 + b'0' + b']' * 65, b'{"x":' + b'1' * 129 + b'}'):
            with self.subTest(data=data[:20]), self.assertRaises(CliError) as caught:
                strict_json(data)
            self.assertEqual(caught.exception.code, "invalid_input")
        self.assertEqual(strict_json(b'[' * 64 + b'0' + b']' * 64), json.loads(b'[' * 64 + b'0' + b']' * 64))

    def test_selection_order_duplicates_and_explicit_current(self):
        """Selection order is detached intact; omissions, aliases by type and duplicate selectors fail."""
        value = dict(format="research_pipeline.cli_snapshot_selection", version=1,
                     project=dict(record_id="project", revision=None),
                     roots=[dict(record_id="b", revision=2), dict(record_id="a", revision=None)])
        self.save(value)
        selected = read_selection(self.path, 65536)
        self.assertEqual(selected.to_dict(), {key: value[key] for key in ("project", "roots")})
        value["roots"].append(dict(record_id="a", revision=None))
        self.save(value)
        with self.assertRaises(DomainValidationError):
            read_selection(self.path, 65536)
        value["roots"] = []
        del value["project"]["revision"]
        self.save(value)
        with self.assertRaises(DomainValidationError):
            read_selection(self.path, 65536)

    def test_maximum_escaped_paths_do_not_break_diagnostics(self):
        """Two maximal escaped paths and hostile prose stay bounded without path or identity truncation."""
        context = dict.fromkeys(cli_views.CONTEXT_FIELDS)
        path = "/" + "\x01" * 4095
        context.update(destination=path, attempt_path=path, plan_id="a" * 64,
                       next_action=cli_views.guidance("generate-readable-view", None))
        target = self.parent / "diagnostic"
        with target.open("wb") as stream, patch.object(cli.sys, "stderr", stream):
            cli._diagnostic("generate-readable-view", CliError(7, "effects_uncertain", "\U0001f600" * 10000), context)
        data = target.read_bytes()
        self.assertLessEqual(len(data), 65536)
        self.assertTrue(data.isascii())
        self.assertEqual(json.loads(data)["context"], context)

    def test_control_growth_replacement_and_close_failure(self):
        """Actual reads and checked closes reject observed mutation and resource failures."""
        self.save(self.value())
        original = self.path.read_bytes()
        def grow(boundary):
            """Grow the held control after its bounded read, before the binding close check."""
            if boundary == "after_control_read":
                with self.path.open("ab") as stream:
                    stream.write(b" ")
        with patch.object(cli_controls, "_fault", grow), self.assertRaises(Exception):
            read_readable_limits(self.path, len(original), "refresh-readable-view")
        self.save(self.value())
        def replace_control(boundary):
            """Replace a bound control with identical bytes after the read."""
            if boundary == "after_control_read":
                other = self.parent / "other"
                other.write_bytes(original)
                other.chmod(0o600)
                other.replace(self.path)
        with patch.object(cli_controls, "_fault", replace_control), self.assertRaises(Exception):
            read_readable_limits(self.path, 65536, "refresh-readable-view")
        self.save(self.value())
        def remove_control(boundary):
            """Remove an already observed leaf before open; this is mutation, not initial absence."""
            if boundary == "before_control_open":
                self.path.unlink()
        with patch.object(cli_controls, "_fault", remove_control), self.assertRaises(checkout.CheckoutIntegrityError):
            read_readable_limits(self.path, 65536, "refresh-readable-view")
        self.save(self.value())
        real_close = os.close
        def fail_close(fd):
            """Close the real descriptor, then report a failed acknowledgment of input close."""
            real_close(fd)
            raise OSError(5, "input close failed")
        with patch.object(os, "close", fail_close), self.assertRaises(OSError):
            read_readable_limits(self.path, 65536, "refresh-readable-view")

    def test_pinned_ancestor_disappears_during_subsequent_traversal(self):
        """Later acquisition, including a missing child, cannot hide disappearance of an earlier pin."""
        real_stat = checkout._stat
        for missing in (False, True):
            ancestor = self.parent / ("ancestor-" + str(missing))
            ancestor.mkdir(mode=0o700)
            child = ancestor / "child"
            target = child / "control"
            if not missing:
                child.mkdir(mode=0o700)
                target.write_bytes(b"{}")
                target.chmod(0o600)
            renamed = False
            def observe(parent, name):
                """Detach an already held ancestor immediately before observing its next child."""
                nonlocal renamed
                if name == "child" and not renamed:
                    ancestor.rename(ancestor.with_name(ancestor.name + "-detached"))
                    renamed = True
                return real_stat(parent, name)
            with self.subTest(missing=missing), patch.object(checkout, "_stat", observe):
                with self.assertRaises(checkout.CheckoutIntegrityError):
                    cli_controls.read_authored(target, 65536)
            self.assertTrue(renamed)
