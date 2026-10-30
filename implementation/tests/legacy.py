"""Independent historical SQLite and format-1 fixtures for compatibility tests."""

# Frozen from the accepted legacy contract: never obtain DDL from production
# version selection. This protects compatibility when current definitions change.
LEGACY_DDL = (
    """CREATE TABLE identities (
        record_id TEXT PRIMARY KEY NOT NULL,
        kind TEXT NOT NULL CHECK(kind IN ('research_context','claim','justification','evidence','task_specification')),
        head INTEGER NOT NULL CHECK(head > 0),
        FOREIGN KEY(record_id, head) REFERENCES revisions(record_id, revision) DEFERRABLE INITIALLY DEFERRED
    )""",
    """CREATE TABLE submissions (
        submission_id TEXT PRIMARY KEY NOT NULL,
        request_json TEXT NOT NULL,
        fingerprint TEXT NOT NULL
    )""",
    """CREATE TABLE revisions (
        record_id TEXT NOT NULL REFERENCES identities(record_id),
        revision INTEGER NOT NULL CHECK(revision > 0),
        submission_id TEXT NOT NULL REFERENCES submissions(submission_id),
        ordinal INTEGER NOT NULL CHECK(ordinal >= 0),
        content_json TEXT NOT NULL,
        provenance_json TEXT NOT NULL,
        operational_status TEXT CHECK(operational_status IN ('proposed','ready','blocked','active','completed','cancelled','abandoned')),
        scientific_disposition TEXT CHECK(scientific_disposition = 'provisional'),
        PRIMARY KEY(record_id, revision), UNIQUE(submission_id, ordinal)
    )""",
    """CREATE TABLE record_links (
        record_id TEXT NOT NULL, revision INTEGER NOT NULL, ordinal INTEGER NOT NULL CHECK(ordinal >= 0),
        relationship TEXT NOT NULL, target_id TEXT NOT NULL, target_revision INTEGER NOT NULL,
        target_kind TEXT CHECK(target_kind IN ('research_context','claim','justification','evidence','task_specification')),
        PRIMARY KEY(record_id, revision, ordinal),
        FOREIGN KEY(record_id, revision) REFERENCES revisions(record_id, revision),
        FOREIGN KEY(target_id, target_revision) REFERENCES revisions(record_id, revision)
    )""",
    """CREATE TABLE artifacts (
        digest TEXT PRIMARY KEY NOT NULL, size INTEGER NOT NULL CHECK(size >= 0), UNIQUE(digest, size)
    )""",
    """CREATE TABLE artifact_links (
        record_id TEXT NOT NULL, revision INTEGER NOT NULL, ordinal INTEGER NOT NULL CHECK(ordinal >= 0),
        digest TEXT NOT NULL, size INTEGER NOT NULL,
        PRIMARY KEY(record_id, revision, ordinal),
        FOREIGN KEY(record_id, revision) REFERENCES revisions(record_id, revision),
        FOREIGN KEY(digest, size) REFERENCES artifacts(digest, size)
    )""",
    """CREATE TABLE audit_events (
        event_id INTEGER PRIMARY KEY,
        submission_id TEXT NOT NULL UNIQUE REFERENCES submissions(submission_id),
        event_type TEXT NOT NULL CHECK(event_type = 'submission_committed'),
        committed_at TEXT NOT NULL, provenance_json TEXT NOT NULL
    )""",
    """CREATE TRIGGER revision_states BEFORE INSERT ON revisions BEGIN
        SELECT CASE WHEN NOT (
            ((SELECT kind FROM identities WHERE record_id = NEW.record_id) = 'claim'
                AND NEW.scientific_disposition IS 'provisional' AND NEW.operational_status IS NULL)
            OR ((SELECT kind FROM identities WHERE record_id = NEW.record_id) = 'task_specification'
                AND NEW.operational_status IS NOT NULL AND NEW.scientific_disposition IS NULL)
            OR ((SELECT kind FROM identities WHERE record_id = NEW.record_id) IN ('research_context','justification','evidence')
                AND NEW.operational_status IS NULL AND NEW.scientific_disposition IS NULL)
        ) THEN RAISE(ABORT, 'invalid kind/state combination') END;
    END""",
)


import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3

from research_pipeline.artifacts import ArtifactStore
from research_pipeline.domain import ArtifactReference, RecordEnvelope
from research_pipeline.store import RecordStore
from tests.test_store import graph, record, request
from tests.test_typed_store import context, envelope, typed_graph


