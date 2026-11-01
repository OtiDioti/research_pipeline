"""Canonical resource admissions and historical invariants on the store's SQLite boundary."""

from datetime import datetime, timezone
import hashlib

from research_pipeline.resources import (
    MAX_QUANTITY, PURPOSES, ResourceCapacityError, ResourceConflictError,
    ResourceInspectionLimitError, ResourceInspectionLimits, ResourceIntegrityError,
    ResourceReceipt, ResourceRequest, ResourceSnapshot, ResourceValidationError,
    amounts, by_kind, canonical, dumps_request, fields, identifier, loads_request,
    quantity, strict_json, validate_call_envelope, validate_run_policy,
)
from research_pipeline.schema import validate_history, validate_schema, _json as history_json
from research_pipeline.snapshot import _schema_identity


_ACCOUNT_COLUMNS = "account_id operation_id owner_id scope_kind stable_identity scope_json parent_account_id dimensions_json limits_json policy_json"
_ALLOCATION_COLUMNS = "allocation_id operation_id parent_account_id account_id purpose_limits_json"
_RESERVATION_COLUMNS = "reservation_id operation_id account_id purpose maxima_json call_bounds_json"
_LINK_COLUMNS = "operation_id ordinal target_id target_revision relationship target_kind"


def _fault(boundary):
    """Private observation seam before writes, after real writes, after COMMIT, and during inspection."""


def require_schema(store):
    """Preserve closed-handle errors and reject old schemas before resource API effects."""
    from research_pipeline.store import StoreLayoutError
    store._require_open()
    if store._schema_version != 3:
        raise StoreLayoutError("resource accounting requires explicit migration to schema 3")


def _empty_state():
    """Create prior-history state for validation; this never represents a second durable ledger."""
    return {"accounts": {}, "allocations": {}, "reservations": {},
            "usage": {}, "source_receipts": set(), "breaches": {}}


def _stable(scope):
    """Identify a scope independently of its exact record revision."""
    return scope["reference"]["record_id"] if scope["type"] == "record" else scope["stable_identity"]


def references(request):
    """Project exact references in declared order without entering scientific outgoing links."""
    payload = request["payload"]
    scope = payload.get("scope")
    scoped = [scope["reference"]] if scope is not None and scope["type"] == "record" else []
    return scoped + request["policy_references"] + request["evidence_references"]


def _check_references(connection, request, watermark):
    """Require exact kinds/revisions visible by the receipt's scientific event watermark."""
    for ref in references(request):
        row = connection.execute("""SELECT i.kind,e.event_id FROM revisions r
            JOIN identities i USING(record_id) JOIN audit_events e USING(submission_id)
            WHERE r.record_id=? AND r.revision=?""", (ref["record_id"], ref["revision"])).fetchone()
        if row is None or row[0] != ref["target_kind"] or not 1 <= row[1] <= watermark:
            raise ResourceValidationError("resource reference is absent, wrong-kind, or newer than scientific watermark")


def _zero(account):
    """Construct a complete dimension map for exact local calculations."""
    return {d["dimension_id"]: 0 for d in account["dimensions"]}


def _sum_vectors(vectors, account):
    """Aggregate using Python integers; admission separately bounds every new expression."""
    result = _zero(account)
    for value in vectors:
        for key, number in amounts(value, account["dimensions"]).items():
            result[key] += number
    return result


def _root(state, account):
    """Resolve the immutable project ancestor for the conservative admission gate."""
    while account["parent_account_id"] is not None:
        account = state["accounts"][account["parent_account_id"]]
    return account["account_id"]


def _blocked(state, account):
    """Keep every admission under a breached project blocked, including siblings and purposes."""
    root = _root(state, account)
    return any(_root(state, state["accounts"][fact["account_id"]]) == root
               for fact in state["breaches"].values())


def _reservation_usage(state, reservation):
    """Derive cumulative charges once: partial spending consumes, rather than adds to, liability."""
    usage = state["usage"][reservation["reservation_id"]]
    rows = {}
    for key, maximum in amounts(reservation["maxima"], state["accounts"][reservation["account_id"]]["dimensions"]).items():
        observed = usage["known"][key]
        known = 0 if observed is None else observed
        status = usage["status"]
        charged = known if status == "authoritative" else max(maximum, known)
        rows[key] = {"observed_quantity": observed, "known_spent": known,
                     "conservative_excess": charged - known if status == "conservative" else 0,
                     "remaining_reserved": max(maximum - known, 0) if status == "unresolved" else 0,
                     "charged_total": charged, "actual_usage": known if status == "authoritative" else None}
    return rows


