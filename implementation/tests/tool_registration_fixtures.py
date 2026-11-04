"""Real-store fixtures for passive registration, independent wire identities and damage tests."""

from contextlib import closing
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
import unittest

from research_pipeline.domain import RecordEnvelope
from research_pipeline.store import RecordStore, ReferenceResolutionError
from research_pipeline.tool_release import ToolRelease
from research_pipeline.tool_release_envelope import encode_envelope
from tests.test_store import CREATOR
from tests.tool_release_fixtures import (
    ARTIFACT_SLOTS, FILE_SLOTS, RECORD_SLOTS, at, constructor_sections, known, rehash, wire,
)

ROLES = (
    (RECORD_SLOTS[0], "reported_provenance", "source", False),
    (RECORD_SLOTS[1], "implementation_source", "source", True),
    (RECORD_SLOTS[1], "implementation_source", "work_product_manifest", True),
    (RECORD_SLOTS[2], "child_tool", "tool_release", True),
    (RECORD_SLOTS[3], "reported_qualification", "tool_assessment", False),
    (RECORD_SLOTS[4], "reported_evidence", "evidence", True),
    (RECORD_SLOTS[5], "reported_issue", "issue", True),
    (RECORD_SLOTS[6], "build_dependency", "source", False),
)
BYTES = (b"synthetic affine implementation\n", b"inert adapter\n", b"synthetic test description")


def declaration(identity="tool", kind="remote_service", links=(), artifacts=False):
    """Adapt substantive immutable fixtures with explicit pins and optional inert bytes.

    Links are (slot path, RecordReference) pairs; repeated occurrences stay ordered.
    Empty artifact inventories are used only for opaque remote declarations.
    """
    doc = wire(kind=kind)
    doc["identity"]["tool_id"] = identity
    for path in RECORD_SLOTS:
        at(doc, path).update(known([]))
    for path, reference in links:
        at(doc, path)["value"].append(reference.to_dict())
    if not artifacts:
        for path in (*ARTIFACT_SLOTS, *FILE_SLOTS):
            fact = at(doc, path)
            if fact["state"] == "known":
                fact.update(known([]))
        doc["invocation"]["adapter"]["entry_file"] = known(None)
    return ToolRelease(**constructor_sections(doc))


def changed(value, **identity_fields):
    """Reconstruct a release with independently rehashed identity-section changes."""
    doc = value.to_dict()
    doc["identity"].update(identity_fields)
    return ToolRelease.from_dict(rehash(doc))


def tool(value=None, revision=1, provenance=CREATOR):
    """Encode an explicit revision, retaining separate envelope creation attribution."""
    value = declaration() if value is None else value
    return encode_envelope(value.tool_id, revision, value, provenance)


def altered(envelope, **fields):
    """Reconstruct generic storage input with deliberately changed envelope fields."""
    doc = envelope.to_dict()
    doc.update(fields)
    return RecordEnvelope.from_dict(doc)


def rows(root):
    """Snapshot all user tables, including schema-3 authority/resource/control effects."""
    with closing(sqlite3.connect(root / "metadata.sqlite3")) as connection:
        names = [row[0] for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]
        return {name: connection.execute(f'SELECT * FROM "{name}" ORDER BY rowid').fetchall()
                for name in names}


class RegistrationCase(unittest.TestCase):
    """Provide private actual stores, complete rollback observations and confined damage."""

    def setUp(self):
        """Create one private schema-3 runtime and close it before temporary cleanup."""
        temporary = TemporaryDirectory(prefix="tool-registration-")
        self.addCleanup(temporary.cleanup)
        self.parent = Path(temporary.name)
        self.root = self.parent / "runtime"
        self.store = RecordStore.create(self.root, schema_version=3)
        self.addCleanup(self.store.close)

    def stage(self):
        """Stage the fixture's implementation, adapter and inert self-test bytes."""
        return tuple(self.store.put_artifact(data) for data in BYTES)

    def rejects(self, batch, error=ReferenceResolutionError):
        """Require rejection to preserve all rows and leave no new receipt or identity."""
        before = rows(self.root)
        with self.assertRaises(error) as caught:
            self.store.submit_typed(batch)
        self.assertEqual(rows(self.root), before)
        self.assertIsNone(self.store.get_submission(batch.submission_id))
        for record in batch.records:
            if record.record_id not in {row[0] for row in before["identities"]}:
                self.assertIsNone(self.store.head(record.record_id))
        return caught.exception

    def damage(self, sql, parameters=()):
        """Corrupt only this disposable open runtime, leaving production schema untouched."""
        with closing(sqlite3.connect(self.root / "metadata.sqlite3")) as connection:
            connection.execute("PRAGMA foreign_keys=OFF")
            with connection:
                connection.execute(sql, parameters)

    def object_path(self, artifact):
        """Locate an actual fixture object for isolated loss/corruption experiments."""
        return self.root / "objects" / artifact.digest