def canonical(value):
    """Independently serialize the frozen legacy request/manifest JSON convention."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False)


def create_legacy(root):
    """Create real private v1 SQLite files without production schema selection."""
    root = Path(root)
    ArtifactStore.create(root)
    descriptor = os.open(root / "metadata.sqlite3", os.O_CREAT | os.O_EXCL | os.O_RDWR, 0o600)
    os.close(descriptor)
    connection = sqlite3.connect(root / "metadata.sqlite3")
    try:
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("BEGIN IMMEDIATE")
        for statement in LEGACY_DDL:
            connection.execute(statement)
        connection.execute("PRAGMA user_version=1")
        connection.commit()
    finally:
        connection.close()
    return RecordStore.open(root)


def legacy_request(submission):
    """Spell out historical canonical fields independently of current envelope serializers."""
    records = []
    for item in submission.records:
        records.append({
            "record_id": item.record_id, "revision": item.revision, "kind": item.kind,
            "content": item.content,
            "provenance": {"actor": item.provenance.actor, "created_at": item.provenance.created_at,
                           "details": item.provenance.details},
            "operational_status": item.operational_status,
            "scientific_disposition": item.scientific_disposition,
            "record_references": [{"record_id": link.record_id, "revision": link.revision,
                                   "relationship": link.relationship, "target_kind": link.target_kind}
                                  for link in item.record_references],
            "artifact_references": [{"digest": link.digest, "size": link.size} for link in item.artifact_references],
        })
    return {"fingerprint_version": 1, "submission": {
        "submission_id": submission.submission_id,
        "provenance": {"actor": submission.provenance.actor, "created_at": submission.provenance.created_at,
                       "details": submission.provenance.details},
        "records": records, "expected_heads": submission.expected_heads}}


def seed_request(connection, submission, event_id):
    """Write historical normalized rows and explicit original event metadata via real SQL."""
    text = canonical(legacy_request(submission))
    connection.execute("INSERT INTO submissions VALUES (?,?,?)",
                       (submission.submission_id, text, hashlib.sha256(text.encode()).hexdigest()))
    for ordinal, item in enumerate(submission.records):
        if submission.expected_heads[item.record_id] == 0:
            connection.execute("INSERT INTO identities VALUES (?,?,?)", (item.record_id, item.kind, item.revision))
        connection.execute("INSERT INTO revisions VALUES (?,?,?,?,?,?,?,?)",
                           (item.record_id, item.revision, submission.submission_id, ordinal,
                            canonical(item.content), canonical(item.provenance.to_dict()),
                            item.operational_status, item.scientific_disposition))
    for item in submission.records:
        for ordinal, link in enumerate(item.record_references):
            connection.execute("INSERT INTO record_links VALUES (?,?,?,?,?,?,?)",
                               (item.record_id, item.revision, ordinal, link.relationship,
                                link.record_id, link.revision, link.target_kind))
        for ordinal, link in enumerate(item.artifact_references):
            connection.execute("INSERT OR IGNORE INTO artifacts VALUES (?,?)", (link.digest, link.size))
            connection.execute("INSERT INTO artifact_links VALUES (?,?,?,?,?)",
                               (item.record_id, item.revision, ordinal, link.digest, link.size))
        connection.execute("UPDATE identities SET head=? WHERE record_id=?", (item.revision, item.record_id))
    connection.execute("INSERT INTO audit_events VALUES (?,?,'submission_committed',?,?)",
                       (event_id, submission.submission_id, f"2026-10-30T12:00:{event_id:02}.123456Z",
                        canonical(submission.provenance.to_dict())))


def historical_store(root):
    """Seed deterministic generic/typed history, old requests, multiple revisions and artifacts."""
    store = create_legacy(root)
    artifact = store.put_artifact(b"independent historical graph bytes\n")
    generic = []
    for item in graph(artifact):
        fields = item.to_dict()
        fields["record_id"] = "g-" + fields["record_id"]
        for link in fields["record_references"]:
            link["record_id"] = "g-" + link["record_id"]
        generic.append(RecordEnvelope.from_dict(fields))
    requests = [request("legacy-generic", generic),
                request("legacy-task", [record("task", kind="task_specification")]),
                request("legacy-typed", typed_graph(artifact)),
                request("legacy-context-next", [envelope("context", context(), 2)], {"context": 1}),
                request("legacy-generic-next", [record("g-context", 2)], {"g-context": 1})]
    connection = sqlite3.connect(Path(root) / "metadata.sqlite3")
    try:
        connection.execute("PRAGMA foreign_keys=ON")
        for index, submission in enumerate(requests, 1):
            connection.execute("BEGIN IMMEDIATE")
            seed_request(connection, submission, index * 11)
            connection.commit()
    finally:
        connection.close()
    return store, requests, artifact


def historical_backup(root, destination):
    """Assemble a format-1 backup independently of the exporter, returning its manifest identity."""
    destination = Path(destination)
    target = ArtifactStore.create(destination)
    source = ArtifactStore.open(root)
    shutil.copyfile(Path(root) / "metadata.sqlite3", destination / "snapshot.sqlite3")
    (destination / "snapshot.sqlite3").chmod(0o400)
    connection = sqlite3.connect((destination / "snapshot.sqlite3").as_uri() + "?mode=ro", uri=True)
    try:
        entries = [{"digest": digest, "size": size} for digest, size in
                   connection.execute("SELECT digest,size FROM artifacts ORDER BY digest")]
    finally:
        connection.close()
    for entry in entries:
        target.put(source.read(ArtifactReference(**entry)))
    data = (destination / "snapshot.sqlite3").read_bytes()
    document = {"format_version": 1, "schema_version": 1,
                "metadata": {"digest": hashlib.sha256(data).hexdigest(), "size": len(data)}, "artifacts": entries}
    text = canonical(document).encode()
    (destination / "manifest.json").write_bytes(text)
    (destination / "manifest.json").chmod(0o400)
    return document, hashlib.sha256(text).hexdigest()


def table_values(root, name="metadata.sqlite3"):
    """Read all seven original tables for exact historical preservation assertions."""
    connection = sqlite3.connect((Path(root) / name).as_uri() + "?mode=ro", uri=True)
    try:
        return {table: connection.execute(f"SELECT * FROM {table} ORDER BY 1,2").fetchall()
                for table in ("identities", "revisions", "record_links", "artifacts", "artifact_links",
                              "submissions", "audit_events")}
    finally:
        connection.close()