def _accounting(state):
    """Roll up exact commitments and measured subtrees while retaining immutable delegation.

    Each child contributes max(allocation, effective commitment), componentwise.
    Aggregates use Python integers, not the bounded input quantity validator.
    """
    result = {}
    # Chronological admission inserts every parent before its children. Reverse
    # order therefore makes each child rollup available without recursive SQL.
    for account in reversed(list(state["accounts"].values())):
        account_id = account["account_id"]
        purposes = ("total",) if account["scope"]["kind"] == "project" else PURPOSES
        children = [a for a in state["allocations"].values() if a["parent_account_id"] == account_id]
        for purpose in purposes:
            direct = [r for r in state["reservations"].values()
                      if r["account_id"] == account_id and r["purpose"] == purpose]
            usage = [(r["reservation_id"], _reservation_usage(state, r)) for r in direct]
            limits = amounts(account["limits"] if purpose == "total" else account["limits"][purpose], account["dimensions"])
            rows = {}
            for key, ceiling in limits.items():
                known = sum(u[key]["known_spent"] for _, u in usage)
                excess = sum(u[key]["conservative_excess"] for _, u in usage)
                reserved = sum(u[key]["remaining_reserved"] for _, u in usage)
                row = {"ceiling": ceiling, "delegated_to_children": 0, "child_overrun": 0,
                       "direct_known_spent": known, "direct_conservative_excess": excess,
                       "direct_reserved": reserved, "known_spent": known,
                       "conservative_excess": excess, "subtree_reserved": reserved,
                       "unknown_reservation_ids": [rid for rid, u in usage if u[key]["actual_usage"] is None]}
                for child in children:
                    for child_purpose in PURPOSES if purpose == "total" else (purpose,):
                        allocated = amounts(child["purpose_limits"][child_purpose], account["dimensions"])[key]
                        child_row = result[(child["account_id"], child_purpose)][key]
                        row["delegated_to_children"] += allocated
                        row["child_overrun"] += max(child_row["commitment"] - allocated, 0)
                        for name in ("known_spent", "conservative_excess", "subtree_reserved"):
                            row[name] += child_row[name]
                        row["unknown_reservation_ids"].extend(child_row["unknown_reservation_ids"])
                row["unknown_reservation_ids"].sort()
                row["commitment"] = (row["delegated_to_children"] + row["child_overrun"]
                                     + known + excess + reserved)
                row["available_for_local_use"] = ceiling - row["commitment"]
                row["actual_usage"] = None if row["unknown_reservation_ids"] else row["known_spent"]
                rows[key] = row
            result[(account_id, purpose)] = rows
    return result


def _available(state, account, purpose):
    """Return signed local availability using effective child commitments and direct charges."""
    return {key: row["available_for_local_use"]
            for key, row in _accounting(state)[(account["account_id"], purpose)].items()}


def _breach(state, operation_id, account_id, purpose, dimension_id, reason, observed, limit):
    """Retain the first deterministic fact for each local reason; settlement never clears it."""
    key = (account_id, purpose, dimension_id, reason)
    if observed > limit and key not in state["breaches"]:
        state["breaches"][key] = {"trigger_operation_id": operation_id, "account_id": account_id,
            "purpose": purpose, "dimension_id": dimension_id, "reason": reason,
            "observed": str(observed), "limit": str(limit)}


def _usage_target(state, payload):
    """Resolve original immutable attribution before recording usage or settlement evidence."""
    reservation = state["reservations"].get(payload["reservation_id"])
    account = state["accounts"].get(payload["account_id"])
    if (reservation is None or account is None or reservation["account_id"] != payload["account_id"]
            or account["owner_id"] != payload["owner_id"]):
        raise ResourceConflictError("usage account/reservation/owner does not match original attribution")
    return reservation, account, state["usage"][payload["reservation_id"]]


