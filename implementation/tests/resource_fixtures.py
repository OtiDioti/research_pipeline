"""Small complete controller declarations for resource tests; no operating authority."""

from research_pipeline.domain import CreationProvenance
from research_pipeline.resources import ResourceRequest, ResourceInspectionLimits, UNITS
from tests.test_store import record, request

PROVENANCE = CreationProvenance("controller", "2026-11-01T00:00:00Z", {"synthetic": True})
DIMENSIONS = [{"dimension_id": "dim_" + k, "kind": k, "unit": unit, "currency": None, "scale": 1}
              for k, unit in UNITS.items()]
LIMITS = ResourceInspectionLimits(1000, 10000, 10_000_000)


def vector(default=0, **values):
    """Build all seven dimensions explicitly, deliberately differing IDs from kinds."""
    return [{"dimension_id": d["dimension_id"], "quantity": values.get(d["kind"], default)} for d in DIMENSIONS]


def policy(**updates):
    """Provision two exact 3-input/5-output calls and positive persistence overhead."""
    return {"policy_id": "run_policy", "statement": "Synthetic controller declaration only",
            "verification_minimum": vector(tool_calls=1),
            "handoff_minimum": vector(model_calls=2, model_input_tokens=6, model_output_tokens=10,
                                      local_time=1, local_storage=1),
            "closeout_minimum": vector(local_time=1, local_storage=1),
            "handoff_call_bounds": {"max_input_tokens_per_call": 3, "max_output_tokens_per_call": 5},
            "context_capacity_tokens": 8, "per_call_output_tokens": 5, "monetary_services": [], **updates}


def scope(kind, identity=None, revision=1):
    """Use required exact project/task references and explicit operational controller identities."""
    identity = identity or kind
    if kind in ("project", "task"):
        return {"type": "record", "kind": kind, "reference": {"record_id": identity, "revision": revision,
                "relationship": "resource_scope", "target_kind": "project" if kind == "project" else "task_specification"}}
    return {"type": "controller", "kind": kind, "stable_identity": identity}


def declaration(kind, identity, payload, **updates):
    """Create an exact complete immutable request with caller-chosen IDs."""
    return ResourceRequest(kind, "op_" + identity, "receipt_" + identity, PROVENANCE, [], [], payload, **updates)


def root_request(**updates):
    """Declare a root project ceiling with all supported nonmonetary dimensions."""
    return declaration("create_account", "project", {"account_id": "project", "owner_id": "owner",
                       "scope": scope("project"), "dimensions": DIMENSIONS, "ceiling": vector(1000),
                       "policy": {"policy_id": "root_policy", "statement": "Synthetic ceiling"}, **updates})


def pools(ordinary=100, verification=40, handoff=40, closeout=0):
    """Partition complete explicit vectors by purpose."""
    return {"ordinary": vector(ordinary), "verification": vector(verification),
            "handoff": vector(handoff), "closeout": vector(closeout)}


def allocation(kind, identity, parent, **updates):
    """Create one child with immutable purpose budgets and a run-only policy declaration."""
    limits = pools(closeout=10) if kind == "run" else pools()
    if kind == "attempt":
        limits = pools(25, 10, 20)
    return declaration("allocate", identity, {"allocation_id": "allocation_" + identity,
                       "parent_account_id": parent, "account_id": identity, "owner_id": "owner",
                       "scope": scope(kind, identity), "purpose_limits": limits,
                       "run_policy": policy() if kind == "run" else None, **updates})


def reservation(identity="work", account="attempt", purpose="ordinary", **updates):
    """Reserve one tool call by default without model token claims."""
    return declaration("reserve", identity, {"reservation_id": "reservation_" + identity,
                       "account_id": account, "owner_id": "owner", "purpose": purpose,
                       "maxima": vector(tool_calls=1), "call_bounds": None, **updates})


def populate(store, *, attempts=1):
    """Install scientific scopes and a complete project/run/task/attempt allocation chain."""
    store.submit(request("scopes", [record("project", kind="project"), record("task", kind="task_specification")]))
    declarations = [root_request(), allocation("run", "run", "project"), allocation("task", "task", "run")]
    declarations.extend(allocation("attempt", "attempt" if i == 0 else "attempt" + str(i + 1), "task") for i in range(attempts))
    receipts = []
    for item in declarations:
        method = store.create_resource_account if item.to_dict()["kind"] == "create_account" else store.allocate_resources
        receipts.append(method(item))
    return declarations, receipts


def changed(request_value, **payload_updates):
    """Reconstruct a changed payload while retaining immutable operation identity for retry tests."""
    doc = request_value.to_dict()
    doc["payload"].update(payload_updates)
    return ResourceRequest.from_dict(doc)
