"""Read-only cumulative investigation budget observations, shared by CLI and agents."""
from datetime import datetime, timezone
from pathlib import Path
import time

from . import jobs


def boot_identity():
    try:
        return Path("/proc/sys/kernel/random/boot_id").read_text().strip()
    except OSError:
        return None


def budget_report(state, live=False):
    """Read-only observations; never charges time or changes an authorization."""
    recorded = state.get("active_seconds", 0)
    spent = recorded
    preparation = state.get("resume_preparation_pending") or state.get("recovery_finalization_pending")
    pending = preparation or state.get("accounting_pending") or state.get("owner_interval", {}).get("pending")
    complete = not pending
    observed_live = False
    boot = boot_identity() if live else None
    if live and boot is not None:
        interval = state.get("owner_interval")
        if preparation:
            if preparation.get("boot_id") == boot and preparation.get("started_monotonic") is not None:
                spent = recorded + min(preparation["allowance"],
                                       max(0, time.monotonic() - preparation["started_monotonic"]))
                complete = observed_live = True
        elif (interval and interval.get("pending") and interval.get("boot_id") == boot
                and interval.get("started_monotonic") is not None):
            spent = max(recorded, interval["initial_active_seconds"]
                        + max(0, time.monotonic() - interval["started_monotonic"]))
            complete = observed_live = True
        elif (state.get("accounting_pending") and state.get("boot_id") == boot
              and state.get("activation_started_monotonic") is not None):
            spent = recorded + max(0, time.monotonic() - state["activation_started_monotonic"]
                                    - state.get("activation_charged_seconds", 0))
            complete = observed_live = True
    allowance = state.get("limits", {}).get("wall_seconds")
    if allowance is not None:
        spent = min(allowance, spent)
    return {"configured_limits": dict(state.get("limits", {})),
            "observed_at": datetime.now(timezone.utc).isoformat(),
            "active_seconds_observed": spent, "active_seconds_recorded": recorded,
            "remaining_seconds_observed": max(0, allowance - spent) if complete and allowance is not None else None,
            "active_time_complete": complete,
            "observation": "Live controller interval included." if observed_live else
                           "Recorded accounting; unobserved work is unknown." if not complete else "Settled accounting.",
            "job_runtime_seconds": state.get("limits", {}).get("job_runtime_seconds"),
            "max_jobs": state.get("limits", {}).get("max_jobs"),
            "occupied_job_reservations": sum(r["state"] in jobs.ACTIVE for r in state.get("jobs", {}).values()),
            "model_usage_observed": state.get("usage_totals"),
            "model_usage_scope": "Emitted completed-turn counters observed so far; missing usage is unknown. "
                                 "Cached tokens are not added again; counters are not spending or context occupancy.",
            "job_enforcement_scope": "Admitted job argv and all descendants share the job deadline and original "
                                     "investigation wall/memory/zero-swap/task grants. Capacity remains occupied "
                                     "until cleanup is confirmed. Job count is not a CPU fraction or thread guarantee. "
                                     "Configured limits alone do not confirm a running service or enforcement check.",
            "model_usage_complete": bool(state.get("usage_totals") is not None and state.get("usage_complete", False)),
            "model_spending": "unknown; backend cannot cap spending",
            "context_occupancy": "unknown; fixed session rollover is a conservative fallback"}