def _observe(state, request):
    """Merge validated receipts and derive sticky sampled/cumulative breaches without releasing liability.

    Current positive receipt counts align retained token lower bounds with an
    observed call population; unknown counts cannot establish invocation facts.
    """
    p, op = request["payload"], request["operation_id"]
    reservation, account, usage = _usage_target(state, p)
    values = amounts(p["usage"], account["dimensions"])
    kinds = by_kind(p["usage"], account["dimensions"])
    if kinds["model_calls"] == 0 and any(kinds[k] not in (None, 0) for k in ("model_input_tokens", "model_output_tokens")):
        raise ResourceValidationError("known zero calls cannot have positive model tokens")
    for category, kind in (("cached_input_tokens", "model_input_tokens"), ("reasoning_output_tokens", "model_output_tokens")):
        number = p["telemetry"][category]
        if number is not None and (kinds[kind] is None or number > kinds[kind]):
            raise ResourceValidationError("telemetry requires a containing numeric cumulative total")
    sample = p["call_observation"]
    if sample is not None:
        if (kinds["model_calls"] is None or kinds["model_calls"] < 1
                or any(kinds[kind] is None or sample[field] > kinds[kind]
                       for field, kind in (("input_tokens", "model_input_tokens"), ("output_tokens", "model_output_tokens")))):
            raise ResourceValidationError("call sample requires containing numeric calls/input/output totals")
    if p["evidence"]["source_kind"] == "controller_receipt":
        identity = (p["evidence"]["source_id"], p["evidence"]["source_receipt_id"])
        if identity in state["source_receipts"]:
            raise ResourceConflictError("source receipt belongs to its original observation; retry original operation_id")
        for key, number in values.items():
            previous = usage["known"][key]
            if number is not None and previous is not None and number < previous:
                raise ResourceConflictError("cumulative usage cannot decrease; refunds/corrections unsupported")
        merged = {key: usage["known"][key] if number is None else number for key, number in values.items()}
        by_type = {d["kind"]: merged[d["dimension_id"]] for d in account["dimensions"]}
        if by_type["model_calls"] == 0 and any(by_type[k] not in (None, 0) for k in ("model_input_tokens", "model_output_tokens")):
            raise ResourceConflictError("cumulative evidence contradicts known zero calls")
        if usage["status"] == "authoritative":
            for key, number in merged.items():
                _breach(state, op, account["account_id"], reservation["purpose"], key,
                        "post_settlement_usage", number, usage["known"][key])
            if merged != usage["known"]:
                usage["status"] = "unresolved"
        usage["known"] = merged
        usage["latest_receipt"] = request
        state["source_receipts"].add(identity)
    usage["latest_observation_operation_id"] = op
    purpose = reservation["purpose"]
    for key, maximum in amounts(reservation["maxima"], account["dimensions"]).items():
        _breach(state, op, account["account_id"], purpose, key, "reservation_maximum",
                usage["known"][key] or 0, maximum)
    ids = {d["kind"]: d["dimension_id"] for d in account["dimensions"]}
    bounds = reservation["call_bounds"]
    if sample is not None:
        # A receipt may establish a call even where the original declaration had none.
        for field, kind, bound in (("input_tokens", "model_input_tokens", "max_input_tokens_per_call"),
                                   ("output_tokens", "model_output_tokens", "max_output_tokens_per_call")):
            _breach(state, op, account["account_id"], purpose, ids[kind], "per_call_bound",
                    sample[field], 0 if bounds is None else bounds[bound])
        _breach(state, op, account["account_id"], purpose, ids["model_output_tokens"], "run_output_bound",
                sample["output_tokens"], account["policy"]["per_call_output_tokens"])
        # Context is a sum of input and output tokens, represented under the input dimension.
        _breach(state, op, account["account_id"], purpose, ids["model_input_tokens"], "context_bound",
                sample["input_tokens"] + sample["output_tokens"], account["policy"]["context_capacity_tokens"])
    calls = kinds["model_calls"]
    # An older count is not an upper bound on the population behind newer tokens.
    # Only this receipt's positive count aligns the retained cumulative lower bounds.
    if p["evidence"]["source_kind"] == "controller_receipt" and calls is not None and calls > 0:
        inputs = usage["known"][ids["model_input_tokens"]]
        outputs = usage["known"][ids["model_output_tokens"]]
        # These exact products are proofs, not charges or bounded input quantities.
        # Samples run first so their individual-call diagnostics retain priority.
        for number, kind, bound in ((inputs, "model_input_tokens", "max_input_tokens_per_call"),
                                    (outputs, "model_output_tokens", "max_output_tokens_per_call")):
            if number is not None:
                _breach(state, op, account["account_id"], purpose, ids[kind], "per_call_bound",
                        number, calls * (0 if bounds is None else bounds[bound]))
        if outputs is not None:
            _breach(state, op, account["account_id"], purpose, ids["model_output_tokens"], "run_output_bound",
                    outputs, calls * account["policy"]["per_call_output_tokens"])
        if inputs is not None or outputs is not None:
            # Unknown tokens contribute only a mathematical lower bound, never measured zero.
            _breach(state, op, account["account_id"], purpose, ids["model_input_tokens"], "context_bound",
                    (inputs or 0) + (outputs or 0), calls * account["policy"]["context_capacity_tokens"])
    for (account_id, pool), rows in sorted(_accounting(state).items()):
        for key, row in sorted(rows.items()):
            _breach(state, op, account_id, pool, key, "ceiling_excess", row["commitment"], row["ceiling"])
            _breach(state, op, account_id, pool, key, "aggregate_known_overflow", row["known_spent"], MAX_QUANTITY)


