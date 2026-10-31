"""Bounded exact CLI metadata reconstruction and offline original-checkout observation."""

from contextlib import ExitStack

from research_pipeline import checkout
from research_pipeline.cli_controls import CliError, read_control, strict_json
from research_pipeline.domain import DomainValidationError
from research_pipeline.snapshot import (
    SnapshotLimits, SnapshotIntegrityError, SnapshotLimitError, _bounded_json, _canonical,
)


def exact_record(store, record_id, revision, maximum, links):
    """Read one exact envelope/commit in a transaction without artifact reads or outgoing traversal."""
    limits = SnapshotLimits(1, 1, links, maximum, maximum, 0, 1, 1, 0)
    with store._transaction() as connection:
        envelope, entry, _, _ = store._snapshot_record(
            connection, (record_id, revision), limits, maximum, links)
    return envelope, entry["commit"]


def _lengths(row):
    """Require complete nonnegative SQL byte lengths before fetching selected receipt fields."""
    if row is None or any(type(value) is not int or value < 0 for value in row):
        raise SnapshotIntegrityError("missing or invalid receipt metadata")
    return sum(row)


def exact_receipt(store, submission_id, maximum, max_records):
    """Preflight and reconstruct the original receipt in the same SQLite read snapshot.

    Count repeated membership and fetched text before collecting rows or decoding
    provenance. No request payload, head, historical artifact or audit dump is read.
    Orphan events/membership and incomplete joins are corruption rather than absence.
    """
    with store._transaction() as connection:
        present = connection.execute("SELECT 1 FROM submissions WHERE submission_id=?",
                                     (submission_id,)).fetchone()
        if present is None:
            for table in ("audit_events", "revisions"):
                if connection.execute(f"SELECT 1 FROM {table} WHERE submission_id=? LIMIT 1",
                                      (submission_id,)).fetchone() is not None:
                    raise SnapshotIntegrityError("orphan submission metadata")
            return None
        lengths = connection.execute("""SELECT
            length(CAST(s.submission_id AS BLOB)),length(CAST(s.fingerprint AS BLOB)),
            length(CAST(e.event_id AS BLOB)),length(CAST(e.submission_id AS BLOB)),
            length(CAST(e.event_type AS BLOB)),length(CAST(e.committed_at AS BLOB)),
            length(CAST(e.provenance_json AS BLOB))
            FROM submissions s LEFT JOIN audit_events e USING(submission_id)
            WHERE s.submission_id=?""", (submission_id,)).fetchone()
        fetched = 2 * _lengths(lengths)
        count = connection.execute("SELECT count(*) FROM revisions WHERE submission_id=?",
                                   (submission_id,)).fetchone()[0]
        if count > max_records:
            raise SnapshotLimitError("receipt membership exceeds max_receipt_records")
        if count < 1:
            raise SnapshotIntegrityError("receipt has no membership")
        if fetched > maximum:
            raise SnapshotLimitError("receipt metadata byte preflight exceeded")
        cursor = connection.execute("""SELECT
            CASE WHEN typeof(r.ordinal)='integer' THEN r.ordinal ELSE NULL END,
            length(CAST(r.record_id AS BLOB)),length(CAST(r.revision AS BLOB)),
            length(CAST(i.record_id AS BLOB))
            FROM revisions r LEFT JOIN identities i USING(record_id)
            WHERE r.submission_id=? ORDER BY r.ordinal""", (submission_id,))
        for ordinal in range(count):
            row = cursor.fetchone()
            if row is None or type(row[0]) is not int or row[0] != ordinal:
                raise SnapshotIntegrityError("invalid receipt membership ordinals")
            fetched += _lengths(row[1:]) + len(str(ordinal))
            if fetched > maximum:
                raise SnapshotLimitError("receipt membership byte preflight exceeded")
        if cursor.fetchone() is not None:
            raise SnapshotIntegrityError("receipt membership count changed")
        raw = connection.execute("""SELECT event_type,provenance_json FROM audit_events
            WHERE submission_id=?""", (submission_id,)).fetchone()
        try:
            if raw[0] != "submission_committed":
                raise SnapshotIntegrityError("invalid receipt event type")
            provenance = strict_json(raw[1].encode("utf-8"))
            if _canonical(provenance) != raw[1]:
                raise SnapshotIntegrityError("noncanonical receipt provenance")
            receipt = store._receipt(connection, submission_id)
            if receipt is None or _canonical(receipt.provenance.to_dict()) != raw[1]:
                raise SnapshotIntegrityError("incomplete receipt provenance")
            _bounded_json(receipt.to_dict(), maximum - fetched, "receipt metadata")
            return receipt
        except SnapshotLimitError:
            raise
        except (ValueError, TypeError, KeyError, AttributeError, CliError) as error:
            raise SnapshotIntegrityError("invalid receipt reconstruction") from error


def local_checkout(path, maximum):
    """Inspect only published local controls, applying CLI byte/depth gates before the existing codec."""
    with ExitStack() as stack:
        directories = checkout._Directories(stack)
        area = directories.traverse(path, private=True, exact=True)
        control_path = path / checkout._CONTROL
        control = directories.open(checkout._CONTROL, area, private=True, exact=True, path=control_path)
        checkout._control_inventory(control, control_path, False)
        data = read_control(control, checkout._DESCRIPTOR, control_path / checkout._DESCRIPTOR,
                            maximum, modes=(0o400,))
        strict_json(data)
        try:
            info = checkout._decode(data)
        except checkout.CheckoutIntegrityError as error:
            raise DomainValidationError("invalid local checkout descriptor") from error
        checkout._control_inventory(control, control_path, False)
        directories.check()
    return info