def _reconcile(state, request):
    """Apply explicit evidence and predecessor checks; no uncertainty observation releases capacity."""
    p = request["payload"]
    _, _, usage = _usage_target(state, p)
    if p["previous_reconciliation_operation_id"] != usage["latest_reconciliation_operation_id"]:
        raise ResourceConflictError("stale reconciliation predecessor")
    if p["mode"] == "authoritative":
        latest = usage["latest_receipt"]
        if (latest is None or p["observation_operation_id"] != latest["operation_id"]
                or latest["payload"]["event"] != "authoritative_completion"):
            raise ResourceConflictError("authoritative settlement requires latest complete controller receipt")
        if usage["status"] == "conservative" and latest["operation_id"] == usage["settled_receipt_operation_id"]:
            raise ResourceConflictError("conservative refinement requires newer authoritative completion evidence")
    elif p["observation_operation_id"] != usage["latest_observation_operation_id"]:
        raise ResourceConflictError("conservative settlement requires latest observation or initial null")
    if usage["status"] == p["mode"] or usage["status"] == "authoritative":
        raise ResourceConflictError("unchanged terminal settlement or unsupported downward correction")
    usage["status"] = p["mode"]
    usage["latest_reconciliation_operation_id"] = request["operation_id"]
    usage["settled_receipt_operation_id"] = (None if usage["latest_receipt"] is None
                                              else usage["latest_receipt"]["operation_id"])


def _fits(needed, available, message):
    """Reject negative availability or an expression exceeding the declared bounded capacity."""
    for key, value in needed.items():
        quantity(value, "capacity expression")
        if value > available[key]:
            raise ResourceCapacityError(message)


def _minimum(pool, minimum, declared, message):
    """Require an entire componentwise minimum, without treating per-call constraints as budgets."""
    _fits(amounts(minimum, declared), amounts(pool, declared), message)


def _run(state, account):
    """Find the inherited run through the previously validated acyclic hierarchy."""
    while account["scope"]["kind"] != "run":
        account = state["accounts"][account["parent_account_id"]]
    return account


def _admit(state, request):
    """Apply one declaration to prior state after all identity, hierarchy and capacity checks.

    This same finite admission code validates historical order and new writes.
    It only builds detached projections; SQLite publication belongs to mutate.
    """
    p, kind, op = request["payload"], request["kind"], request["operation_id"]
    accounts, allocations, reservations = (state[k] for k in ("accounts", "allocations", "reservations"))
    if kind == "observe":
        _observe(state, request)
        return
    if kind == "reconcile":
        _reconcile(state, request)
        return
    if kind in ("allocate", "reserve"):
        target = accounts.get(p["parent_account_id"] if kind == "allocate" else p["account_id"])
        if target is not None and _blocked(state, target):
            raise ResourceCapacityError("admission blocked by sticky resource breach under project " + _root(state, target))
    if kind in ("create_account", "allocate"):
        if p["account_id"] in accounts:
            raise ResourceConflictError("resource account identity already committed")
        scope = p["scope"]
        if any((a["scope"]["kind"], _stable(a["scope"])) == (scope["kind"], _stable(scope)) for a in accounts.values()):
            raise ResourceConflictError("stable scope already has a resource account")
        if kind == "create_account":
            account = {"account_id": p["account_id"], "operation_id": op, "owner_id": p["owner_id"],
                       "scope": scope, "parent_account_id": None, "dimensions": p["dimensions"],
                       "limits": p["ceiling"], "policy": p["policy"]}
        else:
            if p["allocation_id"] in allocations:
                raise ResourceConflictError("allocation identity already committed")
            parent = accounts.get(p["parent_account_id"])
            if parent is None or parent["owner_id"] != p["owner_id"]:
                raise ResourceValidationError("allocation parent absent or owner mismatch")
            allowed = {"project": ("run",), "run": ("branch", "task"), "branch": ("task",), "task": ("attempt",), "attempt": ()}
            if scope["kind"] not in allowed[parent["scope"]["kind"]]:
                raise ResourceValidationError("invalid resource hierarchy")
            declared, limits = parent["dimensions"], p["purpose_limits"]
            for value in limits.values():
                amounts(value, declared)
            account = {"account_id": p["account_id"], "operation_id": op, "owner_id": p["owner_id"],
                       "scope": scope, "parent_account_id": parent["account_id"], "dimensions": declared,
                       "limits": limits, "policy": p["run_policy"] if scope["kind"] == "run" else parent["policy"]}
            if scope["kind"] == "run":
                validate_run_policy(account["policy"], declared)
                for purpose in ("verification", "handoff", "closeout"):
                    _minimum(limits[purpose], account["policy"][purpose + "_minimum"], declared,
                             "run purpose pool cannot provision its minimum")
                total = _sum_vectors(list(limits.values()), account)
                _fits(total, _available(state, parent, "total"), "project ceiling exhausted")
            else:
                if any(amounts(limits["closeout"], declared).values()):
                    raise ResourceValidationError("only a run may own closeout capacity")
                if scope["kind"] == "attempt":
                    _minimum(limits["handoff"], account["policy"]["handoff_minimum"], declared,
                             "attempt requires its own complete handoff minimum")
                for purpose in PURPOSES:
                    _fits(amounts(limits[purpose], declared), _available(state, parent, purpose),
                          "parent purpose allocation exhausted")
            allocations[p["allocation_id"]] = {"allocation_id": p["allocation_id"], "operation_id": op,
                "parent_account_id": p["parent_account_id"], "account_id": p["account_id"], "purpose_limits": limits}
        accounts[p["account_id"]] = account
    elif kind == "reserve":
        if p["reservation_id"] in reservations:
            raise ResourceConflictError("reservation identity already committed")
        account = accounts.get(p["account_id"])
        if account is None or account["owner_id"] != p["owner_id"]:
            raise ResourceValidationError("reservation account absent or owner mismatch")
        purpose, scope = p["purpose"], account["scope"]["kind"]
        if (purpose == "closeout" and scope != "run") or (purpose != "closeout" and scope != "attempt"):
            raise ResourceValidationError("reservation purpose unavailable at this scope")
        maxima = amounts(p["maxima"], account["dimensions"])
        if not any(maxima.values()):
            raise ResourceValidationError("reservation needs at least one positive maximum")
        values = by_kind(p["maxima"], account["dimensions"])
        if values["model_calls"] == 0:
            if p["call_bounds"] is not None or values["model_input_tokens"] or values["model_output_tokens"]:
                raise ResourceValidationError("zero model calls require null bounds and zero model token maxima")
        else:
            validate_call_envelope(values, p["call_bounds"], account["policy"]["context_capacity_tokens"],
                                   account["policy"]["per_call_output_tokens"])
        _fits(maxima, _available(state, account, purpose), "reservation exceeds available purpose capacity")
        if purpose in ("ordinary", "verification"):
            run = _run(state, account)
            # Protected free minima must remain usable after any earlier handoff or
            # closeout commitment; no automatic lifecycle transition releases them.
            _fits(amounts(account["policy"]["handoff_minimum"], account["dimensions"]),
                  _available(state, account, "handoff"), "attempt handoff minimum is no longer free")
            _fits(amounts(run["policy"]["closeout_minimum"], run["dimensions"]),
                  _available(state, run, "closeout"), "run closeout minimum is no longer free")
        reservations[p["reservation_id"]] = {"reservation_id": p["reservation_id"], "operation_id": op,
            "account_id": p["account_id"], "purpose": purpose, "maxima": p["maxima"], "call_bounds": p["call_bounds"]}
        state["usage"][p["reservation_id"]] = {"status": "unresolved", "known": dict.fromkeys(maxima),
            "latest_observation_operation_id": None, "latest_receipt": None,
            "latest_reconciliation_operation_id": None, "settled_receipt_operation_id": None}
    else:
        raise ResourceValidationError("unsupported resource operation")


def _account_row(a):
    """Project one canonical account into the fixed normalized SQLite columns."""
    return (a["account_id"], a["operation_id"], a["owner_id"], a["scope"]["kind"], _stable(a["scope"]),
            canonical(a["scope"]), a["parent_account_id"], canonical(a["dimensions"]), canonical(a["limits"]), canonical(a["policy"]))


def _allocation_row(a):
    """Project one immutable delegation without adding descendant spending again."""
    return (a["allocation_id"], a["operation_id"], a["parent_account_id"], a["account_id"], canonical(a["purpose_limits"]))


def _reservation_row(r):
    """Project the immutable original reservation, retaining maxima and invocation bounds after settlement."""
    return (r["reservation_id"], r["operation_id"], r["account_id"], r["purpose"], canonical(r["maxima"]), canonical(r["call_bounds"]))


def _link_rows(request):
    """Build deterministic exact-reference projections for an operation."""
    return [(request["operation_id"], i, r["record_id"], r["revision"], r["relationship"], r["target_kind"])
            for i, r in enumerate(references(request))]


def _receipt(request, fingerprint, sequence, timestamp, watermark):
    """Construct exact committed membership without embedding changeable balances."""
    p = request["payload"]
    return ResourceReceipt({"format": "research_pipeline.resource_receipt", "version": 1,
        "operation_id": request["operation_id"], "receipt_id": request["receipt_id"], "sequence": sequence,
        "request_fingerprint": fingerprint, "kind": request["kind"], "account_id": p["account_id"],
        "allocation_id": p.get("allocation_id"), "reservation_id": p.get("reservation_id"),
        "committed_at": timestamp, "provenance": request["provenance"], "scientific_watermark_event_id": watermark})


def validate_ledger(connection):
    """Validate administrative and chronological ledger invariants in the caller's read/write snapshot.

    Live callers must first allow legitimate journal recovery. Immutable backup
    callers independently validate scientific history and artifact closure too.
    Returns detached validated projections and original operations, never writes.
    """
    try:
        validate_schema(connection.execute("PRAGMA user_version").fetchone()[0],
                        [row[0] for row in connection.execute("SELECT sql FROM sqlite_master WHERE sql IS NOT NULL")])
        validate_history(connection.execute("SELECT * FROM migration_history ORDER BY migration_id").fetchall(),
                         connection.execute("SELECT digest,size FROM artifacts").fetchall(), 3)
        if connection.execute("PRAGMA foreign_key_check").fetchall():
            raise ResourceIntegrityError("ledger foreign key violation")
        state, operations, links = _empty_state(), [], []
        events = {row[0] for row in connection.execute("SELECT event_id FROM audit_events")}
        seen_ops, seen_receipts = set(), set()
        previous_watermark = 0
        for row in connection.execute("SELECT sequence,operation_id,receipt_id,request_json,fingerprint,result_json,committed_at FROM resource_operations ORDER BY sequence"):
            sequence, op, rid, text, fingerprint, result_text, timestamp = row
            request = loads_request(text)
            doc = request.to_dict()
            receipt = ResourceReceipt.from_dict(strict_json(result_text))
            result = receipt.to_dict()
            watermark = result["scientific_watermark_event_id"]
            if (sequence != len(operations) + 1 or op in seen_ops or rid in seen_receipts
                    or op != doc["operation_id"] or rid != doc["receipt_id"] or text != request._json
                    or fingerprint != request.fingerprint or result_text != receipt._json
                    or watermark < previous_watermark or (watermark != 0 and watermark not in events)):
                raise ResourceIntegrityError("operation canonical identity, sequence, fingerprint or watermark mismatch")
            expected = _receipt(doc, fingerprint, sequence, timestamp, watermark)
            if expected != receipt or timestamp != result["committed_at"]:
                raise ResourceIntegrityError("receipt does not match its operation")
            _check_references(connection, doc, watermark)
            _admit(state, doc)
            links.extend(_link_rows(doc))
            operations.append({"request": doc, "receipt": result})
            seen_ops.add(op)
            seen_receipts.add(rid)
            previous_watermark = watermark
        for table, columns, projector in (("accounts", _ACCOUNT_COLUMNS, _account_row),
                                          ("allocations", _ALLOCATION_COLUMNS, _allocation_row),
                                          ("reservations", _RESERVATION_COLUMNS, _reservation_row)):
            actual = connection.execute(f"SELECT {','.join(columns.split())} FROM resource_{table} ORDER BY 1").fetchall()
            expected = sorted(projector(item) for item in state[table].values())
            if actual != expected:
                raise ResourceIntegrityError(f"resource {table}: normalized rows disagree with operation history")
        actual_links = connection.execute("SELECT " + ','.join(_LINK_COLUMNS.split()) + " FROM resource_record_links ORDER BY operation_id,ordinal").fetchall()
        if actual_links != sorted(links):
            raise ResourceIntegrityError("resource reference projection disagrees with history")
        return state, operations
    except (ValueError, TypeError, AttributeError, KeyError, RecursionError, OverflowError) as error:
        raise ResourceIntegrityError(f"invalid resource history: {error}") from error


def mutate(store, request, kind):
    """Commit atomically, verifying saved request/result identity before any new state admission."""
    require_schema(store)
    text = dumps_request(request)
    normalized = loads_request(text)
    doc = normalized.to_dict()
    if doc["kind"] != kind:
        raise ResourceValidationError("request kind does not match resource method")
    with store._transaction(write=True, reconciliation_id="operation_id") as connection:
        # Exact retries precede capacity/reference checks and return the original
        # stored receipt. Changed policy bounds are part of this same fingerprint.
        old = connection.execute("SELECT request_json,result_json FROM resource_operations WHERE operation_id=?", (doc["operation_id"],)).fetchone()
        if old is not None:
            if old[0] != text:
                raise ResourceConflictError("operation_id already committed a different request")
            receipt = ResourceReceipt.from_dict(strict_json(old[1]))
            result = receipt.to_dict()
            if receipt != _receipt(doc, normalized.fingerprint, result["sequence"], result["committed_at"],
                                   result["scientific_watermark_event_id"]):
                raise ResourceIntegrityError("saved result identity disagrees with original operation")
            return receipt
        if connection.execute("SELECT 1 FROM resource_operations WHERE receipt_id=?", (doc["receipt_id"],)).fetchone():
            raise ResourceConflictError("receipt_id already committed")
        state, operations = validate_ledger(connection)
        sequence = quantity(len(operations) + 1, "operation sequence", 1)
        watermark = connection.execute("SELECT coalesce(max(event_id),0) FROM audit_events").fetchone()[0]
        _check_references(connection, doc, watermark)
        _admit(state, doc)
        timestamp = datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")
        receipt = _receipt(doc, normalized.fingerprint, sequence, timestamp, watermark)
        _fault("before_writes")
        connection.execute("INSERT INTO resource_operations VALUES (?,?,?,?,?,?,?)",
            (sequence, doc["operation_id"], doc["receipt_id"], text, normalized.fingerprint, receipt._json, timestamp))
        p = doc["payload"]
        if kind in ("create_account", "allocate"):
            connection.execute("INSERT INTO resource_accounts VALUES (?,?,?,?,?,?,?,?,?,?)", _account_row(state["accounts"][p["account_id"]]))
        if kind == "allocate":
            connection.execute("INSERT INTO resource_allocations VALUES (?,?,?,?,?)", _allocation_row(state["allocations"][p["allocation_id"]]))
        elif kind == "reserve":
            connection.execute("INSERT INTO resource_reservations VALUES (?,?,?,?,?,?)", _reservation_row(state["reservations"][p["reservation_id"]]))
        connection.executemany("INSERT INTO resource_record_links VALUES (?,?,?,?,?,?)", _link_rows(doc))
        _fault("after_writes")
    # A successful COMMIT is outside rollback handling. Loss of this acknowledgment
    # retains the liability and requires inspection of the original operation_id.
    _fault("after_commit")
    return receipt


def get_operation(store, operation_id):
    """Return an original committed result or None from one consistent read transaction."""
    require_schema(store)
    identifier(operation_id, "operation_id")
    with store._transaction(reconciliation_id="operation_id") as connection:
        row = connection.execute("SELECT result_json FROM resource_operations WHERE operation_id=?", (operation_id,)).fetchone()
        return None if row is None else ResourceReceipt.from_dict(strict_json(row[0]))


def _decimal(value):
    """Encode exact derived integers in [-B*B, B*B], separately from bounded input quantities."""
    if value is None:
        return None
    if type(value) is not int or not -MAX_QUANTITY**2 <= value <= MAX_QUANTITY**2:
        raise ResourceIntegrityError("derived aggregate exceeds operation-count representation")
    return str(value)


def _projections(state):
    """Detach immutable declarations, derived reservation usage, and first chronological breach facts."""
    result = {key: [values[i] for i in sorted(values)] for key, values in state.items()
              if key in ("accounts", "allocations", "reservations")}
    result["reservation_usage"] = []
    for rid, reservation in sorted(state["reservations"].items()):
        usage = state["usage"][rid]
        result["reservation_usage"].append({"reservation_id": rid, "status": usage["status"],
            "latest_observation_operation_id": usage["latest_observation_operation_id"],
            "latest_receipt_operation_id": None if usage["latest_receipt"] is None else usage["latest_receipt"]["operation_id"],
            "latest_reconciliation_operation_id": usage["latest_reconciliation_operation_id"],
            "dimensions": [{"dimension_id": key, **{name: _decimal(number) for name, number in row.items()}}
                           for key, row in sorted(_reservation_usage(state, reservation).items())]})
    result["breaches"] = list(state["breaches"].values())
    return result


def _balances(state):
    """Publish exact decimal balances, local facts, root admission gates, and unknown final usage."""
    result = []
    for (account_id, purpose), dimensions in sorted(_accounting(state).items()):
        unknown = sorted({rid for row in dimensions.values() for rid in row["unknown_reservation_ids"]})
        rows = [{"dimension_id": key,
                 **{name: number if name == "unknown_reservation_ids" else _decimal(number)
                    for name, number in row.items() if name != "commitment"}}
                for key, row in sorted(dimensions.items())]
        result.append({"account_id": account_id, "purpose": purpose, "dimensions": rows,
                       "unresolved_reservation_ids": unknown, "usage_complete": not unknown,
                       "breach": any(f["account_id"] == account_id and f["purpose"] == purpose
                                     for f in state["breaches"].values()),
                       "admission_blocked": _blocked(state, state["accounts"][account_id])})
    return result


def _history(connection):
    """Detach the complete ordered administrative history without modifying original values."""
    names = ("migration_id", "source_schema", "target_schema", "source_backup_id", "source_manifest_json", "provenance_json")
    return [dict(zip(names, row)) for row in connection.execute("SELECT * FROM migration_history ORDER BY migration_id")]


def inspect(store, limits):
    """Capture complete bounded history and balances from a single SQLite read snapshot."""
    require_schema(store)
    if type(limits) is not ResourceInspectionLimits:
        raise ResourceValidationError("limits: expected ResourceInspectionLimits")
    try:
        limits = ResourceInspectionLimits(limits.max_accounts, limits.max_operations, limits.max_metadata_bytes)
    except AttributeError as error:
        raise ResourceValidationError("malformed inspection limits") from error
    with store._transaction(reconciliation_id="operation_id") as connection:
        accounts = connection.execute("SELECT count(*) FROM resource_accounts").fetchone()[0]
        operations = connection.execute("SELECT count(*) FROM resource_operations").fetchone()[0]
        if accounts > limits.max_accounts or operations > limits.max_operations:
            raise ResourceInspectionLimitError("inspection count limits exceeded")
        _fault("inspection_after_counts")
        # Preflight lengths incrementally in Python: never SQLite SUM over input
        # quantities or potentially unbounded metadata totals, and never truncate.
        size = 0
        for table, expressions in (("resource_operations", ("request_json", "result_json")),
                                   ("resource_accounts", ("scope_json", "dimensions_json", "limits_json", "policy_json")),
                                   ("resource_allocations", ("purpose_limits_json",)),
                                   ("resource_reservations", ("maxima_json", "call_bounds_json")),
                                   ("resource_record_links", ("operation_id", "target_id", "relationship", "target_kind")),
                                   ("migration_history", ("source_manifest_json", "provenance_json"))):
            for row in connection.execute("SELECT " + ','.join(f"length(CAST({c} AS BLOB))" for c in expressions) + " FROM " + table):
                size += sum(row)
                if size > limits.max_metadata_bytes:
                    raise ResourceInspectionLimitError("inspection metadata preflight limit exceeded")
        state, operations = validate_ledger(connection)
        body = {"format": "research_pipeline.resource_snapshot", "version": 2, "schema_version": 3,
                "schema_identity": _schema_identity(3), "resource_sequence": len(operations),
                "administrative_history": _history(connection), "operations": operations,
                **_projections(state), "balances": _balances(state)}
        identity = hashlib.sha256(canonical(body).encode("ascii")).hexdigest()
        doc = {**body, "snapshot_id": identity}
        if len(canonical(doc)) > limits.max_metadata_bytes:
            raise ResourceInspectionLimitError("complete inspection exceeds metadata byte limit")
        return ResourceSnapshot(doc)


def validate_snapshot(value):
    """Check strict detached membership and computed balances against its declared operation history.

    This checks internal observation consistency only; detached data cannot resolve
    scientific references or authenticate the source of a claimed observation.
    """
    fields(value, "format version schema_version schema_identity resource_sequence administrative_history operations accounts allocations reservations reservation_usage breaches balances snapshot_id", "resource snapshot")
    if (value["format"] != "research_pipeline.resource_snapshot" or type(value["version"]) is not int
            or value["version"] != 2 or type(value["schema_version"]) is not int or value["schema_version"] != 3
            or canonical(value["schema_identity"]) != canonical(_schema_identity(3))):
        raise ResourceValidationError("unsupported resource snapshot identity")
    quantity(value["resource_sequence"], "resource sequence")
    for key in ("operations", "accounts", "allocations", "reservations", "reservation_usage", "breaches", "balances", "administrative_history"):
        if type(value[key]) is not list:
            raise ResourceValidationError("snapshot collections must be lists")
    state = _empty_state()
    receipts, ops, watermark = set(), set(), 0
    for i, item in enumerate(value["operations"], 1):
        fields(item, "request receipt", "snapshot operation")
        request = ResourceRequest.from_dict(item["request"])
        receipt = ResourceReceipt.from_dict(item["receipt"])
        doc, result = request.to_dict(), receipt.to_dict()
        if canonical(doc) != canonical(item["request"]) or canonical(result) != canonical(item["receipt"]):
            raise ResourceValidationError("noncanonical snapshot operation")
        if (doc["operation_id"] in ops or doc["receipt_id"] in receipts
                or result["scientific_watermark_event_id"] < watermark
                or receipt != _receipt(doc, request.fingerprint, i, result["committed_at"], result["scientific_watermark_event_id"])):
            raise ResourceValidationError("snapshot operation identity mismatch")
        _admit(state, doc)
        ops.add(doc["operation_id"])
        receipts.add(doc["receipt_id"])
        watermark = result["scientific_watermark_event_id"]
    if value["resource_sequence"] != len(ops):
        raise ResourceValidationError("snapshot sequence mismatch")
    for key, projection in _projections(state).items():
        if canonical(value[key]) != canonical(projection):
            raise ResourceValidationError("snapshot projection mismatch")
    if canonical(value["balances"]) != canonical(_balances(state)):
        raise ResourceValidationError("snapshot balances mismatch")
    history = []
    registrations = {}
    names = "migration_id source_schema target_schema source_backup_id source_manifest_json provenance_json"
    for row in value["administrative_history"]:
        fields(row, names, "administrative history")
        history.append(tuple(row[key] for key in names.split()))
        # A detached observation has no artifact inventory. Validate source
        # manifests/attribution here; the live/backup validator checks closure.
        for artifact in history_json(row["source_manifest_json"])["artifacts"]:
            old = registrations.setdefault(artifact["digest"], artifact["size"])
            if old != artifact["size"]:
                raise ResourceValidationError("inconsistent source artifact size")
    validate_history(history, list(registrations.items()), 3)
    body = {key: item for key, item in value.items() if key != "snapshot_id"}
    if hashlib.sha256(canonical(body).encode("ascii")).hexdigest() != value["snapshot_id"]:
        raise ResourceValidationError("resource snapshot digest mismatch")
